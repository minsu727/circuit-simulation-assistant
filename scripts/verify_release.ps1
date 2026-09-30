# Optional post-install smoke check. Windows PowerShell 5.1 only; no Python/Git.
# Run the first clean-machine smoke manually with Setup.exe alone, then use this.
# Never installs/uninstalls, changes Windows features, or runs a simulation/API.
param(
    [Parameter(Mandatory=$true)][string]$Setup,
    [string]$InstalledExe = '',
    [string]$Report = ''
)
$ErrorActionPreference = 'Stop'
if (-not $Report) { $Report = Join-Path $PSScriptRoot '..\installer_output\release-validation\release-smoke.json' }
$process = $null
$started = $false
$stdoutTask = $null
$stderrTask = $null
$result = [ordered]@{schema_version=1; clean_vm_verified=$false; simulation_run=$false}

function Get-OwnedListeners([int]$ProcessId) {
    $netstat = Join-Path $env:SystemRoot 'System32\netstat.exe'
    foreach ($line in (& $netstat -ano -p tcp)) {
        $fields = $line.Trim() -split '\s+'
        if ($fields.Count -eq 5 -and $fields[0] -eq 'TCP' -and
            $fields[3] -eq 'LISTENING' -and $fields[4] -eq [string]$ProcessId) {
            $fields[1]
        }
    }
}

try {
    $setupFile = Get-Item -LiteralPath $Setup
    if ($setupFile.PSIsContainer -or $setupFile.Extension -ne '.exe') { throw 'Setup must be an existing executable.' }
    $result.installer = [ordered]@{
        file=$setupFile.Name; bytes=$setupFile.Length
        sha256=(Get-FileHash -LiteralPath $setupFile.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        last_write_utc=$setupFile.LastWriteTimeUtc.ToString('o')
    }
    $version = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
    $result.windows = [ordered]@{edition=$version.EditionID; display_version=$version.DisplayVersion; build=$version.CurrentBuild; revision=$version.UBR}
    $result.admin_token = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    $result.python_absence_verified = $false
    if ($InstalledExe) {
        $exe = Get-Item -LiteralPath $InstalledExe
        if ($exe.Name -ne 'CircuitSimulationAssistant.exe' -or $exe.PSIsContainer) { throw 'Select the installed CircuitSimulationAssistant.exe.' }
        if (-not (Test-Path -LiteralPath (Join-Path $exe.DirectoryName '_internal\python313.dll'))) { throw 'Bundled Python runtime missing.' }
        $start = New-Object System.Diagnostics.ProcessStartInfo
        $start.FileName = $exe.FullName
        $start.Arguments = '--no-browser'
        $start.WorkingDirectory = $env:TEMP
        $start.UseShellExecute = $false
        $start.CreateNoWindow = $true
        $start.RedirectStandardOutput = $true
        $start.RedirectStandardError = $true
        foreach ($name in @('PYTHONPATH','PYTHONHOME','VIRTUAL_ENV','OPENAI_API_KEY','LTSPICE_EXECUTABLE')) {
            $start.EnvironmentVariables.Remove($name)
        }
        $start.EnvironmentVariables['PATH'] = Join-Path $env:SystemRoot 'System32'
        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $start
        $started = $process.Start()
        if (-not $started) { throw 'Could not start installed executable.' }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        Add-Type -AssemblyName System.Net.Http
        $handler = New-Object System.Net.Http.HttpClientHandler
        $handler.UseProxy = $false
        $client = New-Object System.Net.Http.HttpClient($handler)
        $client.Timeout = [TimeSpan]::FromSeconds(2)
        try {
            $ready = $false
            $deadline = [DateTime]::UtcNow.AddSeconds(60)
            while ([DateTime]::UtcNow -lt $deadline -and -not $process.HasExited) {
                $listeners = @(Get-OwnedListeners $process.Id)
                foreach ($address in $listeners) {
                    if ($address -notmatch '^127\.0\.0\.1:\d+$') { throw 'Application exposed a non-loopback listener.' }
                    try {
                        $response = $client.GetAsync('http://' + $address + '/_stcore/health').GetAwaiter().GetResult()
                        try { $ready = $response.IsSuccessStatusCode -and $response.Content.ReadAsStringAsync().GetAwaiter().GetResult().Trim() -eq 'ok' }
                        finally { $response.Dispose() }
                    } catch { $ready = $false }
                    if ($ready) { break }
                }
                if ($ready) { break }
                Start-Sleep -Milliseconds 250
            }
            if (-not $ready) { throw 'Installed server did not become healthy within 60 seconds.' }
            $result.listen_addresses = @(Get-OwnedListeners $process.Id)
            if (-not $result.listen_addresses.Count -or @($result.listen_addresses | Where-Object { $_ -notmatch '^127\.0\.0\.1:\d+$' }).Count) { throw 'Expected only IPv4 loopback listeners.' }
            $result.localhost_health = $true
            $process.Refresh()
            $pythonDlls = @($process.Modules | Where-Object { $_.ModuleName -match '^python\d+\.dll$' })
            if (-not $pythonDlls.Count) { throw 'Could not observe loaded bundled Python DLL.' }
            $internal = [IO.Path]::GetFullPath((Join-Path $exe.DirectoryName '_internal')) + '\'
            foreach ($module in $pythonDlls) {
                if (-not $module.FileName.StartsWith($internal, [StringComparison]::OrdinalIgnoreCase)) { throw 'Python DLL was loaded outside the installed bundle.' }
            }
            $result.python_dlls = @($pythonDlls | ForEach-Object ModuleName)
            $result.bundled_python_observed = $true
            $result.development_environment_removed = $true
            $result.unrelated_working_directory = $true
            $result.browser_check = 'Not performed by this helper; use the manual checklist or UI verification.'
        } finally { $client.Dispose(); $handler.Dispose() }
    }
    $result.status = 'passed'
} catch {
    $result.status = 'failed'
    # Errors can contain local paths. Keep the public report to the exception type.
    $result.error_type = $_.Exception.GetType().Name
} finally {
    if ($started) {
        # Terminate ONLY this helper's own no-browser smoke process, never an
        # existing user app. Normal Ctrl+C shutdown is tested separately.
        if (-not $process.HasExited) { $process.Kill(); $process.WaitForExit() }
        $outputText = $stdoutTask.GetAwaiter().GetResult() + $stderrTask.GetAwaiter().GetResult()
        $result.shutdown = 'Owned smoke process terminated; not a graceful-exit test.'
        $result.server_stopped = @(Get-OwnedListeners $process.Id).Count -eq 0
        $result.console_no_development_path = $outputText -notmatch '(?i)\.venv[\\/]|Desktop[\\/]circuit-ai-report|[A-Z]:[\\/]Users[\\/]'
        if (-not $result.server_stopped -or -not $result.console_no_development_path) { $result.status = 'failed' }
    }
    if ($process) { $process.Dispose() }
    $reportPath = [IO.Path]::GetFullPath($Report)
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($reportPath)) | Out-Null
    $result | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $reportPath -Encoding UTF8
}
$result | ConvertTo-Json -Depth 5
if ($result.status -ne 'passed') { exit 1 }

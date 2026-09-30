param(
    [string]$ISCC = '',
    [string]$PortableDir = ''
)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
try {
    if (-not $PortableDir) { $PortableDir = Join-Path $projectRoot 'dist\CircuitSimulationAssistant' }
    $PortableDir = [IO.Path]::GetFullPath($PortableDir)
    foreach ($required in @('CircuitSimulationAssistant.exe', '_internal\app.py', '_internal\python313.dll')) {
        if (-not (Test-Path -LiteralPath (Join-Path $PortableDir $required) -PathType Leaf)) {
            throw 'Portable output is missing or incomplete. Run scripts/build_windows.ps1 first.'
        }
    }
    $items = Get-ChildItem -LiteralPath $PortableDir -Recurse -Force
    foreach ($item in $items) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Portable output contains a linked resource. Review the build folder.' }
        if ($item.Name -match '^(\.env($|\.)|secrets\.toml$|test_ltspice\.py$|LTspice\.exe$|XVIIx64\.exe$|scad3\.exe$|\.git$|\.venv$|simulation_input$|simulation_output$)' -or
            $item.Extension -in @('.raw', '.log', '.asc')) {
            throw 'Portable output contains private or external simulation files. Rebuild a clean portable folder.'
        }
    }
    if (-not $ISCC) { $ISCC = $env:ISCC_EXE }
    if ($ISCC) {
        if (-not (Test-Path -LiteralPath $ISCC -PathType Leaf)) { throw 'Configured ISCC.exe was not found. Fix -ISCC or ISCC_EXE.' }
    } else {
        $command = Get-Command ISCC.exe -CommandType Application -ErrorAction SilentlyContinue
        if ($command) { $ISCC = $command.Source }
        foreach ($base in @(${env:ProgramFiles(x86)}, $env:ProgramFiles, (Join-Path $env:LOCALAPPDATA 'Programs'))) {
            if (-not $ISCC -and $base) {
                $candidate = Join-Path $base 'Inno Setup 6\ISCC.exe'
                if (Test-Path -LiteralPath $candidate -PathType Leaf) { $ISCC = $candidate }
            }
        }
    }
    if (-not $ISCC) { throw 'Inno Setup 6 was not found. Install it from https://jrsoftware.org/isdl.php, or set ISCC_EXE / pass -ISCC with the compiler path.' }
    $ISCC = (Resolve-Path -LiteralPath $ISCC).Path
    # ISCC's Windows file-version resource can be 0.0.0.0. The recipe checks
    # Inno's authoritative preprocessor Ver value and reports the real version.
    Write-Host 'Compiling with Inno Setup (recipe requires major version 6).'
    $outputDir = Join-Path $projectRoot 'installer_output'
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    $recipe = Join-Path $projectRoot 'installer\CircuitSimulationAssistant.iss'
    & $ISCC '/Qp' ('/DPortableDir=' + $PortableDir) ('/O' + $outputDir) $recipe
    $compileExit = $LASTEXITCODE
    if ($compileExit -ne 0) {
        [Console]::Error.WriteLine('Installer compile failed. ISCC exit code: ' + $compileExit)
        exit $compileExit
    }
    $setup = Join-Path $outputDir 'CircuitSimulationAssistant-Setup.exe'
    if (-not (Test-Path -LiteralPath $setup -PathType Leaf)) { throw 'ISCC succeeded but expected Setup.exe is missing.' }
    Write-Host 'Installer ready: installer_output/CircuitSimulationAssistant-Setup.exe'
    Write-Host ('Installer bytes: ' + (Get-Item -LiteralPath $setup).Length)
    exit 0
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}

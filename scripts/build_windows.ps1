param([string]$Python = '')
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (-not $Python) { $Python = Join-Path $projectRoot '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw 'Python not found. Create .venv and install requirements.txt and requirements-build.txt.' }
Push-Location $projectRoot
try {
    & $Python -c "import PyInstaller, streamlit; assert PyInstaller.__version__ == '6.22.3'; assert streamlit.__version__ == '1.63.0'"
    if ($LASTEXITCODE -ne 0) { throw 'Install the pinned build and runtime requirements first.' }
    # Remove only these exact generated subfolders; never user simulation data.
    foreach ($relative in @('build\CircuitSimulationAssistant', 'dist\CircuitSimulationAssistant')) {
        $target = [IO.Path]::GetFullPath((Join-Path $projectRoot $relative))
        if (-not $target.StartsWith($projectRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Build path escaped workspace.' }
        if (Test-Path -LiteralPath $target) {
            if ((Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Refusing to clean a linked build directory.' }
            Remove-Item -LiteralPath $target -Recurse -Force
        }
    }
    & $Python -m PyInstaller --noconfirm --clean --distpath dist --workpath build CircuitSimulationAssistant.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
    $expected = Join-Path $projectRoot 'dist\CircuitSimulationAssistant\CircuitSimulationAssistant.exe'
    if (-not (Test-Path -LiteralPath $expected -PathType Leaf)) { throw 'Expected executable is missing.' }
    Write-Host 'Portable folder ready: dist/CircuitSimulationAssistant/'
} finally { Pop-Location }

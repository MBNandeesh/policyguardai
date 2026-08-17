<#
PowerShell helper to create a Python 3.12 virtual environment for the backend.
Usage: run in repository root as Administrator or normal user if Python 3.12 is installed.
#>
param()

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Error "The 'py' launcher is not available. Install Python 3.12 and ensure 'py' is on PATH."
    exit 1
}

$py312 = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
if ($LASTEXITCODE -ne 0 -or -not $py312) {
    Write-Error "Python 3.12 is not installed or not registered with the py launcher. Install Python 3.12 first."
    exit 1
}

$venvDir = "backend/.venv"
if (-not (Test-Path $venvDir)) {
    & py -3.12 -m venv $venvDir
}

Write-Output "Activating venv and installing requirements..."
& "$venvDir/Scripts/python.exe" -m pip install --upgrade pip
& "$venvDir/Scripts/python.exe" -m pip install -r backend/requirements.txt

Write-Output "Done. Activate with: .\\backend\\.venv\\Scripts\\Activate.ps1"

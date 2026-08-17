$ErrorActionPreference = 'Stop'
Set-Location "C:\Users\Sahana\OneDrive\Desktop\SIH2026"
$py = "C:\Users\Sahana\OneDrive\Desktop\SIH2026\backend\.venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Error "Python 3.12 venv not found at $py"
    exit 1
}

& $py --version
& $py -m pip install -r "C:\Users\Sahana\OneDrive\Desktop\SIH2026\backend\requirements.txt"
& $py -m pytest -q

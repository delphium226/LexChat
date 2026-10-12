<#
.SYNOPSIS
    Installs pdfplumber and python-docx on the target from wheels committed to the repo.

.DESCRIPTION
    AILA reads uploaded PDFs and the text of Scottish judgments with pdfplumber,
    and uploaded Word documents with python-docx. Both are in
    server_py\requirements.txt, but the offline bundle predates them, and the
    target cannot reach PyPI. The wheels they need (Python 3.11, 64-bit Windows)
    are committed in deployment\pdf_wheels\, so `git pull` brings them.

    Installs with --no-index (never contacts PyPI), using the same Python the app
    runs under: server_py\venv if it exists (as start_native.cmd does), otherwise
    `python` on PATH. Packages already installed are left as they are.

    Run as Administrator (Python is installed for all users), then restart the
    app with stop_native.cmd and start_native.cmd.

.EXAMPLE
    cd C:\Projects\LexChat
    .\deployment\install_pdf_support.ps1
#>

$ErrorActionPreference = "Stop"

$repoRoot  = Split-Path -Parent $PSScriptRoot
$wheelDir  = Join-Path $PSScriptRoot "pdf_wheels"
$venvPy    = Join-Path $repoRoot "server_py\venv\Scripts\python.exe"

if (-not (Test-Path $wheelDir)) {
    Write-Error "Wheel folder not found: $wheelDir. Run git pull first."
}

if (Test-Path $venvPy) {
    $python = $venvPy
    Write-Host "Python : $python  (venv, as start_native.cmd uses)"
} else {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $cmd) { Write-Error "Python not found on PATH." }
    $python = $cmd.Source
    Write-Host "Python : $python  (system, as start_native.cmd uses)"
}

& $python --version

Write-Host ""
Write-Host "Installing pdfplumber and python-docx from $wheelDir (no internet needed)..."
& $python -m pip install --no-index --find-links="$wheelDir" "pdfplumber==0.11.10" "python-docx==1.2.0"
if ($LASTEXITCODE -ne 0) {
    Write-Error "pip install failed (exit code $LASTEXITCODE). Nothing else was changed."
}

Write-Host ""
Write-Host "Checking the imports..."
$failed = $false
foreach ($module in @("pdfplumber", "docx")) {
    & $python -c "import $module"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK]   import $module"
    } else {
        Write-Host "  [FAIL] import $module"
        $failed = $true
    }
}

Write-Host ""
if ($failed) {
    Write-Error "An import still fails. Send the output above to the developer."
}
Write-Host "Done. Restart the app: deployment\stop_native.cmd, then deployment\start_native.cmd"

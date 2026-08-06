$ErrorActionPreference = 'Stop'

$envFile = ".env.staging"
if (-not (Test-Path $envFile)) {
    Write-Host "[ERROR] $envFile not found. Please populate credentials in it." -ForegroundColor Red
    exit 1
}

# Read env file, ignoring comments and empty lines
Get-Content $envFile | Where-Object { $_ -match '^\s*([^#\s]+?)\s*=\s*(.*?)\s*$' } | ForEach-Object {
    $name = $matches[1]
    $value = $matches[2]
    Set-Item -Path "Env:$name" -Value $value
}

Write-Host "[INFO] Environment variables loaded from $envFile." -ForegroundColor Cyan
Write-Host "[INFO] Executing automated E2E smoke test..." -ForegroundColor Cyan

try {
    python tests/smoke_test_e2e.py
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        Write-Host "`n[SUCCESS] End-to-End smoke test validated! Credentials and receipts confirmed." -ForegroundColor Green
    } else {
        Write-Host "`n[FAIL] E2E smoke test failed with exit code $exitCode." -ForegroundColor Red
    }
    exit $exitCode
} catch {
    Write-Host "`n[FAIL] E2E smoke test encountered a critical error: $_" -ForegroundColor Red
    exit 1
}

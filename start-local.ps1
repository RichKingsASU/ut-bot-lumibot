# start-local.ps1 - Start all UT Bot Lumibot services locally
# Usage: powershell -ExecutionPolicy Bypass -File start-local.ps1

$ErrorActionPreference = "Stop"
$ROOT = "C:\github\ut-bot-lumibot"
$SUPABASE_DIR = "C:\Working\SupabaseProjects\UTBOT LUMIBOT"

Write-Host "`n=== UT Bot Lumibot - Local Startup ===" -ForegroundColor Cyan

# 1. Check Docker is running
Write-Host "`n[1/4] Checking Docker..." -ForegroundColor Yellow
try {
    docker info *>$null
    Write-Host "  Docker is running." -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Docker is not running. Start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# 2. Start Supabase
Write-Host "`n[2/4] Starting Supabase..." -ForegroundColor Yellow
Push-Location $SUPABASE_DIR
try {
    npx supabase start
    Write-Host "  Supabase started." -ForegroundColor Green
} catch {
    Write-Host "  WARNING: Supabase start failed (may already be running)." -ForegroundColor Yellow
}
Pop-Location

# 3. Start Dashboard + Netlify Functions in new terminal
Write-Host "`n[3/4] Starting Dashboard (Netlify Dev)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$ROOT\dashboard'; Write-Host 'Starting Netlify Dev...' -ForegroundColor Cyan; netlify dev --offline"
)
Write-Host "  Dashboard launching in new window." -ForegroundColor Green

# 4. Start Python bot in new terminal
Write-Host "`n[4/4] Starting Python Bot..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$ROOT'; & '$ROOT\venv\Scripts\Activate.ps1'; Write-Host 'Starting UT Bot...' -ForegroundColor Cyan; python main.py"
)
Write-Host "  Bot launching in new window." -ForegroundColor Green

# Summary
Write-Host "`n=== All Services Started ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Supabase Studio:      http://127.0.0.1:54323" -ForegroundColor White
Write-Host "  Dashboard + Functions: http://localhost:8888" -ForegroundColor White
Write-Host "  Bot:                   running in separate window" -ForegroundColor White
Write-Host ""
Write-Host "Press any key to exit this launcher..." -ForegroundColor DarkGray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

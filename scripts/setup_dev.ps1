# Solar Hub Development Environment Setup
# Run this script from the project root: .\scripts\setup_dev.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Solar Hub - Dev Environment Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# --------------------------------------------------------------------------
# 1. Check Prerequisites
# --------------------------------------------------------------------------
Write-Host "[1/6] Checking prerequisites..." -ForegroundColor Yellow

# Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "  ERROR: Python not found. Install Python 3.11+ from https://python.org" -ForegroundColor Red
    exit 1
}
$pyVersion = python --version 2>&1
Write-Host "  Python: $pyVersion" -ForegroundColor Green

# Node.js
$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) {
    Write-Host "  WARNING: Node.js not found. Frontend will not work." -ForegroundColor Yellow
    Write-Host "  Install Node.js 18+ from https://nodejs.org" -ForegroundColor Yellow
} else {
    $nodeVersion = node --version 2>&1
    Write-Host "  Node.js: $nodeVersion" -ForegroundColor Green
}

# Docker
$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
    Write-Host "  ERROR: Docker not found. Install Docker Desktop from https://docker.com" -ForegroundColor Red
    exit 1
}
$dockerVersion = docker --version 2>&1
Write-Host "  Docker: $dockerVersion" -ForegroundColor Green

# Docker Compose
try {
    docker compose version > $null 2>&1
    Write-Host "  Docker Compose: available" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Docker Compose not found." -ForegroundColor Red
    exit 1
}

Write-Host ""

# --------------------------------------------------------------------------
# 2. Start Infrastructure Services
# --------------------------------------------------------------------------
Write-Host "[2/6] Starting Docker services (postgres, timescaledb, redis)..." -ForegroundColor Yellow
docker compose up -d postgres timescaledb redis
Write-Host "  Waiting for services to be healthy..." -ForegroundColor Gray
Start-Sleep -Seconds 10

# Verify services
$healthy = $true
docker compose ps --format "table {{.Name}}\t{{.Status}}" | ForEach-Object {
    Write-Host "  $_" -ForegroundColor Green
}
Write-Host ""

# --------------------------------------------------------------------------
# 3. Install Python Dependencies
# --------------------------------------------------------------------------
Write-Host "[3/6] Installing Python dependencies..." -ForegroundColor Yellow

Write-Host "  System A..." -ForegroundColor Gray
pip install -r system_a/requirements.txt --quiet 2>&1 | Out-Null
Write-Host "  System A dependencies installed" -ForegroundColor Green

Write-Host "  System B..." -ForegroundColor Gray
if (Test-Path "system_b/requirements.txt") {
    pip install -r system_b/requirements.txt --quiet 2>&1 | Out-Null
    Write-Host "  System B dependencies installed" -ForegroundColor Green
} else {
    Write-Host "  System B requirements.txt not found, skipping" -ForegroundColor Yellow
}
Write-Host ""

# --------------------------------------------------------------------------
# 4. Run Database Migrations
# --------------------------------------------------------------------------
Write-Host "[4/6] Running database migrations..." -ForegroundColor Yellow

Write-Host "  System A (PostgreSQL)..." -ForegroundColor Gray
Push-Location system_a
try {
    python -m alembic upgrade head 2>&1
    Write-Host "  System A migrations complete" -ForegroundColor Green
} catch {
    Write-Host "  WARNING: System A migrations failed: $_" -ForegroundColor Yellow
}
Pop-Location

Write-Host "  System B (TimescaleDB)..." -ForegroundColor Gray
Push-Location system_b
try {
    python -m alembic upgrade head 2>&1
    Write-Host "  System B migrations complete" -ForegroundColor Green
} catch {
    Write-Host "  WARNING: System B migrations failed: $_" -ForegroundColor Yellow
}
Pop-Location
Write-Host ""

# --------------------------------------------------------------------------
# 5. Install Frontend Dependencies
# --------------------------------------------------------------------------
Write-Host "[5/6] Installing frontend dependencies..." -ForegroundColor Yellow
if (Test-Path "frontend/package.json") {
    Push-Location frontend
    npm install --silent 2>&1 | Out-Null
    Pop-Location
    Write-Host "  Frontend dependencies installed" -ForegroundColor Green
} else {
    Write-Host "  Frontend package.json not found, skipping" -ForegroundColor Yellow
}
Write-Host ""

# --------------------------------------------------------------------------
# 6. Run Tests
# --------------------------------------------------------------------------
Write-Host "[6/6] Running tests to verify setup..." -ForegroundColor Yellow
Push-Location system_a
python -m pytest tests/ --tb=short -q 2>&1
Pop-Location
Write-Host ""

# --------------------------------------------------------------------------
# Done - Print Instructions
# --------------------------------------------------------------------------
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To start the full stack, open separate terminals:" -ForegroundColor White
Write-Host ""
Write-Host "  1. System B (Telemetry API - port 8001):" -ForegroundColor Yellow
Write-Host "     cd system_b" -ForegroundColor Gray
Write-Host '     python -m uvicorn app.main:app --port 8001 --reload' -ForegroundColor Gray
Write-Host ""
Write-Host "  2. System A (Platform API - port 8000):" -ForegroundColor Yellow
Write-Host "     cd system_a" -ForegroundColor Gray
Write-Host '     python -m uvicorn app.main:app --port 8000 --reload' -ForegroundColor Gray
Write-Host ""
Write-Host "  3. Frontend (React - port 5173):" -ForegroundColor Yellow
Write-Host "     cd frontend" -ForegroundColor Gray
Write-Host "     npm run dev" -ForegroundColor Gray
Write-Host ""
Write-Host "  4. Device Simulator (optional):" -ForegroundColor Yellow
Write-Host "     python scripts/device_simulator.py --devices 2 --interval 30" -ForegroundColor Gray
Write-Host ""
Write-Host "  5. Trigger manual sync (after simulator runs):" -ForegroundColor Yellow
Write-Host '     curl -X POST "http://localhost:8000/api/v1/dashboard/sync?site_id=YOUR_SITE_ID" -H "Authorization: Bearer YOUR_TOKEN"' -ForegroundColor Gray
Write-Host ""
Write-Host "API Docs:  http://localhost:8000/docs" -ForegroundColor Green
Write-Host "Frontend:  http://localhost:5173" -ForegroundColor Green
Write-Host ""

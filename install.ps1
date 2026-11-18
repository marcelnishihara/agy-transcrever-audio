# Script de instalacao e inicializacao rapida para Windows (PowerShell)
$ErrorActionPreference = "Stop"

Write-Host "=== Instalando Skill agy-transcrever-audio (v0.0.1) para Windows ===" -ForegroundColor Cyan

# 1. Cria ambiente virtual se nao existir
if (-not (Test-Path "venv")) {
    Write-Host ">> Criando ambiente virtual Python (venv)..." -ForegroundColor Yellow
    python -m venv venv
}

# 2. Instala dependencias
Write-Host ">> Instalando dependencias minimas..." -ForegroundColor Yellow
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\pip.exe install -r requirements.txt

# 3. Configura .env a partir do .env.example se necessario
if (-not (Test-Path ".env")) {
    Write-Host ">> Criando arquivo .env a partir de .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "Lembre-se de configurar a sua OPENAI_API_KEY no arquivo .env!" -ForegroundColor Magenta
}

Write-Host ">> Validando instalacao..." -ForegroundColor Yellow
.\venv\Scripts\python.exe scripts\transcrever.py --check

Write-Host "=== Instalacao concluida com sucesso! ===" -ForegroundColor Green

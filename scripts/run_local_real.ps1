$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$env:ENV_FILE = ".env"
$env:DJANGO_SETTINGS_MODULE = "config.settings.dev"

Write-Host "Ambiente: REAL LOCAL"
Write-Host "Env file:  .env"
Write-Host "URL:       http://127.0.0.1:8000"
Write-Host ""

python manage.py migrate
python manage.py runserver 127.0.0.1:8000

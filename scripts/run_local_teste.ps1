$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$branch = git branch --show-current
if ($branch -ne "dev/teste-local" -and $branch -ne "dev/local-teste") {
    throw "Para alterar codigo sem afetar o real, rode este script na pasta de teste: C:\Users\tiago\OneDrive\Documentos\Gerenciador de Viagens"
}

$envFile = Join-Path $projectRoot ".env.local.teste"

if (-not (Test-Path $envFile)) {
    if (-not (Test-Path ".env")) {
        throw "Arquivo .env nao encontrado. Crie o .env principal antes de iniciar o ambiente de teste."
    }

    $content = Get-Content ".env"

    $content = $content | ForEach-Object {
        if ($_ -match "^DB_ENGINE=") {
            "DB_ENGINE=django.db.backends.sqlite3"
        } elseif ($_ -match "^DB_NAME=") {
            "DB_NAME=dados/local_teste.sqlite3"
        } elseif ($_ -match "^DB_USER=") {
            "DB_USER="
        } elseif ($_ -match "^DB_PASSWORD=") {
            "DB_PASSWORD="
        } elseif ($_ -match "^DB_HOST=") {
            "DB_HOST="
        } elseif ($_ -match "^DB_PORT=") {
            "DB_PORT="
        } elseif ($_ -match "^MEDIA_ROOT=") {
            "MEDIA_ROOT=media_teste"
        } elseif ($_ -match "^STATIC_ROOT=") {
            "STATIC_ROOT=staticfiles_teste"
        } elseif ($_ -match "^LOGIN_ENFORCED=") {
            "LOGIN_ENFORCED=false"
        } else {
            $_
        }
    }

    if (-not ($content -match "^MEDIA_ROOT=")) {
        $content += "MEDIA_ROOT=media_teste"
    }
    if (-not ($content -match "^STATIC_ROOT=")) {
        $content += "STATIC_ROOT=staticfiles_teste"
    }
    if (-not ($content -match "^LOGIN_ENFORCED=")) {
        $content += "LOGIN_ENFORCED=false"
    }

    $content | Set-Content $envFile -Encoding UTF8
    Write-Host "Criado .env.local.teste usando o .env principal como base."
}

$env:ENV_FILE = ".env.local.teste"
$env:DJANGO_SETTINGS_MODULE = "config.settings.dev"

Write-Host "Ambiente: TESTE LOCAL"
Write-Host "Env file:  .env.local.teste"
Write-Host "URL:       http://127.0.0.1:8001"
Write-Host ""

& "$PSScriptRoot\setup_local_teste_db.ps1"
python manage.py runserver 127.0.0.1:8001

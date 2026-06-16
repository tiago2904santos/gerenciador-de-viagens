$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Test-Path ".env.local.teste")) {
    if (-not (Test-Path ".env")) {
        throw "Arquivo .env nao encontrado. Crie o .env principal antes de preparar o ambiente de teste."
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

    $content | Set-Content ".env.local.teste" -Encoding UTF8
    Write-Host "Criado .env.local.teste usando o .env principal como base."
}

$envVars = @{}
Get-Content ".env.local.teste" | ForEach-Object {
    if ($_ -match "^\s*#" -or $_ -notmatch "=") {
        return
    }
    $parts = $_ -split "=", 2
    $envVars[$parts[0].Trim()] = $parts[1].Trim()
}

$dbName = $envVars["DB_NAME"]
$dbEngine = $envVars["DB_ENGINE"]
$dbUser = $envVars["DB_USER"]
$dbPassword = $envVars["DB_PASSWORD"]
$dbHost = if ($envVars["DB_HOST"]) { $envVars["DB_HOST"] } else { "127.0.0.1" }
$dbPort = if ($envVars["DB_PORT"]) { $envVars["DB_PORT"] } else { "5432" }

if (-not $dbName) {
    throw ".env.local.teste precisa ter DB_NAME."
}

if ($dbEngine -eq "django.db.backends.sqlite3") {
    $env:ENV_FILE = ".env.local.teste"
    $env:DJANGO_SETTINGS_MODULE = "config.settings.dev"
    python manage.py migrate
    exit
}

if (-not $dbUser -or -not $dbPassword) {
    throw ".env.local.teste precisa ter DB_USER e DB_PASSWORD para PostgreSQL."
}

$env:PGPASSWORD = $dbPassword

$exists = psql -h $dbHost -p $dbPort -U $dbUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$dbName';"
if ($LASTEXITCODE -ne 0) {
    throw "Nao foi possivel consultar o PostgreSQL com o usuario $dbUser."
}

if ($exists -eq "1") {
    Write-Host "Banco $dbName ja existe."
} else {
    createdb -h $dbHost -p $dbPort -U $dbUser $dbName
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "O usuario $dbUser nao conseguiu criar o banco $dbName."
        Write-Host "Execute uma vez como administrador do PostgreSQL:"
        Write-Host ""
        Write-Host "psql -U postgres -c `"CREATE DATABASE $dbName OWNER $dbUser;`""
        Write-Host "psql -U postgres -d $dbName -c `"GRANT ALL ON SCHEMA public TO $dbUser;`""
        Write-Host ""
        throw "Banco de teste ainda nao foi criado."
    }
    Write-Host "Banco $dbName criado."
}

$env:ENV_FILE = ".env.local.teste"
$env:DJANGO_SETTINGS_MODULE = "config.settings.dev"
python manage.py migrate

param(
    [string]$NewPassword,
    [string]$ServiceName = "postgresql-x64-16",
    [string]$DataDir = "C:\Program Files\PostgreSQL\16\data",
    [string]$BinDir = "C:\Program Files\PostgreSQL\16\bin"
)

$ErrorActionPreference = "Stop"

if (-not $NewPassword) {
    throw "Informe a nova senha. Exemplo: .\scripts\reset_postgres_password_admin.ps1 -NewPassword `"sua-senha`""
}

$hbaPath = Join-Path $DataDir "pg_hba.conf"
$backupPath = "$hbaPath.bak-reset-$(Get-Date -Format 'yyyyMMddHHmmss')"
$psqlPath = Join-Path $BinDir "psql.exe"

if (-not (Test-Path $hbaPath)) {
    throw "pg_hba.conf nao encontrado em: $hbaPath"
}

if (-not (Test-Path $psqlPath)) {
    throw "psql.exe nao encontrado em: $psqlPath"
}

Copy-Item $hbaPath $backupPath

try {
    $hba = Get-Content $hbaPath
    $updated = $hba | ForEach-Object {
        if ($_ -match "^host\s+all\s+all\s+127\.0\.0\.1/32\s+") {
            "host    all             all             127.0.0.1/32            trust"
        } elseif ($_ -match "^host\s+all\s+all\s+::1/128\s+") {
            "host    all             all             ::1/128                 trust"
        } else {
            $_
        }
    }

    $updated | Set-Content $hbaPath -Encoding ASCII

    Restart-Service $ServiceName

    & $psqlPath -U postgres -h 127.0.0.1 -d postgres -c "ALTER USER postgres WITH PASSWORD '$NewPassword';"
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao alterar a senha do usuario postgres."
    }

    Copy-Item $backupPath $hbaPath -Force
    Restart-Service $ServiceName

    Write-Host "Senha do usuario postgres redefinida com sucesso."
}
catch {
    if (Test-Path $backupPath) {
        Copy-Item $backupPath $hbaPath -Force
        Restart-Service $ServiceName
    }
    throw
}

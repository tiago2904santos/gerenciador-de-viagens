$ErrorActionPreference = "Stop"

psql -U postgres -c "CREATE DATABASE central_viagens_teste OWNER central_viagens_user;"
psql -U postgres -d central_viagens_teste -c "GRANT ALL ON SCHEMA public TO central_viagens_user;"

Write-Host "Banco central_viagens_teste preparado."

# E2 - Persistencia RDS + DynamoDB (FLOCI). Ejecutar desde raiz del proyecto.
$ErrorActionPreference = "Stop"
$ENDPOINT = "http://localhost:4566"
$env:AWS_ACCESS_KEY_ID = "test"; $env:AWS_SECRET_ACCESS_KEY = "test"; $env:AWS_DEFAULT_REGION = "us-east-1"

Write-Host "== RDS describe =="
aws --endpoint-url $ENDPOINT rds describe-db-instances --query "DBInstances[].{ID:DBInstanceIdentifier,Addr:Endpoint.Address,Port:Endpoint.Port}" --output table
# RDS endpoint lomax-db (proxy en 172.17.0.2:7001). Para psql usar contenedor:
Write-Host "== Aplicando schema via contenedor postgres cliente =="
docker run --rm --network host -v "${PWD}/db:/db" -e PGPASSWORD=admin123 postgres:16-alpine `
  psql -h 172.17.0.2 -p 7001 -U admin -d admin -f /db/01-schema.sql
docker run --rm --network host -v "${PWD}/db:/db" -e PGPASSWORD=admin123 postgres:16-alpine `
  psql -h 172.17.0.2 -p 7001 -U admin -d admin -f /db/02-seed.sql

Write-Host "== DynamoDB create-table =="
python ./dynamodb/create_table.py
aws --endpoint-url $ENDPOINT dynamodb describe-table --table-name lomax-productos --query "Table.{Name:TableName,Status:TableStatus}"
Write-Host "E2 listo. Guardar salidas en evidencias/E2/"

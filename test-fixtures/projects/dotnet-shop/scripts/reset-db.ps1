#Requires -Version 7
<#
.SYNOPSIS
    Drops and recreates the local Shop database and applies all EF Core migrations.
.EXAMPLE
    pwsh scripts/reset-db.ps1 -Seed
#>
param(
    [string]$Connection = "Server=localhost,1433;Database=Shop;User Id=sa;Password=$env:SHOP_SA_PASSWORD;TrustServerCertificate=True",
    [switch]$Seed
)

$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

if (-not $env:SHOP_SA_PASSWORD) {
    throw "SHOP_SA_PASSWORD is not set. Export it before running this script."
}

Write-Host "Dropping local database..."
dotnet ef database drop --force --project src/Shop.Infrastucture --startup-project src/Shop.Api

Write-Host "Applying migrations..."
dotnet ef database update --project src/Shop.Infrastucture --startup-project src/Shop.Api --connection $Connection

if ($Seed) {
    Write-Host "Seeding demo customers and invoices..."
    dotnet run --project src/Shop.Api -- --seed-demo-data
}

Write-Host "Done."

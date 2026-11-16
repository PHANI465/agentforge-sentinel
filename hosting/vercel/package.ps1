param(
    [Parameter(Mandatory = $true)]
    [string] $Destination
)

$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath (Join-Path $PSScriptRoot '../..')
try {
    uv run --locked --no-sync python hosting/vercel/package_release.py $Destination
    if ($LASTEXITCODE) { throw 'Could not package Sentinel release.' }
} finally {
    Pop-Location
}

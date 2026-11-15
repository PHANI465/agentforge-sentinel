param(
    [Parameter(Mandatory = $true)]
    [string] $Destination
)

$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$stage = [IO.Path]::GetFullPath($Destination)
if (Test-Path -LiteralPath $stage) { throw "Choose a new deployment directory." }
if ($stage.StartsWith($project + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Use a deployment directory outside the project."
}
New-Item -ItemType Directory -Path $stage | Out-Null
Push-Location -LiteralPath $project
try {
    $sourceZip = Join-Path $stage 'app-source.tar'
    git archive --format=tar -o $sourceZip HEAD src/sentinel ml data_pipeline
    if ($LASTEXITCODE) { throw "Could not archive the tracked backend." }
    tar.exe -xf $sourceZip -C $stage
    if ($LASTEXITCODE) { throw "Could not extract the tracked backend." }
    Remove-Item -LiteralPath $sourceZip
    Move-Item -LiteralPath (Join-Path $stage 'src/sentinel') -Destination (Join-Path $stage 'sentinel')
    Remove-Item -LiteralPath (Join-Path $stage 'src')
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'app.py') -Destination $stage
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'vercel.json') -Destination $stage

    $requirements = Join-Path $stage 'requirements.txt'
    uv export --locked --no-dev --no-hashes --no-header --no-emit-project --output-file $requirements --quiet
    if ($LASTEXITCODE) { throw "Could not export the locked runtime dependencies." }

    $public = Join-Path $stage 'public'
    Copy-Item -LiteralPath (Join-Path $project 'public_site/static') -Destination $public -Recurse
    Copy-Item -LiteralPath (Join-Path $project 'web/dist') -Destination (Join-Path $public 'workbench') -Recurse
    [IO.File]::WriteAllText((Join-Path $stage '.python-version'), '3.12' + [char]10)
    Write-Output "Prepared FastAPI, static site and analyst build."
} finally {
    Pop-Location
}

param(
    [string]$VendorRoot = "vendor/ageverify"
)

$ErrorActionPreference = "Stop"

$repos = @(
    "https://github.com/eu-digital-identity-wallet/av-web-verifier-ui.git",
    "https://github.com/eu-digital-identity-wallet/av-srv-web-verifier-endpoint-23220-4-kt.git",
    "https://github.com/eu-digital-identity-wallet/av-doc-technical-specification.git"
)

New-Item -ItemType Directory -Force -Path $VendorRoot | Out-Null

foreach ($repo in $repos) {
    $name = [System.IO.Path]::GetFileNameWithoutExtension($repo)
    $target = Join-Path $VendorRoot $name

    if (Test-Path $target) {
        Write-Host "[skip] $name already exists at $target"
        continue
    }

    Write-Host "[clone] $repo -> $target"
    git clone $repo $target
}

Write-Host "Done. Vendored Age Verification sources are in $VendorRoot"

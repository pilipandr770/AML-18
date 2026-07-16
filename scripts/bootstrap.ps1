param(
    [switch]$Reset
)

$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..")

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

# 1. Root .env: create from example, and fill in GIT_REVISION.
Write-Step ".env"
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "created .env from .env.example"
}

$gitRevision = (git rev-parse --short HEAD).Trim()
$envContent = Get-Content ".env" -Raw
if ($envContent -match "(?m)^GIT_REVISION=.*$") {
    $envContent = $envContent -replace "(?m)^GIT_REVISION=.*$", "GIT_REVISION=$gitRevision"
} else {
    $envContent += "`nGIT_REVISION=$gitRevision`n"
}
Set-Content -Path ".env" -Value $envContent -NoNewline

# 2. Envoy sandbox TLS certs. Generated once, then bind-mounted/reused --
# only regenerate if missing or -Reset was passed. Requires Git Bash + a
# local openssl on PATH (Windows: MSYS_NO_PATHCONV avoids MSYS mangling the
# -subj DN string into a Windows path; see patches/0003 for why -extfile is
# used instead of -copy_extensions, which needs OpenSSL 3.0+).
Write-Step "TLS sandbox certs"
$secretsExist = (Test-Path "envoy/.secret/server.pem.gz") -and
                (Test-Path "envoy/.secret/counterparty.pem.gz") -and
                (Test-Path "envoy/.secret/localhost.pem.gz")
if (-not $secretsExist -or $Reset) {
    Write-Host "generating..."
    Push-Location "envoy/.secret"
    try {
        $env:MSYS_NO_PATHCONV = "1"
        bash generate.sh
    } finally {
        Pop-Location
        Remove-Item Env:\MSYS_NO_PATHCONV -ErrorAction SilentlyContinue
    }
} else {
    Write-Host "already present, skipping (pass -Reset to regenerate)"
}

# 3. Build and start the whole stack.
Write-Step "docker compose build"
docker compose build

Write-Step "docker compose up -d"
docker compose up -d

Write-Host "waiting for services to settle..."
Start-Sleep -Seconds 10

# 4. Register both TRISA nodes with the local sandbox directory (gds.local).
# go run ./cmd/fsi gds:init opens the GDS leveldb store directly on disk, so
# gds.local must be stopped first (Windows file-locking is stricter than
# Linux about a bind-mounted file being open in two processes at once).
Write-Step "TRISA directory (gds:init)"
$gdsInitialized = Test-Path "envoy/tmp/gds/db"
if (-not $gdsInitialized -or $Reset) {
    docker compose stop gds.local
    Push-Location envoy
    try {
        if ($Reset) {
            go run ./cmd/fsi gds:init --reset
        } else {
            go run ./cmd/fsi gds:init
        }
    } finally {
        Pop-Location
    }
    docker compose start gds.local
    Start-Sleep -Seconds 3
    # envoy.local/counterparty.local cache the directory (6h sync interval)
    # -- force an immediate re-sync so the demo scripts see the new records
    # without waiting.
    docker compose restart envoy.local counterparty.local
    Start-Sleep -Seconds 8
} else {
    Write-Host "already initialized, skipping (pass -Reset to reinitialize)"
}

# 5. API keys for envoy.local / counterparty.local -- used by cmd/fsi and by
# examples/travel-rule-demo/send_transfer.py. Written straight to a
# gitignored file, never printed to the console.
Write-Step "API keys"
New-Item -ItemType Directory -Force -Path "envoy/tmp/creds" | Out-Null

$envoyKeyPath = "envoy/tmp/creds/envoy_local_apikey.txt"
if (-not (Test-Path $envoyKeyPath)) {
    docker compose exec -T envoy.local envoy createapikey all | Out-File -FilePath $envoyKeyPath -Encoding ascii
    Write-Host "created $envoyKeyPath"
} else {
    Write-Host "$envoyKeyPath already exists, skipping"
}

$counterpartyKeyPath = "envoy/tmp/creds/counterparty_local_apikey.txt"
if (-not (Test-Path $counterpartyKeyPath)) {
    docker compose exec -T counterparty.local envoy createapikey all | Out-File -FilePath $counterpartyKeyPath -Encoding ascii
    Write-Host "created $counterpartyKeyPath"
} else {
    Write-Host "$counterpartyKeyPath already exists, skipping"
}

# 6. Webhook HMAC key: envoy.local needs one to sign its webhook calls, and
# compliance.local needs the same one to verify them. Chicken-and-egg --
# doesn't exist until envoy.local has already been running once.
Write-Step "Webhook HMAC key"
$envContent = Get-Content ".env" -Raw
if ($envContent -notmatch "(?m)^WEBHOOK_AUTH_KEY_ID=\S") {
    $hmacOutput = docker compose exec -T envoy.local envoy hmackey
    $keyId = ($hmacOutput | Select-String "^Key ID: (.+)$").Matches[0].Groups[1].Value.Trim()
    $keySecret = ($hmacOutput | Select-String "^Key: (.+)$").Matches[0].Groups[1].Value.Trim()

    $envContent = $envContent -replace "(?m)^WEBHOOK_AUTH_KEY_ID=.*$", "WEBHOOK_AUTH_KEY_ID=$keyId"
    $envContent = $envContent -replace "(?m)^WEBHOOK_AUTH_KEY_SECRET=.*$", "WEBHOOK_AUTH_KEY_SECRET=$keySecret"
    Set-Content -Path ".env" -Value $envContent -NoNewline

    Write-Host "generated webhook HMAC key, restarting envoy.local + compliance.local to pick it up"
    docker compose up -d envoy.local compliance.local
    Start-Sleep -Seconds 5
} else {
    Write-Host "already configured in .env, skipping"
}

Write-Step "Done"
Write-Host "Compliance officer UI: http://localhost:8300/review/"
Write-Host "Demo: python examples/travel-rule-demo/send_transfer.py --clean"
Write-Host "      python examples/travel-rule-demo/send_transfer.py --flagged"

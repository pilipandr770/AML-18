param(
    [string]$SubjectReference = "user-live-option1",
    [string]$IssuedMdocPath = "tmp/ageverify-e2e/issued_mdoc.txt",
    [string]$ComplianceBaseUrl = "http://localhost:8300",
    [string]$VerifierBaseUrl = "http://localhost:8080",
    [int]$PollAttempts = 10,
    [int]$PollDelaySeconds = 1
)

$ErrorActionPreference = "Stop"

function Decode-JwtPayload([string]$Jwt) {
    $parts = $Jwt.Split('.')
    if ($parts.Length -lt 2) {
        throw "Invalid JWT request_value format"
    }

    $payload = $parts[1].Replace('-', '+').Replace('_', '/')
    switch ($payload.Length % 4) {
        2 { $payload += '==' }
        3 { $payload += '=' }
    }

    $json = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($payload))
    return $json | ConvertFrom-Json
}

function Ensure-Cbor2Installed([string]$PythonExe) {
    $checkCmd = "import cbor2; print('ok')"
    $result = & $PythonExe -c $checkCmd 2>$null
    if ($LASTEXITCODE -ne 0) {
        & $PythonExe -m pip install cbor2 | Out-Null
    }
}

function Build-DeviceResponseFromIssued([string]$PythonExe, [string]$IssuedPath, [string]$OutPath) {
    $py = @'
import base64
import sys
from pathlib import Path
import cbor2

issued_path = sys.argv[1]
out_path = sys.argv[2]

issued = Path(issued_path).read_text(encoding="utf-8-sig").strip().strip('"').strip()
pad = '=' * ((4 - len(issued) % 4) % 4)
raw = base64.urlsafe_b64decode(issued + pad)
issuer_signed = cbor2.loads(raw)

device_response = {
    "version": "1.0",
    "documents": [
        {
            "docType": "eu.europa.ec.av.1",
            "issuerSigned": issuer_signed,
        }
    ],
    "status": 0,
}

encoded = cbor2.dumps(device_response)
out = base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")
Path(out_path).write_text(out, encoding="ascii")
print(len(out))
'@

    $tmpPyPath = "tmp/ageverify-e2e/build_device_response_tmp.py"
    [System.IO.File]::WriteAllText($tmpPyPath, $py, (New-Object System.Text.UTF8Encoding($false)))

    & $PythonExe $tmpPyPath $IssuedPath $OutPath | Out-Null
    if (Test-Path $tmpPyPath) {
        Remove-Item $tmpPyPath -Force
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to build DeviceResponse from issued mdoc"
    }
}

Set-Location (Resolve-Path "$PSScriptRoot\..")

$pythonExe = ".\compliance-service\.venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Python venv not found at $pythonExe"
}

if (-not (Test-Path $IssuedMdocPath)) {
    throw "Issued mdoc file not found: $IssuedMdocPath"
}

Ensure-Cbor2Installed -PythonExe $pythonExe

$deviceResponsePath = "tmp/ageverify-e2e/device_response_from_issued.txt"
New-Item -ItemType Directory -Force -Path "tmp/ageverify-e2e" | Out-Null
Build-DeviceResponseFromIssued -PythonExe $pythonExe -IssuedPath $IssuedMdocPath -OutPath $deviceResponsePath

$enc = New-Object System.Text.UTF8Encoding($false)
$startPayload = [ordered]@{
    subject_reference = $SubjectReference
    adapter = "eu_oid4vp"
} | ConvertTo-Json -Compress

$startPayloadPath = "tmp/ageverify-e2e/start_session_auto.json"
[System.IO.File]::WriteAllText($startPayloadPath, $startPayload, $enc)

$startRaw = & curl.exe -sS -X POST -H "Content-Type: application/json" --data-binary "@$startPayloadPath" "$ComplianceBaseUrl/age-verify/sessions"
$start = $startRaw | ConvertFrom-Json
if (-not $start.session_id -or -not $start.request_value) {
    throw "Session start failed: $startRaw"
}

$sessionId = [string]$start.session_id
$requestPayload = Decode-JwtPayload -Jwt ([string]$start.request_value)
$state = [string]$requestPayload.state
if (-not $state) {
    throw "No state in request_value"
}

$deviceResponse = (Get-Content $deviceResponsePath -Raw).Trim()
$vpTokenPayload = (@{ proof_of_age = @($deviceResponse) } | ConvertTo-Json -Compress)
$vpTokenPath = "tmp/ageverify-e2e/vp_token_device_response_auto.json"
[System.IO.File]::WriteAllText($vpTokenPath, $vpTokenPayload, $enc)

$directPostUrl = "$VerifierBaseUrl/wallet/direct_post/$state"
$directPostResponse = & curl.exe -sS -X POST --data-urlencode "state=$state" --data-urlencode "vp_token@$vpTokenPath" "$directPostUrl"

$final = $null
for ($i = 1; $i -le $PollAttempts; $i++) {
    $pollRaw = & curl.exe -sS "$ComplianceBaseUrl/age-verify/sessions/$sessionId"
    $poll = $pollRaw | ConvertFrom-Json
    $final = $poll

    if ($poll.status -eq "verified" -and $poll.verified -eq $true) {
        break
    }

    Start-Sleep -Seconds $PollDelaySeconds
}

$result = [ordered]@{
    session_id = $sessionId
    direct_post_url = $directPostUrl
    direct_post_response = $directPostResponse
    final_status = $final.status
    verified = $final.verified
    verification_id = $final.verification_id
}

$result | ConvertTo-Json -Depth 5

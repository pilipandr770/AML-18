param(
    [string]$SubjectReference = "user-live-option1",
    [string]$IssuedMdocPath = "tmp/ageverify-e2e/issued_mdoc.txt",
    [string]$ComplianceBaseUrl = "http://localhost:8300",
    [string]$VerifierBaseUrl = "http://localhost:8080",
    [string]$IssuerBaseUrl = "https://backend.issuer.dev.ageverification.dev",
    [switch]$ReuseExistingMdoc,
    [int]$PollAttempts = 10,
    [int]$PollDelaySeconds = 1
)

$ErrorActionPreference = "Stop"

function ConvertFrom-JwtPayload([string]$Jwt) {
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

function Install-Cbor2Dependency([string]$PythonExe) {
    $checkCmd = "import cbor2; print('ok')"
    & $PythonExe -c $checkCmd 2>$null
    if ($LASTEXITCODE -ne 0) {
        & $PythonExe -m pip install cbor2 | Out-Null
    }
}

function Install-CryptographyDependency([string]$PythonExe) {
    $checkCmd = "import cryptography; print('ok')"
    & $PythonExe -c $checkCmd 2>$null
    if ($LASTEXITCODE -ne 0) {
        & $PythonExe -m pip install cryptography | Out-Null
    }
}

function New-FreshCredential([string]$PythonExe, [string]$IssuerBaseUrl, [string]$OutPath) {
    $py = @'
import base64
import json
import sys
import time
from pathlib import Path

import requests
from cryptography.hazmat.primitives.asymmetric import ec

requests.packages.urllib3.disable_warnings()

issuer_base = sys.argv[1].rstrip("/")
out_path = sys.argv[2]


def b64u(value):
    if isinstance(value, dict):
        value = json.dumps(value).encode("utf-8")
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


claims_payload = {
    "credentials": [
        {
            "credential_configuration_id": "eu.europa.ec.eudi.age_verification_mdoc",
            "data": {
                "age_over_18": True,
                "age_over_13": True,
                "age_over_15": True,
                "age_over_16": True,
                "age_over_21": True,
            },
        }
    ]
}
offer_request_jwt = f"{b64u({'alg': 'none', 'typ': 'JWT'})}.{b64u(claims_payload)}.sig"

resp = requests.post(
    f"{issuer_base}/credentialOfferReq2",
    data={"request": offer_request_jwt},
    verify=False,
    timeout=15,
)
resp.raise_for_status()
offer = resp.json()

grant = offer["grants"]["urn:ietf:params:oauth:grant-type:pre-authorized_code"]
preauth_code = grant["pre-authorized_code"]
tx_code = grant["tx_code"]["value"]

resp = requests.post(
    f"{issuer_base}/oidc/token",
    data={
        "grant_type": "urn:ietf:params:oauth:grant-type:pre-authorized_code",
        "pre-authorized_code": preauth_code,
        "tx_code": str(tx_code),
    },
    verify=False,
    timeout=15,
)
resp.raise_for_status()
access_token = resp.json()["access_token"]

private_key = ec.generate_private_key(ec.SECP256R1())
public_numbers = private_key.public_key().public_numbers()
x_bytes = public_numbers.x.to_bytes(32, "big")
y_bytes = public_numbers.y.to_bytes(32, "big")
jwk = {
    "kty": "EC",
    "crv": "P-256",
    "x": base64.urlsafe_b64encode(x_bytes).rstrip(b"=").decode("ascii"),
    "y": base64.urlsafe_b64encode(y_bytes).rstrip(b"=").decode("ascii"),
}
proof_header = {"typ": "openid4vci-proof+jwt", "alg": "ES256", "jwk": jwk}
proof_payload = {"aud": f"{issuer_base}/credential", "nonce": "test-nonce", "iat": int(time.time())}
proof_jwt = f"{b64u(proof_header)}.{b64u(proof_payload)}.sig"

resp = requests.post(
    f"{issuer_base}/credential",
    json={
        "credential_configuration_id": "eu.europa.ec.eudi.age_verification_mdoc",
        "proof": {"proof_type": "jwt", "jwt": proof_jwt},
    },
    headers={"Authorization": f"Bearer {access_token}"},
    verify=False,
    timeout=15,
)
resp.raise_for_status()
credential = resp.json()["credentials"][0]["credential"]

Path(out_path).parent.mkdir(parents=True, exist_ok=True)
Path(out_path).write_text(credential, encoding="ascii")
print(len(credential))
'@

    $tmpPyPath = "tmp/ageverify-e2e/issue_fresh_credential_tmp.py"
    [System.IO.File]::WriteAllText($tmpPyPath, $py, (New-Object System.Text.UTF8Encoding($false)))

    & $PythonExe $tmpPyPath $IssuerBaseUrl $OutPath | Out-Null
    if (Test-Path $tmpPyPath) {
        Remove-Item $tmpPyPath -Force
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to issue fresh AV credential from $IssuerBaseUrl"
    }
}

function New-DeviceResponseFromIssued([string]$PythonExe, [string]$IssuedPath, [string]$OutPath) {
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

New-Item -ItemType Directory -Force -Path "tmp/ageverify-e2e" | Out-Null

if ($ReuseExistingMdoc) {
    if (-not (Test-Path $IssuedMdocPath)) {
        throw "Issued mdoc file not found: $IssuedMdocPath"
    }
} else {
    Install-CryptographyDependency -PythonExe $pythonExe
    New-FreshCredential -PythonExe $pythonExe -IssuerBaseUrl $IssuerBaseUrl -OutPath $IssuedMdocPath
}

Install-Cbor2Dependency -PythonExe $pythonExe

$deviceResponsePath = "tmp/ageverify-e2e/device_response_from_issued.txt"
New-DeviceResponseFromIssued -PythonExe $pythonExe -IssuedPath $IssuedMdocPath -OutPath $deviceResponsePath

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
$requestPayload = ConvertFrom-JwtPayload -Jwt ([string]$start.request_value)
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

[ordered]@{
    session_id = $sessionId
    direct_post_url = $directPostUrl
    direct_post_response = $directPostResponse
    final_status = $final.status
    verified = $final.verified
    verification_id = $final.verification_id
} | ConvertTo-Json -Depth 5

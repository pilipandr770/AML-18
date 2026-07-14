"""HMAC authentication for the Envoy webhook, mirroring envoy's own
pkg/webhook/auth.go byte-for-byte so the two sides interoperate.

Signed-data construction: 16 random nonce bytes, followed by the raw
(un-normalized) values of each declared header, concatenated in the order
they were declared -- HMAC-SHA256 over that, base64 RawURLEncoding (no
padding). Authorization header shape:

    HMAC sig=<b64url>, nonce=<b64url>, headers=<h1>;<h2>, kid=<key_id>

Verification is fail-closed by design: a missing/malformed header, an
unconfigured key, or a signature mismatch all raise HMACError. There is no
"skip verification if the header is absent" path -- this endpoint has no
other authentication, so a silent pass-through here would be a real gap.
"""

import base64
import hashlib
import hmac
import os


class HMACError(Exception):
    """Raised whenever an incoming or outgoing HMAC token fails to parse,
    fails to verify, or the service isn't configured to check it."""


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


class HMACToken:
    """A parsed Authorization/Server-Authorization header value, ready to be
    completed with header values and verified against a shared secret."""

    def __init__(self, signature: bytes, nonce: bytes, headers: list, key_id: str):
        self.signature = signature
        self.data = bytearray(nonce)
        self.headers = headers
        self.key_id = key_id

    @classmethod
    def parse(cls, token: str) -> "HMACToken":
        if not token or not token.startswith("HMAC "):
            raise HMACError("missing or malformed HMAC authorization header")

        token = token[len("HMAC "):]
        kv = {}
        for part in token.split(","):
            if "=" not in part:
                raise HMACError("malformed HMAC authorization header")
            key, value = part.split("=", 1)
            kv[key.strip()] = value.strip()

        for required in ("sig", "nonce", "headers", "kid"):
            if required not in kv or not kv[required]:
                raise HMACError(f"missing {required} in HMAC token")

        try:
            signature = _b64url_decode(kv["sig"])
            nonce = _b64url_decode(kv["nonce"])
        except Exception as exc:
            raise HMACError(f"could not decode HMAC token: {exc}") from exc

        headers = [h.strip() for h in kv["headers"].split(";") if h.strip()]
        if not headers:
            raise HMACError("could not decode headers in HMAC token")

        return cls(signature=signature, nonce=nonce, headers=headers, key_id=kv["kid"])

    def collect(self, get_header):
        """get_header(name) -> str | None, a case-insensitive header lookup
        (e.g. flask.Request.headers.get). Appends each declared header's raw
        value, in the token's declared order, to the signed data."""
        for header in self.headers:
            value = get_header(header)
            if value:
                self.data += value.encode("utf-8")

    def verify(self, key: bytes) -> bool:
        mac = hmac.new(key, bytes(self.data), hashlib.sha256).digest()
        return hmac.compare_digest(mac, self.signature)


def verify_request(auth_header: str, get_header, key_id: str, key: bytes) -> None:
    """Verify an incoming webhook call's Authorization header. Raises
    HMACError on any failure -- callers must treat that as a hard 401."""
    if not key_id or not key:
        raise HMACError("webhook auth is not configured on this service")

    token = HMACToken.parse(auth_header or "")

    if not hmac.compare_digest(token.key_id, key_id):
        raise HMACError("unknown HMAC key ID")

    token.collect(get_header)

    if not token.verify(key):
        raise HMACError("invalid HMAC signature")


class HMACSigner:
    """Builds an outgoing Authorization/Server-Authorization header value,
    mirroring envoy's webhook.NewHMAC / Append / Authorization exactly."""

    def __init__(self, key_id: str, key: bytes):
        self.key_id = key_id
        self.key = key
        self.nonce = os.urandom(16)
        self.data = bytearray(self.nonce)
        self.header_names = []

    def append(self, header: str, value: str) -> None:
        header = header.lower()
        if header in self.header_names:
            return
        self.header_names.append(header)
        self.data += value.encode("utf-8")

    def authorization(self) -> str:
        signature = hmac.new(self.key, bytes(self.data), hashlib.sha256).digest()
        sig_b64 = _b64url_encode(signature)
        nonce_b64 = _b64url_encode(self.nonce)
        headers_joined = ";".join(self.header_names)
        return f"HMAC sig={sig_b64}, nonce={nonce_b64}, headers={headers_joined}, kid={self.key_id}"

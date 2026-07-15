import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4
from urllib.parse import urljoin

import requests


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_proof_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AdapterError(Exception):
    pass


class AdapterNotConfiguredError(AdapterError):
    pass


@dataclass
class VerificationResult:
    verified: bool
    method: str
    verified_at: datetime | None
    expires_at: datetime | None = None


@dataclass
class SessionStartResult:
    transaction_id: str
    request_value: str | None


@dataclass
class SessionPollResult:
    status: str
    verified: bool | None = None
    method: str | None = None
    proof_token_hash: str | None = None
    error: str | None = None


class BaseAgeVerifier:
    name = "base"
    supports_sessions = False

    def verify(self, proof_token: str, min_age: int) -> VerificationResult:
        raise NotImplementedError

    def start_session(self, min_age: int) -> SessionStartResult:
        raise AdapterError(f"adapter {self.name} does not support interactive sessions")

    def get_session_result(self, transaction_id: str, min_age: int) -> SessionPollResult:
        raise AdapterError(f"adapter {self.name} does not support interactive sessions")


class MockAgeVerifier(BaseAgeVerifier):
    """Deterministic local adapter for tests and demos.

    Accepted token values:
      - "mock:over18"  -> verified=true
      - "mock:under18" -> verified=false
    """

    name = "mock"

    def verify(self, proof_token: str, min_age: int) -> VerificationResult:
        normalized = (proof_token or "").strip().lower()
        if normalized == "mock:over18":
            return VerificationResult(
                verified=True,
                method=f"mock_age_over_{min_age}",
                verified_at=_utcnow(),
            )
        if normalized == "mock:under18":
            return VerificationResult(
                verified=False,
                method=f"mock_age_under_{min_age}",
                verified_at=None,
            )
        raise AdapterError("invalid mock proof token")


class EUID4VPAgeVerifier(BaseAgeVerifier):
    """Stub for the EU privacy-preserving age verification flow.

    The target integration is OID4VP-based and should consume a
    cryptographic over-age proof, returning only the age claim outcome.
    """

    name = "eu_oid4vp"
    supports_sessions = True

    def __init__(self, base_url: str, timeout_seconds: float):
        self.base_url = (base_url or "").strip()
        self.timeout_seconds = timeout_seconds
        self.presentation_path = "/ui/presentations"
        self.device_response_validation_path = "/utilities/validations/msoMdoc/deviceResponse"

    def verify(self, proof_token: str, min_age: int) -> VerificationResult:
        raise AdapterError("eu_oid4vp requires session-based verification flow")

    def start_session(self, min_age: int) -> SessionStartResult:
        self._ensure_configured()
        endpoint = self._url(self.presentation_path)
        payload = {
            "type": "vp_token",
            "dcql_query": {
                "credentials": [
                    {
                        "id": "proof_of_age",
                        "format": "mso_mdoc",
                        "meta": {"doctype_value": "eu.europa.ec.av.1"},
                        "claims": [{"path": ["eu.europa.ec.av.1", f"age_over_{min_age}"]}],
                    }
                ]
            },
            "nonce": str(uuid4()),
        }
        try:
            response = requests.post(endpoint, json=payload, timeout=self.timeout_seconds)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise AdapterError(f"eu_oid4vp presentation init failed: {exc}") from exc
        except ValueError as exc:
            raise AdapterError("eu_oid4vp init returned non-json response") from exc

        transaction_id = data.get("transaction_id")
        request_value = data.get("request_uri") or data.get("request")
        if not transaction_id:
            raise AdapterError("eu_oid4vp init response missing transaction_id")
        return SessionStartResult(transaction_id=transaction_id, request_value=request_value)

    def get_session_result(self, transaction_id: str, min_age: int) -> SessionPollResult:
        self._ensure_configured()
        presentation_url = self._url(f"{self.presentation_path}/{transaction_id}")

        try:
            response = requests.get(presentation_url, timeout=self.timeout_seconds)
        except requests.RequestException as exc:
            raise AdapterError(f"eu_oid4vp presentation poll failed: {exc}") from exc

        if response.status_code == 400:
            try:
                error_data = response.json()
            except ValueError:
                error_data = None
            if error_data is None:
                return SessionPollResult(status="pending")
            cause = str(error_data.get("cause") or error_data.get("message") or "")
            if "Submitted state" in cause or "RequestObjectRetrieved" in cause:
                return SessionPollResult(status="pending")
            raise AdapterError(f"eu_oid4vp poll returned 400: {cause or response.text}")

        if response.status_code == 404:
            raise AdapterError("eu_oid4vp transaction not found")

        try:
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise AdapterError(f"eu_oid4vp poll failed: {exc}") from exc
        except ValueError as exc:
            raise AdapterError("eu_oid4vp poll returned non-json response") from exc

        proof_of_age = (((data or {}).get("vp_token") or {}).get("proof_of_age"))
        if not proof_of_age:
            return SessionPollResult(status="pending")

        if isinstance(proof_of_age, list):
            if len(proof_of_age) != 1 or not isinstance(proof_of_age[0], str):
                raise AdapterError("eu_oid4vp proof_of_age has unsupported array shape")
            proof_of_age = proof_of_age[0]

        if not isinstance(proof_of_age, str):
            raise AdapterError("eu_oid4vp proof_of_age is not a string")

        validated_documents = self._validate_device_response(proof_of_age)
        age_key = f"age_over_{min_age}"
        verified = self._extract_verified(validated_documents, age_key)
        return SessionPollResult(
            status="complete",
            verified=verified,
            method="eu_oid4vp_mso_mdoc",
            proof_token_hash=hash_proof_token(proof_of_age),
        )

    def _ensure_configured(self) -> None:
        if not self.base_url:
            raise AdapterNotConfiguredError("eu_oid4vp adapter is not configured yet")

    def _url(self, path: str) -> str:
        return urljoin(self.base_url.rstrip("/") + "/", path.lstrip("/"))

    def _validate_device_response(self, proof_of_age: str) -> list:
        endpoint = self._url(self.device_response_validation_path)
        try:
            response = requests.post(
                endpoint,
                data={"device_response": proof_of_age},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            detail = self._describe_http_error(exc.response)
            raise AdapterError(f"eu_oid4vp device response validation failed: {detail}") from exc
        except requests.RequestException as exc:
            raise AdapterError(f"eu_oid4vp device response validation failed: {exc}") from exc
        except ValueError as exc:
            raise AdapterError("eu_oid4vp validation returned non-json response") from exc

    @staticmethod
    def _describe_http_error(response) -> str:
        if response is None:
            return "unknown http error"

        try:
            payload = response.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict):
            error_type = payload.get("type")
            invalid_documents = payload.get("invalidDocuments")
            if isinstance(invalid_documents, list) and invalid_documents:
                first = invalid_documents[0] or {}
                errors = first.get("errors") or []
                if isinstance(errors, list) and errors:
                    return f"{error_type or 'validation_error'}: {', '.join(str(item) for item in errors)}"
            if error_type:
                return str(error_type)
            message = payload.get("message") or payload.get("error")
            if message:
                return str(message)

        body = getattr(response, "text", "") or ""
        if body:
            return body

        return f"HTTP {response.status_code}"

    @staticmethod
    def _extract_verified(validated_documents: list, age_key: str) -> bool:
        if not validated_documents:
            raise AdapterError("eu_oid4vp validation returned no documents")

        first = validated_documents[0]
        namespace = ((first.get("attributes") or {}).get("eu.europa.ec.av.1") or {})
        verified = namespace.get(age_key)
        if not isinstance(verified, bool):
            raise AdapterError(f"eu_oid4vp validation missing boolean claim {age_key}")
        return verified


def get_adapter(name: str, config=None) -> BaseAgeVerifier:
    registry = {
        "mock": MockAgeVerifier,
    }

    if name == "eu_oid4vp":
        config = config or {}
        return EUID4VPAgeVerifier(
            base_url=config.get("AGEVERIFY_EU_VERIFIER_BASE_URL", ""),
            timeout_seconds=float(config.get("AGEVERIFY_EU_VERIFIER_TIMEOUT_SECONDS", 5.0)),
        )

    adapter_cls = registry.get(name)
    if adapter_cls is None:
        raise AdapterError(f"unknown adapter: {name}")
    return adapter_cls()
import base64
import json
from urllib.parse import quote


class PresentationError(Exception):
    pass


def request_value_to_av_uri(request_value: str) -> str:
    if not request_value:
        raise PresentationError("missing request value")

    parts = request_value.split(".")
    if len(parts) != 3:
        raise PresentationError("request value is not a signed JWT")

    payload = _decode_payload(parts[1])
    required = ("response_type", "response_uri", "dcql_query", "nonce", "state")
    missing = [key for key in required if key not in payload]
    if missing:
        raise PresentationError(f"request value is missing fields: {', '.join(missing)}")

    response_uri = str(payload["response_uri"])
    return (
        "av://?"
        + "response_type=" + quote(str(payload["response_type"]), safe="")
        + "&response_mode=" + quote(str(payload.get("response_mode", "direct_post")), safe="")
        + "&client_id=" + quote("redirect_uri:" + response_uri, safe="")
        + "&response_uri=" + quote(response_uri, safe="")
        + "&dcql_query=" + quote(json.dumps(payload["dcql_query"], separators=(",", ":")), safe="")
        + "&nonce=" + quote(str(payload["nonce"]), safe="")
        + "&state=" + quote(str(payload["state"]), safe="")
    )


def _decode_payload(value: str) -> dict:
    padding = "=" * (-len(value) % 4)
    try:
        decoded = base64.urlsafe_b64decode(value + padding)
        return json.loads(decoded.decode("utf-8"))
    except Exception as exc:
        raise PresentationError(f"could not decode request payload: {exc}") from exc
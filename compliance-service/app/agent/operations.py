"""Operation execution boundary. An 'operation' is a signed instruction to
the CLIENT's system (release / hold / reject a transfer, confirm or reject
wallet ownership, close a simple review case). The agent never holds keys
and never moves funds itself. Executors are only ever called by the runner
after the policy engine returned EXECUTE."""


class OperationError(Exception):
    pass


class RecordingExecutor:
    """Records instructions instead of sending them (tests, MONITOR demo)."""

    def __init__(self):
        self.executed: list[dict] = []

    def execute(self, operation: str, case, project) -> dict:
        record = {"operation": operation, "case": case.public_id, "project": project.public_id}
        self.executed.append(record)
        return {"delivered": True, "mode": "recorded"}


class WebhookExecutor:
    """Sends the instruction to the client's own system as a signed JSON
    webhook. Signature: header X-AML18-Signature: t=<unix>,v1=<hex hmac-sha256
    of "<t>.<body>"> using the per-project secret shown once to the owner.
    Idempotency-Key = case id + operation, so retries are safe to replay."""

    def __init__(self, timeout_seconds: float = 5.0, attempts: int = 3):
        self.timeout = timeout_seconds
        self.attempts = attempts

    def execute(self, operation: str, case, project) -> dict:
        import hashlib
        import hmac
        import json
        import time

        import requests

        from app.agent.settings import get_settings_row

        url = (project.webhook_url or "").strip()
        secret = get_settings_row(project.id).webhook_secret
        if not url or not secret:
            raise OperationError("project has no webhook_url or signing secret configured")

        body = json.dumps({
            "operation": operation, "case_id": case.public_id, "external_ref": case.external_ref,
            "tx_hash": case.tx_hash, "amount": str(case.amount), "asset": case.asset, "chain": case.chain,
        }, sort_keys=True, separators=(",", ":"))
        ts = str(int(time.time()))
        sig = hmac.new(secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest()
        headers = {
            "Content-Type": "application/json", "X-AML18-Signature": f"t={ts},v1={sig}",
            "Idempotency-Key": f"{case.public_id}:{operation}",
        }
        last = None
        for attempt in range(self.attempts):
            try:
                r = requests.post(url, data=body, headers=headers, timeout=self.timeout)
                if r.status_code < 300:
                    return {"delivered": True, "status": r.status_code, "attempt": attempt + 1}
                last = f"HTTP {r.status_code}"
            except requests.RequestException as exc:
                last = type(exc).__name__
            time.sleep(0.5 * (attempt + 1))
        raise OperationError(f"delivery failed after {self.attempts} attempts: {last}")

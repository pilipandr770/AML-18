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

"""Read access to a project's agent mode/policy for the runner. Writes live
in owner routes only (authenticated); nothing here is reachable from a tool."""

from pydantic import ValidationError

from app.agent.models import MODE_MONITOR, AgentSettings
from app.agent.policy import Policy
from app.extensions import db


def get_settings_row(project_id: int) -> AgentSettings:
    row = AgentSettings.query.filter_by(developer_project_id=project_id).first()
    if row is None:
        row = AgentSettings(developer_project_id=project_id, mode=MODE_MONITOR, policy={}, kill_switch=False)
        db.session.add(row)
        db.session.commit()
    return row


def load_effective(project_id: int) -> tuple[str, Policy, bool]:
    """Returns (mode, policy, kill_switch). An unparseable stored policy
    degrades to the empty policy, which denies every operation."""
    row = get_settings_row(project_id)
    try:
        policy = Policy.model_validate(row.policy or {})
    except ValidationError:
        policy = Policy()
    return row.mode, policy, bool(row.kill_switch)

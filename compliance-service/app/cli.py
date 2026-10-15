import click


@click.command("sanctions-ingest")
def sanctions_ingest_command():
    """Fetch and reload all registered sanctions sources (OFAC SDN, EU FSF)."""
    from app.sanctions.ingest import ingest_all

    snapshots = ingest_all()
    for snapshot in snapshots:
        click.echo(f"{snapshot.source}: {snapshot.record_count} records, status={snapshot.status}")


@click.command("agent-monitor")
@click.option("--once", is_flag=True, help="Scan once and exit instead of looping.")
@click.option("--interval", default=15, show_default=True, help="Seconds between scans.")
def agent_monitor_command(once, interval):
    """Watch registered deposit addresses (EVM testnet) and run the agent on new deposits."""
    import time

    from flask import current_app

    from app.agent.chain import EvmRpcLedger
    from app.agent.factory import get_runtime
    from app.agent.models import DepositAddress
    from app.agent.monitor import scan_address
    from app.agent.runner import process_case
    from app.developer_portal.models import DeveloperProject
    from app.extensions import db

    if not current_app.config["AGENT_ENABLED"]:
        raise click.ClickException("AGENT_ENABLED is false")
    rt = get_runtime(current_app)
    rpc = EvmRpcLedger(
        current_app.config["AGENT_EVM_RPC_URL"], timeout_seconds=current_app.config["AGENT_EVM_RPC_TIMEOUT_SECONDS"]
    )._rpc
    while True:
        for dep in DepositAddress.query.all():
            project = db.session.get(DeveloperProject, dep.developer_project_id)
            try:
                cases = scan_address(rpc, dep)
            except Exception as exc:
                click.echo(f"scan failed for {dep.address}: {type(exc).__name__}")
                db.session.rollback()
                continue
            for case in cases:
                process_case(case, project, current_app.config, rt.llm, rt.ledger, rt.executor)
                click.echo(f"case {case.public_id}: {case.status}")
        if once:
            return
        time.sleep(interval)


@click.command("platform-create-operator")
@click.option("--email", prompt=True)
@click.password_option(envvar="AML18_OPERATOR_PASSWORD")
def platform_create_operator_command(email, password):
    """Create a platform operator (super-admin) account and print its authenticator secret once."""
    import pyotp
    from werkzeug.security import generate_password_hash

    from app.extensions import db
    from app.platform_admin.models import PlatformOperator

    email = email.strip().lower()
    if len(password) < 12:
        raise click.ClickException("password must be at least 12 characters")
    if PlatformOperator.query.filter_by(email=email).first():
        raise click.ClickException("operator already exists")
    secret = pyotp.random_base32()
    db.session.add(PlatformOperator(email=email, password_hash=generate_password_hash(password), totp_secret=secret))
    db.session.commit()
    click.echo(f"Operator created: {email}")
    click.echo(f"Authenticator secret (shown once, add to a TOTP app): {secret}")
    click.echo(pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="AML+18 Platform"))


def register_cli(app):
    app.cli.add_command(sanctions_ingest_command)
    app.cli.add_command(agent_monitor_command)
    app.cli.add_command(platform_create_operator_command)

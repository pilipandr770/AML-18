import click

from app.extensions import db


@click.command("init-db")
def init_db_command():
    """Create all tables. A placeholder for proper Alembic migrations,
    sufficient for Phase 0/1 while the schema is still moving fast."""
    db.create_all()
    click.echo("database tables created")


@click.command("sanctions-ingest")
def sanctions_ingest_command():
    """Fetch and reload all registered sanctions sources (OFAC SDN, EU FSF)."""
    from app.sanctions.ingest import ingest_all

    snapshots = ingest_all()
    for snapshot in snapshots:
        click.echo(f"{snapshot.source}: {snapshot.record_count} records, status={snapshot.status}")


def register_cli(app):
    app.cli.add_command(init_db_command)
    app.cli.add_command(sanctions_ingest_command)

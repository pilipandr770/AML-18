import click


@click.command("sanctions-ingest")
def sanctions_ingest_command():
    """Fetch and reload all registered sanctions sources (OFAC SDN, EU FSF)."""
    from app.sanctions.ingest import ingest_all

    snapshots = ingest_all()
    for snapshot in snapshots:
        click.echo(f"{snapshot.source}: {snapshot.record_count} records, status={snapshot.status}")


def register_cli(app):
    app.cli.add_command(sanctions_ingest_command)

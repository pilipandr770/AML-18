#!/bin/sh
# Sidecar entrypoint for the `sanctions-cron` service in the root
# docker-compose.yml. Runs `flask sanctions-ingest` on a fixed interval so a
# fresh clone stays screening against a current list without the user
# having to wire up host crontab themselves. Migrations are owned by
# compliance.local's own entrypoint.sh, not this one -- depends_on ensures
# that container has already started before this loop's first iteration.
set -e

interval="${SANCTIONS_CRON_INTERVAL_SECONDS:-86400}"

echo "sanctions-cron: refreshing every ${interval}s"

while true; do
    echo "sanctions-cron: $(date -u +%Y-%m-%dT%H:%M:%SZ) running flask sanctions-ingest"
    flask sanctions-ingest || echo "sanctions-cron: ingest failed, will retry next interval"
    sleep "$interval"
done

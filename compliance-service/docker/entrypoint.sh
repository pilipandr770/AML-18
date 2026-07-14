#!/bin/sh
set -e

flask init-db

exec gunicorn --bind 0.0.0.0:8300 --workers 2 --timeout 25 wsgi:app

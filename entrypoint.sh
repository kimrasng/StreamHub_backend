#!/bin/sh
set -e

if [ -n "$DB_PATH" ]; then
  DB_DIR=$(dirname "$DB_PATH")
  mkdir -p "$DB_DIR"
fi

python manage.py migrate --noinput

exec daphne -b 0.0.0.0 -p 8000 stream_hub.asgi:application

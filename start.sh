#!/usr/bin/env bash
# Render start command: prepare the database, then start the web server.
set -o errexit

python manage.py migrate --noinput
python manage.py seed_maldives --if-empty ${SEED_DEMO:+--demo}
python manage.py ensure_admin

# Link photos from Wikimedia Commons to islands and experiences that don't have one yet.
# Runs in the background so the site starts immediately; output appears in the Render logs.
if [ "${FETCH_PHOTOS:-1}" = "1" ]; then
  python manage.py fetch_island_photos &
fi

exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers "${WEB_CONCURRENCY:-2}" --timeout 60

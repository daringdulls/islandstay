#!/usr/bin/env bash
# Render start command: prepare the database, then start the web server.
set -o errexit

python manage.py migrate --noinput
python manage.py seed_maldives --if-empty ${SEED_DEMO:+--demo}
python manage.py ensure_admin

# Island cover photos from Wikimedia Commons. Runs in the background so the site starts immediately;
# only islands without a photo are fetched.
if [ "${FETCH_PHOTOS:-1}" = "1" ]; then
  python manage.py fetch_island_photos > /tmp/fetch_photos.log 2>&1 &
fi

exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers "${WEB_CONCURRENCY:-2}" --timeout 60

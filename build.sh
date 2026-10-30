#!/usr/bin/env bash
# Render build command.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput

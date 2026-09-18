#!/usr/bin/env bash
# exit on error
set -o errexit

chmod +x start.sh build.sh || true

pip install -r requirements.txt

python manage.py collectstatic --no-input


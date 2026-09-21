#!/usr/bin/env bash
set -euo pipefail

if [[ "$(python --version 2>&1)" != "Python 3.11.2" ]]; then
  echo "Expected Python 3.11.2. Current: $(python --version 2>&1)" >&2
  exit 1
fi
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python django_app/manage.py migrate
echo "Ready. Create an admin with: python django_app/manage.py createsuperuser"

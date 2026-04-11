#!/bin/bash
set -e
python manage.py collectstatic --noinput
python manage.py migrate --noinput
exec gunicorn expense_month.wsgi:application -c gunicorn.conf.py

#!/bin/bash
set -e

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

python manage.py collectstatic --noinput
python manage.py migrate --noinput
exec gunicorn expense_month.wsgi:application -c gunicorn.conf.py

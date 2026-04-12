#!/bin/bash

STATE_FILE="/home/sami/expense-tracker/backups/.monitor_state"
CONTAINER="expense-tracker-web"

mkdir -p "$(dirname "$STATE_FILE")"

STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null || echo "missing")

if [ "$STATUS" = "healthy" ]; then
    rm -f "$STATE_FILE"
    exit 0
fi

# Avoid duplicate alerts — only alert on state changes
if [ -f "$STATE_FILE" ]; then
    LAST=$(cat "$STATE_FILE")
    if [ "$LAST" = "$STATUS" ]; then
        exit 0
    fi
fi

echo "$STATUS" > "$STATE_FILE"

# Export .env vars so Python subprocess can read them
set -a
source /home/sami/expense-tracker/.env
set +a

python3 /home/sami/expense-tracker/deploy/send_email.py \
    --subject "⚠ Expense Tracker DOWN — status: ${STATUS}" \
    --body "Container '${CONTAINER}' is ${STATUS} at $(date). Docker will attempt auto-restart."

# Attempt restart if container is stopped or missing
if [ "$STATUS" = "exited" ] || [ "$STATUS" = "missing" ]; then
    cd /home/sami/expense-tracker
    docker compose -f docker-compose.prod.yml up -d
fi

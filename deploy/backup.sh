#!/bin/bash
set -e

BACKUP_DIR="/home/sami/expense-tracker/backups"
CONTAINER="expense-tracker-web"
DATA_DIR="/home/sami/expense-tracker/data"
LABEL="${1:-daily}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="expense_${LABEL}_${TIMESTAMP}.db"

mkdir -p "$BACKUP_DIR"

# Safe SQLite backup via container (sqlite3 guaranteed inside image)
docker exec "$CONTAINER" sqlite3 /app/data/db.sqlite3 ".backup '/app/data/${BACKUP_FILE}'"

mv "${DATA_DIR}/${BACKUP_FILE}" "${BACKUP_DIR}/${BACKUP_FILE}"
gzip "${BACKUP_DIR}/${BACKUP_FILE}"

# Export .env vars so Python subprocess can read them
set -a
source /home/sami/expense-tracker/.env
set +a

python3 /home/sami/expense-tracker/deploy/send_email.py \
  --subject "Expense Tracker Backup (${LABEL}) - ${TIMESTAMP}" \
  --body "SQLite backup attached. Label: ${LABEL}" \
  --attachment "${BACKUP_DIR}/${BACKUP_FILE}.gz"

# Retain only last 7 local backups
cd "$BACKUP_DIR"
ls -tp *.gz 2>/dev/null | tail -n +8 | xargs -I {} rm -- {}

echo "Backup complete: ${BACKUP_DIR}/${BACKUP_FILE}.gz"

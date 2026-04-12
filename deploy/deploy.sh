#!/bin/bash
set -e

IMAGE=${1:-ghcr.io/xsyed/expense-tracker:latest}
cd /home/sami/expense-tracker

[ -f ./deploy/backup.sh ] && ./deploy/backup.sh "manual-deploy" || echo "Skipping pre-deploy backup (backup.sh not found, implement Phase 5)"
docker pull "$IMAGE"
docker compose -f docker-compose.prod.yml up -d
sleep 15
curl -sf http://localhost:8000/health/
rm -rf ./deploy
docker cp expense-tracker-web:/app/deploy ./deploy
chmod +x ./deploy/*.sh
mkdir -p backups
echo "Deploy successful!"

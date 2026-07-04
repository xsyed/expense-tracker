#!/bin/bash
set -e

IMAGE=${1:-ghcr.io/xsyed/expense-tracker:latest}
RELEASE_CONTAINER="expense-tracker-release"
cd /home/sami/expense-tracker

cleanup_release_container() {
    docker rm -f "$RELEASE_CONTAINER" >/dev/null 2>&1 || true
}

trap cleanup_release_container EXIT

[ -f ./deploy/backup.sh ] && ./deploy/backup.sh "manual-deploy" || echo "Skipping pre-deploy backup (backup.sh not found, implement Phase 5)"
docker pull "$IMAGE"
cleanup_release_container
docker create --name "$RELEASE_CONTAINER" "$IMAGE" >/dev/null
docker cp "$RELEASE_CONTAINER":/app/docker-compose.prod.yml ./docker-compose.prod.yml
rm -rf ./deploy
docker cp "$RELEASE_CONTAINER":/app/deploy ./deploy
chmod +x ./deploy/*.sh
docker compose -f docker-compose.prod.yml up -d
sleep 15
curl -sf http://localhost:8000/health/
docker inspect --format='{{.State.Running}}' expense-tracker-advisor-worker | grep -q true
mkdir -p backups
echo "Deploy successful!"

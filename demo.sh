#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo " Ephemeral Machines Platform - 1-Command Demo Runner"
echo "=========================================================="

echo "[1/4] Starting Docker services (Postgres & Traefik)..."
docker compose up -d

echo "[2/4] Applying migrations and seeding database..."
source api/.venv/bin/activate || source api/.venv/Scripts/activate
alembic -c api/alembic.ini upgrade head || python -m alembic -C api upgrade head
python api/seed.py

echo "[3/4] Running automated smoke tests..."
pytest api/tests/ -q

echo "[4/4] Services ready!"
echo "To start services:"
echo "  Terminal 1: cd api && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
echo "  Terminal 2: cd scheduler && python -m app.main"
echo ""
echo "Interactive Swagger docs: http://localhost:8000/docs"
echo "Traefik Dashboard:        http://localhost:8080/dashboard/"

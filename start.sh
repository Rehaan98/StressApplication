#!/usr/bin/env bash
# ============================================================
# Psychological Stress AI — Local Development Startup Script
# ============================================================
# Usage:
#   chmod +x start.sh
#   ./start.sh            # starts both backend and frontend
#   ./start.sh backend    # backend only (dev, hot-reload)
#   ./start.sh frontend   # frontend only
#   ./start.sh train      # train the ML model
#   ./start.sh seed       # seed the SQLite database
#   ./start.sh facial     # verify/download facial recognition artifacts
#   ./start.sh backend-prod  # backend with N workers (STRESSAI_WORKERS, default 4) — large-scale serving
# ============================================================

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT_DIR/venv"
FRONTEND="$ROOT_DIR/frontend"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${CYAN}[StressAI]${NC} $1"; }
ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ── Python virtual environment ────────────────────────────────────────────────
setup_python() {
  if [ ! -d "$VENV" ]; then
    log "Creating Python virtual environment..."
    python3 -m venv "$VENV"
  fi
  source "$VENV/bin/activate"
  log "Installing Python dependencies..."
  pip install -q --upgrade pip
  pip install -q -r "$ROOT_DIR/backend/requirements.txt"
  ok "Python environment ready."
}

# ── ML model training ─────────────────────────────────────────────────────────
train_model() {
  source "$VENV/bin/activate"
  log "Training ML model pipeline..."
  cd "$ROOT_DIR"
  PYTHONPATH="$ROOT_DIR" python -m ml_engine.src.train_pipeline
  ok "ML model trained and artifacts saved to ml_engine/models/"
}

# ── Database seed ─────────────────────────────────────────────────────────────
seed_db() {
  source "$VENV/bin/activate"
  log "Seeding SQLite database..."
  cd "$ROOT_DIR"
  PYTHONPATH="$ROOT_DIR" python database/seed_data.py
  ok "Database seeded."
}

# ── Facial recognition artifacts ───────────────────────────────────────────────
setup_facial() {
  source "$VENV/bin/activate"
  log "Ensuring facial expression recognition artifacts..."
  cd "$ROOT_DIR"
  PYTHONPATH="$ROOT_DIR" python -c "
from ml_engine.facial.fer_detector import FacialStressAnalyzer
a = FacialStressAnalyzer(download_if_missing=True)
print('  CNN model:', 'ferplus-fer2013' if a.is_cnn else 'MISSING — heuristic mode')
print('  Face cascade:', 'OK' if a.face_cascade is not None else 'MISSING')
"
  ok "Facial recognition ready."
}

# ── Backend server ────────────────────────────────────────────────────────────
start_backend() {
  source "$VENV/bin/activate"
  log "Starting FastAPI backend on http://localhost:8000 ..."
  log "  API docs: http://localhost:8000/docs"
  cd "$ROOT_DIR"
  PYTHONPATH="$ROOT_DIR" uvicorn backend.app.main:app \
    --host 0.0.0.0 --port 8000 --reload \
    --env-file "$ROOT_DIR/.env"
}

# ── Backend server (production / large scale) ─────────────────────────────────
start_backend_prod() {
  source "$VENV/bin/activate"
  WORKERS="${STRESSAI_WORKERS:-4}"
  log "Starting FastAPI backend (production) with $WORKERS workers on http://localhost:8000 ..."
  log "  Scale horizontally: STRESSAI_WORKERS=<n> ./start.sh backend-prod"
  cd "$ROOT_DIR"
  PYTHONPATH="$ROOT_DIR" uvicorn backend.app.main:app \
    --host 0.0.0.0 --port 8000 --workers "$WORKERS" \
    --env-file "$ROOT_DIR/.env"
}

# ── Frontend server ───────────────────────────────────────────────────────────
start_frontend() {
  if [ ! -d "$FRONTEND/node_modules" ]; then
    log "Installing Node.js dependencies..."
    cd "$FRONTEND" && npm install
  fi
  log "Starting Next.js frontend on http://localhost:3000 ..."
  cd "$FRONTEND"
  npm run dev
}

# ── Main dispatch ─────────────────────────────────────────────────────────────
CMD="${1:-all}"

case "$CMD" in
  backend)
    setup_python
    # Seed db if it doesn't exist yet
    [ ! -f "$ROOT_DIR/stress_ai.db" ] && seed_db
    setup_facial
    start_backend
    ;;
  backend-prod)
    setup_python
    [ ! -f "$ROOT_DIR/stress_ai.db" ] && seed_db
    setup_facial
    start_backend_prod
    ;;
  facial)
    setup_python
    setup_facial
    ;;
  frontend)
    start_frontend
    ;;
  train)
    setup_python
    train_model
    ;;
  seed)
    setup_python
    seed_db
    ;;
  all)
    setup_python
    # Seed db if it doesn't exist
    [ ! -f "$ROOT_DIR/stress_ai.db" ] && seed_db
    setup_facial
    log "Starting backend in background..."
    (start_backend &)
    BACKEND_PID=$!
    sleep 3
    log "Starting frontend..."
    start_frontend
    # When frontend exits, kill backend
    kill $BACKEND_PID 2>/dev/null || true
    ;;
  *)
    echo "Usage: $0 [all|backend|backend-prod|frontend|train|seed|facial]"
    exit 1
    ;;
esac

# KG Coach Dashboard — one-command dev setup
# Requires: uv (Python), node + npm (Frontend)

.PHONY: dev setup backend frontend install-backend install-frontend test check

# ── One-command: start backend + frontend concurrently ────────────────────────
dev:
	@echo "Starting backend (FastAPI :8000) + frontend (Vite :5173)..."
	@cd frontend && npx concurrently \
		--names "backend,frontend" \
		--prefix-colors "blue,green" \
		"cd ../backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000" \
		"npm run dev"

# ── First-time setup ─────────────────────────────────────────────────────────
setup: install-backend install-frontend
	@echo "Setup complete. Run 'make dev' to start."

install-backend:
	@echo "Installing Python dependencies..."
	cd backend && uv sync --extra dev

install-frontend:
	@echo "Installing Node dependencies..."
	cd frontend && npm install

# ── Individual processes ──────────────────────────────────────────────────────
backend:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

# ── Quality checks ────────────────────────────────────────────────────────────
test:
	cd backend && uv run pytest -v

check: test
	cd frontend && npm run build
	cd frontend && npm run typecheck

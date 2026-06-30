PYTHON_BIN ?= python3.11
PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
FRONTEND_DIR ?= frontend

.PHONY: setup backend-setup frontend-setup db-up db-down wait-db migrate seed import reconcile bootstrap api web web-clean dev demo test clean

setup: backend-setup frontend-setup

.venv:
	$(PYTHON_BIN) -m venv .venv

backend-setup: .venv
	$(PIP) install -e ".[api,dev]"

frontend-setup:
	cd $(FRONTEND_DIR) && npm install

db-up:
	docker compose up -d db

db-down:
	docker compose down

wait-db:
	@echo "→ esperando Postgres…"
	@until docker exec operaciones_db pg_isready -U operaciones -d operaciones >/dev/null 2>&1; do sleep 1; done

bootstrap: db-up wait-db migrate seed import reconcile
	@echo "✔ bootstrap listo"

migrate:
	$(PYTHON) -m alembic upgrade head

seed:
	$(PYTHON) scripts/seed_db.py

import:
	$(PYTHON) scripts/import_movements.py

reconcile:
	$(PYTHON) scripts/reconcile_db.py

api:
	$(PYTHON) scripts/serve.py

web:
	cd $(FRONTEND_DIR) && npm run dev

web-clean:
	rm -rf $(FRONTEND_DIR)/.next
	cd $(FRONTEND_DIR) && npm run dev

dev: bootstrap
	@echo "→ API en :8000 y web en :3000 (Ctrl+C para detener)"
	@trap 'kill 0' INT TERM; \
	  $(PYTHON) scripts/serve.py & \
	  (cd $(FRONTEND_DIR) && npm run dev) & \
	  wait

demo:
	$(PYTHON) scripts/run_demo.py

test:
	$(PYTHON) -m pytest

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache frontend/.next

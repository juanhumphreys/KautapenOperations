PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
FRONTEND_DIR ?= frontend

.PHONY: setup backend-setup frontend-setup db-up db-down migrate seed import reconcile api web demo test clean

setup: backend-setup frontend-setup

.venv:
	python3 -m venv .venv

backend-setup: .venv
	$(PIP) install -e ".[api,dev]"

frontend-setup:
	cd $(FRONTEND_DIR) && npm install

db-up:
	docker compose up -d db

db-down:
	docker compose down

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

demo:
	$(PYTHON) scripts/run_demo.py

test:
	$(PYTHON) -m pytest

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache frontend/.next

"""Entrypoint para correr el backend en local.

Uso:
    python scripts/serve.py
    # o:
    .venv/bin/uvicorn api.main:app --reload --port 8000

Después abrí http://localhost:8000/dashboards/DEL en el browser.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import uvicorn


def main() -> None:
    uvicorn.run(
        "api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=[str(ROOT / "src")],
        log_level="info",
    )


if __name__ == "__main__":
    main()

"""FastAPI app: API JSON pura para el frontend Next.js.

Sin renderizado HTML. El frontend (Next.js en `frontend/`) consume estos
endpoints y arma la UI.

Rutas principales:
  GET  /api/health                          health-check
  GET  /api/lodges                          lista de lodges
  GET  /api/lodges/{code}                   info del lodge
  GET  /api/lodges/{code}/dashboard         JSON con datos del dashboard
  GET  /api/lodges/{code}/accounts          plan de cuentas
  GET  /api/lodges/{code}/movements         listado de movimientos
  POST /api/lodges/{code}/movements         crear movimiento
  GET  /api/lodges/{code}/movements/{id}    detalle
"""
from __future__ import annotations
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import db_session
from api.routers import movements as movements_router
from api.services import build_dashboard
from db.models import Lodge, Region
from operaciones.settings import get_settings

app = FastAPI(
    title="Kautapen Operaciones — Control de costos",
    version="0.3.0",
    description=(
        "API JSON que sirve el control de costos por bednight para los lodges "
        "de Kautapen Group. Consumido por el frontend Next.js."
    ),
)

# CORS: en dev, el frontend Next.js corre en 3000 y el backend en 8000.
# En prod, configurar via env CORS_ORIGINS="https://operaciones.kautapen.com,..."
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/lodges")
def list_lodges(session: Session = Depends(db_session)) -> list[dict[str, Any]]:
    lodges = session.scalars(
        select(Lodge).where(Lodge.active == True).order_by(Lodge.code)
    ).all()
    regions = {r.id: r for r in session.scalars(select(Region)).all()}
    return [
        {
            "code": l.code,
            "name": l.name,
            "region": regions[l.region_id].name if l.region_id in regions else None,
            "currency": l.currency,
        }
        for l in lodges
    ]


@app.get("/api/lodges/{code}")
def lodge_detail(code: str, session: Session = Depends(db_session)) -> dict[str, Any]:
    lodge = session.scalar(select(Lodge).where(Lodge.code == code))
    if not lodge:
        raise HTTPException(status_code=404, detail=f"Lodge {code} no existe")
    region = session.get(Region, lodge.region_id) if lodge.region_id else None
    return {
        "code": lodge.code,
        "name": lodge.name,
        "currency": lodge.currency,
        "active": lodge.active,
        "region": {"code": region.code, "name": region.name} if region else None,
    }


@app.get("/api/lodges/{code}/dashboard")
def lodge_dashboard_json(code: str, session: Session = Depends(db_session)) -> dict[str, Any]:
    payload = build_dashboard(session, code)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Lodge {code} no existe")
    return {
        "lodge": {
            "code": payload.lodge_code,
            "name": payload.lodge_name,
            "region": payload.region,
        },
        "season": {
            "bn_real": payload.bn_real,
            "bn_budget": payload.bn_budget,
            "months_elapsed": payload.months_elapsed,
            "months_total": payload.months_total,
        },
        "comparisons": [
            {
                "rubro": c.rubro,
                "criterio": c.criterio,
                "account_codes": list(c.account_codes),
                "budget_usd": c.budget_usd,
                "real_usd": c.real_usd_declarado,
                "budget_per_bn": c.budget_per_bn,
                "real_per_bn": c.real_per_bn,
                "variance_pct": c.variance_pct,
                "observation": c.observacion,
            }
            for c in payload.comparisons
        ],
        "flags": [
            {
                "rubro": f.rubro_or_account,
                "rule": f.rule,
                "severity": f.severity,
                "value": f.value,
                "impact_usd": f.impact_usd,
                "reason": f.reason,
                "obs_cliente": f.obs_cliente,
                "is_seasonal": f.is_seasonal,
            }
            for f in payload.flags
        ],
    }


app.include_router(movements_router.router)

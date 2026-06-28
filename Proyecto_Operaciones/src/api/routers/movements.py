"""Endpoints de movimientos: CRUD + autocompletes para el formulario."""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.deps import db_session
from api.schemas import AccountOption, MovementCreate, MovementOut, MovementsList
from db.models import Account, AuditLog, Lodge, Movement, Season

router = APIRouter(prefix="/api/lodges/{code}", tags=["movements"])


def _get_lodge(session: Session, code: str) -> Lodge:
    lodge = session.scalar(select(Lodge).where(Lodge.code == code))
    if not lodge:
        raise HTTPException(status_code=404, detail=f"Lodge {code} no existe")
    return lodge


def _active_season(session: Session, lodge_id) -> Optional[Season]:
    return session.scalar(
        select(Season)
        .where(Season.lodge_id == lodge_id, Season.closed == False)
        .order_by(Season.year_start.desc())
    )


def _validate_movement(session: Session, lodge: Lodge, payload: MovementCreate) -> None:
    """Validaciones server-side previas al insert."""
    # 1) Cuenta existe en el plan
    acc = session.get(Account, payload.account_code)
    if acc is None:
        raise HTTPException(
            status_code=400,
            detail=f"La cuenta {payload.account_code} no está en el plan. "
                   f"Pedile al admin que la agregue.",
        )
    # 2) Fecha dentro de la temporada activa (si hay una)
    season = _active_season(session, lodge.id)
    if season and season.starts_on and season.ends_on:
        if not (season.starts_on <= payload.date <= season.ends_on):
            raise HTTPException(
                status_code=400,
                detail=f"La fecha {payload.date} está fuera de la temporada "
                       f"{season.starts_on}..{season.ends_on}",
            )


@router.get("/accounts", response_model=list[AccountOption])
def list_accounts(code: str, session: Session = Depends(db_session)) -> list[AccountOption]:
    """Plan de cuentas para alimentar el dropdown del form.
    `code` del lodge se acepta pero hoy el plan es global; queda en la URL
    para que el día que tengamos planes por lodge la signature no cambie.
    """
    _get_lodge(session, code)
    accs = session.scalars(select(Account).order_by(Account.code)).all()
    return [
        AccountOption(
            code=a.code,
            name=a.name,
            rubro_secundario=a.rubro_secundario,
            rubro_final=a.rubro_final,
        )
        for a in accs
    ]


@router.get("/movements", response_model=MovementsList)
def list_movements(
    code: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    account: Optional[str] = None,
    session: Session = Depends(db_session),
) -> MovementsList:
    lodge = _get_lodge(session, code)
    stmt = select(Movement).where(Movement.lodge_id == lodge.id, Movement.void == False)
    count_stmt = select(func.count()).select_from(Movement).where(
        Movement.lodge_id == lodge.id, Movement.void == False,
    )
    if from_date:
        stmt = stmt.where(Movement.date >= from_date)
        count_stmt = count_stmt.where(Movement.date >= from_date)
    if to_date:
        stmt = stmt.where(Movement.date <= to_date)
        count_stmt = count_stmt.where(Movement.date <= to_date)
    if account:
        stmt = stmt.where(Movement.account_code == account)
        count_stmt = count_stmt.where(Movement.account_code == account)

    total = session.scalar(count_stmt) or 0
    items = session.scalars(
        stmt.order_by(Movement.date.desc(), Movement.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return MovementsList(
        total=total,
        page=page,
        page_size=page_size,
        items=[MovementOut.model_validate(m) for m in items],
    )


@router.get("/movements/{mov_id}", response_model=MovementOut)
def get_movement(code: str, mov_id: UUID, session: Session = Depends(db_session)) -> Movement:
    lodge = _get_lodge(session, code)
    m = session.get(Movement, mov_id)
    if not m or m.lodge_id != lodge.id:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    return m


@router.post("/movements", response_model=MovementOut, status_code=201)
def create_movement(
    code: str,
    payload: MovementCreate,
    session: Session = Depends(db_session),
) -> Movement:
    lodge = _get_lodge(session, code)
    _validate_movement(session, lodge, payload)

    amount_usd = (payload.amount_local / payload.fx_rate).quantize(Decimal("0.0001"))
    mov = Movement(
        lodge_id=lodge.id,
        account_code=payload.account_code,
        date=payload.date,
        amount_local=payload.amount_local,
        currency=payload.currency,
        fx_rate=payload.fx_rate,
        amount_usd=amount_usd,
        concept=payload.concept,
        description=payload.description,
        subdiario=payload.subdiario,
        comprobante=payload.comprobante,
        proveedor=payload.proveedor,
        tax_id=payload.tax_id,
        observation=payload.observation,
        attachment_url=payload.attachment_url,
        source="web",
    )
    session.add(mov)
    session.flush()
    session.add(AuditLog(
        action="create",
        entity="movement",
        entity_id=mov.id,
        after={
            "lodge_code": lodge.code,
            "account_code": mov.account_code,
            "date": str(mov.date),
            "amount_local": str(mov.amount_local),
            "amount_usd": str(mov.amount_usd),
            "currency": mov.currency,
            "subdiario": mov.subdiario,
            "proveedor": mov.proveedor,
        },
    ))
    session.commit()
    session.refresh(mov)
    return mov

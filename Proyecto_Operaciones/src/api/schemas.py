"""Pydantic schemas: contratos de request/response del API."""
from __future__ import annotations
from datetime import date as _date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MovementCreate(BaseModel):
    """Payload para crear un movimiento. Mapea al §7 del plan.

    Reglas mínimas (validaciones más cruzadas se hacen en el endpoint):
      - date: obligatorio
      - account_code: obligatorio (debe existir en el plan)
      - amount_local: != 0
      - fx_rate: > 0
      - subdiario: obligatorio
    """
    date: _date
    account_code: str = Field(min_length=1, max_length=32)
    amount_local: Decimal
    fx_rate: Decimal = Field(gt=0)
    currency: str = Field(default="ARS", min_length=2, max_length=8)
    subdiario: str = Field(min_length=1, max_length=32)
    concept: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    comprobante: Optional[str] = Field(default=None, max_length=64)
    proveedor: Optional[str] = Field(default=None, max_length=255)
    tax_id: Optional[str] = Field(default=None, max_length=32)
    observation: Optional[str] = None
    attachment_url: Optional[str] = None

    @field_validator("amount_local")
    @classmethod
    def amount_not_zero(cls, v: Decimal) -> Decimal:
        if v == 0:
            raise ValueError("amount_local no puede ser 0")
        return v


class MovementOut(BaseModel):
    """Respuesta cuando devolvemos un movimiento."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lodge_id: UUID
    account_code: str
    date: _date
    amount_local: Decimal
    currency: str
    fx_rate: Decimal
    amount_usd: Decimal
    concept: Optional[str] = None
    subdiario: Optional[str] = None
    comprobante: Optional[str] = None
    proveedor: Optional[str] = None
    tax_id: Optional[str] = None
    observation: Optional[str] = None
    source: str
    created_at: datetime
    void: bool


class MovementsList(BaseModel):
    """Listado paginado."""
    total: int
    page: int
    page_size: int
    items: list[MovementOut]


class AccountOption(BaseModel):
    """Para alimentar el dropdown de cuenta en el form."""
    code: str
    name: str
    rubro_secundario: Optional[str] = None
    rubro_final: Optional[str] = None

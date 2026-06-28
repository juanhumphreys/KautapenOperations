"""Modelos SQLAlchemy 2.0 — corresponden al schema descrito en
PLAN_fase2_webapp.md §4. Pensados para 40 lodges en producción.
"""
from __future__ import annotations
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric,
    String, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Base(DeclarativeBase):
    """Base declarativa común."""
    pass


# ---------------------------------------------------------------------------
# Dimensión: lo que define el dominio (cambia raramente)
# ---------------------------------------------------------------------------

class Region(Base):
    __tablename__ = "regions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    default_currency: Mapped[str] = mapped_column(String(8), nullable=False, default="ARS")

    lodges: Mapped[list["Lodge"]] = relationship(back_populates="region")


class Lodge(Base):
    __tablename__ = "lodges"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    region_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("regions.id"), nullable=False)
    manager_email: Mapped[Optional[str]] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    excel_template: Mapped[str] = mapped_column(String(32), nullable=False, default="standard_v1")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="ARS")

    region: Mapped[Region] = relationship(back_populates="lodges")
    seasons: Mapped[list["Season"]] = relationship(back_populates="lodge")


class Account(Base):
    """Plan de cuentas canónico, compartido entre todos los lodges."""
    __tablename__ = "accounts"
    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rubro_principal: Mapped[str] = mapped_column(String(128), default="")
    rubro_secundario: Mapped[str] = mapped_column(String(255), default="")
    rubro_final: Mapped[str] = mapped_column(String(255), default="")
    is_seasonal: Mapped[bool] = mapped_column(Boolean, default=False)


class Rubro(Base):
    """Agrupación de cuentas para el Budget Comparativo."""
    __tablename__ = "rubros"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    criterio: Mapped[Optional[str]] = mapped_column(String(16))   # 'BN' | 'Acumulado' | 'FD'
    display_order: Mapped[int] = mapped_column(Integer, default=0)

    accounts: Mapped[list["RubroAccount"]] = relationship(
        back_populates="rubro", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("name", name="uq_rubro_name"),)


class RubroAccount(Base):
    """M2M rubro <-> cuenta."""
    __tablename__ = "rubro_accounts"
    rubro_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rubros.id", ondelete="CASCADE"), primary_key=True)
    account_code: Mapped[str] = mapped_column(ForeignKey("accounts.code"), primary_key=True)

    rubro: Mapped[Rubro] = relationship(back_populates="accounts")


# ---------------------------------------------------------------------------
# Operación: lo que se mueve mes a mes
# ---------------------------------------------------------------------------

class Season(Base):
    """Una temporada (año fiscal) de un lodge."""
    __tablename__ = "seasons"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    lodge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lodges.id"), nullable=False)
    year_start: Mapped[int] = mapped_column(Integer, nullable=False)   # 2025 = temp 2025-26
    starts_on: Mapped[Optional[date]] = mapped_column(Date)
    ends_on: Mapped[Optional[date]] = mapped_column(Date)
    # Budget de temporada
    bn_budget: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    fd_budget: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    pax_budget: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    fx_budget: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4))   # TC fijo del budget
    # Real season-to-date (acumulado hasta el último mes cerrado).
    # En Fase 2D cuando entren cierres mensuales reales, derivamos desde
    # season_months. Por ahora se popula del Budget Comparativo del Excel.
    bn_real_std: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    pax_real_std: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    fd_real_std: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    months_elapsed: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 1))
    months_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 1))
    closed: Mapped[bool] = mapped_column(Boolean, default=False)

    lodge: Mapped[Lodge] = relationship(back_populates="seasons")
    months: Mapped[list["SeasonMonth"]] = relationship(back_populates="season", cascade="all, delete-orphan")
    budget_lines: Mapped[list["BudgetLine"]] = relationship(back_populates="season", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("lodge_id", "year_start", name="uq_season_lodge_year"),)


class SeasonMonth(Base):
    """Cierre mensual con BN/Pax/FD reales."""
    __tablename__ = "season_months"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    season_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seasons.id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    bn_real: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    pax_real: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    fd_real: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    closed_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))

    season: Mapped[Season] = relationship(back_populates="months")

    __table_args__ = (UniqueConstraint("season_id", "year", "month", name="uq_season_month"),)


class Movement(Base):
    """FACT TABLE: cada gasto o ingreso.

    Particionado por año fiscal en la migración (RANGE PARTITION BY date).
    Índices definidos abajo.
    """
    __tablename__ = "movements"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    lodge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lodges.id"), nullable=False)
    account_code: Mapped[str] = mapped_column(ForeignKey("accounts.code"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_local: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="ARS")
    fx_rate: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False, default=1)
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    concept: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    subdiario: Mapped[Optional[str]] = mapped_column(String(32))
    comprobante: Mapped[Optional[str]] = mapped_column(String(64))
    proveedor: Mapped[Optional[str]] = mapped_column(String(255))
    tax_id: Mapped[Optional[str]] = mapped_column(String(32))
    observation: Mapped[Optional[str]] = mapped_column(Text)
    attachment_url: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32), default="web")
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)
    void: Mapped[bool] = mapped_column(Boolean, default=False)
    voided_reason: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        Index("ix_movements_lodge_date", "lodge_id", "date"),
        Index("ix_movements_lodge_acc_date", "lodge_id", "account_code", "date"),
        Index("ix_movements_date", "date"),
        Index("ix_movements_active", "lodge_id", "date",
              postgresql_where=text("NOT void")),
    )


class BudgetLine(Base):
    """Budget de un rubro para una temporada."""
    __tablename__ = "budget_lines"
    season_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("seasons.id"), primary_key=True)
    rubro_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rubros.id"), primary_key=True)
    budget_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2))
    budget_per_bn: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4))

    season: Mapped[Season] = relationship(back_populates="budget_lines")


class Observation(Base):
    """Observación manual del manager sobre un rubro y período."""
    __tablename__ = "observations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    lodge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lodges.id"), nullable=False)
    rubro_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rubros.id"), nullable=False)
    period: Mapped[str] = mapped_column(String(32), nullable=False)   # '2026-04' o 'season-to-date'
    body: Mapped[str] = mapped_column(Text, nullable=False)   # texto de la observación
    author: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"),
    )


# ---------------------------------------------------------------------------
# Control de acceso
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="lodge_manager")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"),
    )


class UserLodge(Base):
    """M2M user <-> lodge (override del rol)."""
    __tablename__ = "user_lodges"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    lodge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lodges.id", ondelete="CASCADE"), primary_key=True)


class UserRegion(Base):
    """M2M user <-> region (un regional_manager ve toda la región)."""
    __tablename__ = "user_regions"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    region_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("regions.id", ondelete="CASCADE"), primary_key=True)


class AuditLog(Base):
    """Trazabilidad: quién hizo qué y cuándo."""
    __tablename__ = "audit_log"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(32), nullable=False)   # 'create' | 'update' | 'void'
    entity: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    before: Mapped[Optional[dict]] = mapped_column(JSONB)
    after: Mapped[Optional[dict]] = mapped_column(JSONB)

    __table_args__ = (
        Index("ix_audit_entity", "entity", "entity_id"),
        Index("ix_audit_user_time", "user_id", "timestamp"),
    )

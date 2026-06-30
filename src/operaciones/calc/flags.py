"""Reglas de flagging de desvíos. Sin ML. Pensado para auditoría manual.

Reglas (ver Plan, sección 5.6):

R1 - DESVIO_BUDGET
     |real_per_bn / budget_per_bn - 1| > THRESHOLD_BUDGET_PCT
     y el monto absoluto del rubro supera MIN_USD (evita ruido sobre cuentas chicas).

R2 - SALTO_MOM
     Comparar costo USD del mes vs mes anterior por cuenta:
     |real_mes / real_mes_anterior - 1| > THRESHOLD_MOM_PCT y delta absoluto > MIN_USD.

R3 - OUTLIER_INTRAMES
     Un movimiento individual cuyo monto absoluto > MEDIA_HISTORICA * MULT_OUTLIER
     dentro de la misma cuenta. (No implementado en demo; requiere histórico).

Cada flag guarda 'reason' legible para la curaduría manual previa al demo
(se muestran sólo 3-4 confirmados).
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Optional

from .per_bednight import AccountMonthlySpend, RubroComparison


# Umbrales (configurables; defaults razonables para validar contra abr/may).
THRESHOLD_BUDGET_PCT = 0.10   # 10% desvío vs budget
THRESHOLD_MOM_PCT = 0.30      # 30% salto mes a mes
MIN_USD_FOR_FLAG = 500        # ignorar rubros con gasto <500 USD acumulado


# Rubros que se pagan en pocas cuotas al año (patentes, seguros, licencias, canon).
# Un desvío negativo en estos rubros es típicamente TIMING (la cuota todavía no se pagó),
# no ahorro real — por eso los separamos del alert normal.
SEASONAL_RUBROS = {
    "Vehicles Taxes",
    "Insurance for lodge and boats",
    "Licenses / Permits (Fishing and Shooting)",
}


@dataclass(frozen=True)
class Flag:
    lodge_code: str
    rubro_or_account: str
    rule: str               # "DESVIO_BUDGET" | "SALTO_MOM" | "OUTLIER_INTRAMES"
    severity: str           # "info" | "warn" | "alert" | "timing"
    reason: str
    value: Optional[float]  # número que disparó el flag (ej. % desvío)
    impact_usd: Optional[float] = None   # delta absoluto en USD — la magnitud "real"
    obs_cliente: Optional[str] = None    # observación manual asociada, si la hay
    is_seasonal: bool = False            # rubro de pago estacional (timing posible)
    is_income: bool = False              # True si el rubro es de ingreso (semántica invertida)


def _severity(pct: float) -> str:
    if abs(pct) >= 0.30:
        return "alert"
    if abs(pct) >= 0.15:
        return "warn"
    return "info"


def flag_budget_deviations(
    comparisons: Iterable[RubroComparison],
    threshold_pct: float = THRESHOLD_BUDGET_PCT,
    min_usd: float = MIN_USD_FOR_FLAG,
) -> list[Flag]:
    out = []
    for c in comparisons:
        if c.budget_per_bn in (None, 0) or c.real_per_bn is None:
            continue
        pct = (c.real_per_bn - c.budget_per_bn) / c.budget_per_bn
        if abs(pct) < threshold_pct:
            continue
        if c.budget_usd is None or abs(c.budget_usd) < min_usd:
            continue

        # Impacto absoluto en USD: la magnitud "real" del desvío.
        impact = None
        if c.real_usd_declarado is not None and c.budget_usd is not None:
            impact = c.real_usd_declarado - c.budget_usd

        seasonal = c.rubro in SEASONAL_RUBROS
        # Rubros estacionales con desvío negativo → 'timing', no 'alert' normal.
        # Si están por encima del budget (gastaron más de lo esperado) sí es alerta real.
        if seasonal and pct < 0:
            sev = "timing"
        else:
            sev = _severity(pct)

        direction = "por encima" if pct > 0 else "por debajo"
        reason = (f"USD/BN real {c.real_per_bn:.2f} vs budget {c.budget_per_bn:.2f} "
                  f"({pct:+.1%} {direction})")
        if impact is not None:
            reason += f" · impacto ${impact:+,.0f} USD"

        out.append(Flag(
            lodge_code=c.lodge_code,
            rubro_or_account=c.rubro,
            rule="DESVIO_BUDGET",
            severity=sev,
            reason=reason,
            value=pct,
            impact_usd=impact,
            obs_cliente=c.observacion or None,
            is_seasonal=seasonal,
            is_income=c.is_income,
        ))
    # Orden default: por impacto USD absoluto (lo que mueve plata real va primero).
    out.sort(key=lambda f: -abs(f.impact_usd or 0))
    return out


def flag_month_over_month(
    spends: Iterable[AccountMonthlySpend],
    threshold_pct: float = THRESHOLD_MOM_PCT,
    min_usd: float = MIN_USD_FOR_FLAG,
) -> list[Flag]:
    """Compara cada cuenta consigo misma en meses consecutivos.

    Si alguno de los dos meses está por debajo del umbral de ruido (min_usd),
    el % se vuelve engañoso (ej. de $11 a $504 = +4261%). En esos casos
    reportamos solo el delta absoluto y la severity la decidimos por |delta|.
    """
    by_acc: dict[tuple[str, str], dict[str, AccountMonthlySpend]] = defaultdict(dict)
    for s in spends:
        by_acc[(s.lodge_code, s.account_code)][s.month_key] = s

    out = []
    for (lodge, acc), by_month in by_acc.items():
        months = sorted(by_month)
        for prev_m, cur_m in zip(months, months[1:]):
            prev_s = by_month[prev_m]
            cur_s = by_month[cur_m]
            delta = cur_s.amount_usd - prev_s.amount_usd
            # Ambos meses muy chicos → ruido, no flag.
            if abs(prev_s.amount_usd) < min_usd and abs(cur_s.amount_usd) < min_usd:
                continue
            # Denominador chico (o cero): el % no sirve. Reportamos solo |delta|.
            small_prev = abs(prev_s.amount_usd) < min_usd or prev_s.amount_usd == 0
            if small_prev:
                if abs(delta) < min_usd:
                    continue   # el salto en sí también es chico
                pct = None
                sev = (
                    "alert" if abs(delta) >= 3000
                    else "warn" if abs(delta) >= 1000
                    else "info"
                )
                reason = (f"{prev_m}→{cur_m}: "
                          f"USD {prev_s.amount_usd:,.0f} → {cur_s.amount_usd:,.0f} "
                          f"(Δ {delta:+,.0f} USD · mes anterior muy chico para %)")
            else:
                pct = delta / abs(prev_s.amount_usd)
                if abs(pct) < threshold_pct:
                    continue
                sev = _severity(pct)
                reason = (f"{prev_m}→{cur_m}: "
                          f"USD {prev_s.amount_usd:,.0f} → {cur_s.amount_usd:,.0f} "
                          f"({pct:+.1%})")
            out.append(Flag(
                lodge_code=lodge,
                rubro_or_account=f"{acc} {cur_s.account_name}",
                rule="SALTO_MOM",
                severity=sev,
                reason=reason,
                value=pct,
                impact_usd=delta,
            ))
    # Orden default: por impacto USD absoluto del salto (los más fuertes primero).
    out.sort(key=lambda f: -abs(f.impact_usd or 0))
    return out

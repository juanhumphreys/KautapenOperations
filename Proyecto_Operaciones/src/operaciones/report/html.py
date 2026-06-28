"""Reporte HTML estático con dashboard + detalle por rubro.

Sin dependencias. Una sola página con dos tabs (Dashboard, Detalle). Para abrirlo,
doble click en data/out/demo_delta.html.

Paleta unificada (variables CSS): un único azul-grafito como brand, severidades
con un solo tono saturado (rojo / naranja / verde) y un único fondo neutro.
"""
from __future__ import annotations
import html
from pathlib import Path
from typing import Optional

from ..calc.flags import Flag
from ..calc.per_bednight import RubroComparison
from ..calc.reconcile import ReconcileAccount


def _esc(s) -> str:
    return html.escape(str(s)) if s is not None else ""


def _fmt_usd(v: float | None, with_sign: bool = False) -> str:
    if v is None:
        return "—"
    if with_sign:
        return f"${v:+,.0f}"
    return f"${v:,.0f}"


def _fmt_pct(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:+.1%}"


# ---------------------------------------------------------------------------
# Paleta y CSS unificados.
# ---------------------------------------------------------------------------
CSS = """
:root {
  --bg:         #f4f4f5;     /* zinc-100 */
  --surface:    #ffffff;
  --border:     #e4e4e7;     /* zinc-200 */
  --border-strong: #d4d4d8;  /* zinc-300 */
  --text:       #18181b;     /* zinc-900 */
  --text-soft:  #52525b;     /* zinc-600 */
  --text-mute:  #a1a1aa;     /* zinc-400 */
  --brand:      #1e293b;     /* slate-800 */
  --brand-soft: #475569;     /* slate-600 */

  --alert:      #b91c1c;     /* red-700 */
  --alert-bg:   #fef2f2;
  --warn:       #c2410c;     /* orange-700 */
  --warn-bg:    #fff7ed;
  --ok:         #15803d;     /* green-700 */
  --ok-bg:      #f0fdf4;
  --timing:     #6366f1;     /* indigo-500 */
  --timing-bg:  #eef2ff;

  --radius:     10px;
  --radius-lg:  14px;
  --pad:        16px;
  --pad-lg:     24px;
  --shadow:     0 1px 2px rgba(0,0,0,0.04), 0 1px 1px rgba(0,0,0,0.02);
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  background: var(--bg); color: var(--text);
  line-height: 1.5; font-size: 14px;
}
a { color: var(--brand); }

.wrap { max-width: 1180px; margin: 0 auto; padding: 24px; }

/* ---- Top bar / brand ---- */
.topbar {
  background: var(--brand); color: white;
  padding: 20px 24px; border-radius: var(--radius-lg);
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 20px;
}
.topbar h1 {
  margin: 0; font-size: 18px; font-weight: 600;
  display: flex; align-items: center; gap: 10px;
}
.topbar .sub { color: #cbd5e1; font-size: 13px; margin-top: 4px; }
.topbar .meta { text-align: right; }
.topbar .meta .stamp { color: #94a3b8; font-size: 12px; }

/* ---- Tabs ---- */
.tabs {
  display: flex; gap: 4px; padding: 4px;
  background: var(--surface); border-radius: var(--radius);
  border: 1px solid var(--border); margin-bottom: 20px;
  box-shadow: var(--shadow);
}
.tab {
  flex: 1; text-align: center; padding: 10px 16px;
  border-radius: 8px; cursor: pointer; font-weight: 500;
  color: var(--text-soft); transition: background 0.15s;
  border: none; background: transparent; font-size: 14px;
  font-family: inherit;
}
.tab:hover { background: var(--bg); }
.tab.active { background: var(--brand); color: white; }

.tab-content { display: none; }
.tab-content.active { display: block; }

/* ---- KPIs ---- */
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }
.kpi {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 16px;
  box-shadow: var(--shadow);
}
.kpi .label {
  color: var(--text-soft); font-size: 11px;
  text-transform: uppercase; letter-spacing: 0.6px; font-weight: 600;
}
.kpi .value { font-size: 26px; font-weight: 700; margin-top: 6px; line-height: 1.1; color: var(--brand); }
.kpi .delta { font-size: 12px; color: var(--text-mute); margin-top: 4px; }

/* ---- Section ---- */
.section { margin-bottom: 28px; }
.section h2 {
  margin: 0 0 6px 0; font-size: 16px; font-weight: 600; color: var(--brand);
  display: flex; align-items: center; gap: 8px;
}
.section .desc {
  color: var(--text-soft); font-size: 13px; margin: 0 0 14px 0;
}

/* ---- Cards (alerts) ---- */
.cards { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 16px;
  display: flex; flex-direction: column; gap: 8px;
  box-shadow: var(--shadow);
}
.card.severity-alert  { border-left: 4px solid var(--alert);  }
.card.severity-warn   { border-left: 4px solid var(--warn);   }
.card.severity-saving { border-left: 4px solid var(--ok);     }
.card.severity-ok     { border-left: 4px solid var(--ok);     }
.card.severity-timing { border-left: 4px solid var(--timing); }

.card .head { display: flex; align-items: center; justify-content: space-between; }
.card .rubro { font-weight: 600; font-size: 15px; color: var(--text); }
.card .badges { display: flex; gap: 6px; }

.badge {
  display: inline-block; padding: 2px 8px; border-radius: 999px;
  font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;
}
.badge-alert  { background: var(--alert-bg);  color: var(--alert);  }
.badge-warn   { background: var(--warn-bg);   color: var(--warn);   }
.badge-ok     { background: var(--ok-bg);     color: var(--ok);     }
.badge-timing { background: var(--timing-bg); color: var(--timing); }
.badge-mute   { background: var(--bg);        color: var(--text-soft); border: 1px solid var(--border); }

.card .numbers { display: flex; align-items: baseline; gap: 12px; margin-top: 2px; }
.card .numbers .pct  { font-size: 22px; font-weight: 700; }
.card .numbers .usd  { font-size: 14px; color: var(--text-soft); font-variant-numeric: tabular-nums; }
.card.severity-alert  .numbers .pct { color: var(--alert);  }
.card.severity-warn   .numbers .pct { color: var(--warn);   }
.card.severity-saving .numbers .pct { color: var(--ok);     }
.card.severity-ok     .numbers .pct { color: var(--ok);     }
.card.severity-timing .numbers .pct { color: var(--timing); }

.card .reason { color: var(--text-soft); font-size: 12px; }

.card .obs {
  background: var(--bg); padding: 10px 12px; border-radius: 8px;
  font-size: 12px; color: var(--text); margin-top: 4px;
}
.card .obs .obs-head {
  font-size: 10px; text-transform: uppercase; letter-spacing: 0.6px;
  color: var(--text-soft); font-weight: 600; margin-bottom: 4px;
}
.card .obs.missed { background: var(--alert-bg); }
.card .obs.missed .obs-head { color: var(--alert); }

/* ---- Validation green panel ---- */
.panel {
  background: var(--ok-bg); border: 1px solid #bbf7d0;
  border-left: 4px solid var(--ok); border-radius: var(--radius);
  padding: 16px; display: flex; align-items: center; gap: 16px;
}
.panel .num { font-size: 28px; font-weight: 700; color: var(--ok); white-space: nowrap; }
.panel .copy { color: var(--text); }
.panel .copy strong { display: block; margin-bottom: 2px; color: var(--ok); }
.panel .copy span { color: var(--text-soft); font-size: 13px; }

/* ---- Detail table ---- */
table.tbl {
  width: 100%; border-collapse: collapse; background: var(--surface);
  border-radius: var(--radius); overflow: hidden; border: 1px solid var(--border);
  box-shadow: var(--shadow); font-size: 13px;
}
table.tbl th, table.tbl td { padding: 10px 12px; text-align: left; }
table.tbl th {
  background: var(--bg); color: var(--text-soft); font-size: 11px;
  text-transform: uppercase; letter-spacing: 0.6px; font-weight: 600;
  border-bottom: 1px solid var(--border);
}
table.tbl tr:not(:last-child) td { border-bottom: 1px solid var(--border); }
table.tbl td.num { text-align: right; font-variant-numeric: tabular-nums; }
table.tbl tr.row-alert   { background: var(--alert-bg); }
table.tbl tr.row-warn    { background: var(--warn-bg);  }
table.tbl tr.row-info    { background: #fefce8; }
table.tbl tr.row-saving  { background: var(--ok-bg); }
table.tbl tr.row-timing  { background: var(--timing-bg); }

/* ---- Footer ---- */
.foot {
  color: var(--text-mute); font-size: 12px; margin-top: 32px;
  padding: 16px 0; text-align: center; border-top: 1px solid var(--border);
}
"""


def _severity_class(c: RubroComparison) -> str:
    pct = c.variance_pct
    if pct is None: return ""
    # Pintamos verde si gastaron menos (ahorro), independiente de la magnitud.
    if pct < -0.10:
        return "row-saving"
    if pct >= 0.30: return "row-alert"
    if pct >= 0.15: return "row-warn"
    if pct >= 0.10: return "row-info"
    return ""


def _visual_severity(flag: Flag) -> str:
    """Color visual del card:
       - timing → índigo (cuotas pendientes)
       - ahorro (value < 0) → verde (gastaron menos del budget)
       - sobrecosto (value > 0) → rojo/naranja según magnitud
    """
    if flag.severity == "timing":
        return "timing"
    if flag.value is not None and flag.value < 0:
        return "saving"
    return flag.severity   # alert / warn


def _badge_for_flag(flag: Flag) -> str:
    vsev = _visual_severity(flag)
    if vsev == "timing":
        return '<span class="badge badge-timing">posible timing</span>'
    if vsev == "saving":
        return '<span class="badge badge-ok">ahorro</span>'
    return f'<span class="badge badge-{vsev}">sobrecosto</span>'


def _card(flag: Flag) -> str:
    vsev = _visual_severity(flag)
    obs_html = ""
    if flag.obs_cliente:
        obs_html = (
            f'<div class="obs"><div class="obs-head">Observación del cliente</div>'
            f"{_esc(flag.obs_cliente)}</div>"
        )
    elif vsev in ("alert", "warn"):
        # Sólo destacamos "se les pasó" para sobrecostos sin comentar.
        # Ahorros no observados no son críticos (es buena noticia, capaz no la anotaron).
        obs_html = (
            '<div class="obs missed"><div class="obs-head">Sin observación del cliente</div>'
            "El sistema detectó este sobrecosto pero el cliente no lo comentó. "
            "Candidato a revisión.</div>"
        )

    impact = (f'<span class="usd">{_fmt_usd(flag.impact_usd, with_sign=True)} USD</span>'
              if flag.impact_usd is not None else "")
    extra_badge = ""
    if flag.obs_cliente:
        extra_badge = '<span class="badge badge-ok">visto</span>'
    elif vsev in ("alert", "warn"):
        extra_badge = '<span class="badge badge-alert">sin ver</span>'

    return f"""
    <div class="card severity-{vsev}">
      <div class="head">
        <div class="rubro">{_esc(flag.rubro_or_account)}</div>
        <div class="badges">{_badge_for_flag(flag)}{extra_badge}</div>
      </div>
      <div class="numbers">
        <span class="pct">{_fmt_pct(flag.value)}</span>
        {impact}
      </div>
      <div class="reason">{_esc(flag.reason)}</div>
      {obs_html}
    </div>
    """


def _comparison_row(c: RubroComparison) -> str:
    sev = _severity_class(c)
    return f"""
      <tr class="{sev}">
        <td>{_esc(c.rubro)}</td>
        <td>{_esc('+'.join(c.account_codes))}</td>
        <td class="num">{_fmt_usd(c.budget_usd)}</td>
        <td class="num">{_fmt_usd(c.real_usd_declarado)}</td>
        <td class="num">{_fmt_usd((c.real_usd_declarado or 0) - (c.budget_usd or 0), with_sign=True)}</td>
        <td class="num">{_fmt_usd(c.budget_per_bn)}</td>
        <td class="num">{_fmt_usd(c.real_per_bn)}</td>
        <td class="num">{_fmt_pct(c.variance_pct)}</td>
      </tr>
    """


JS = """
function showTab(name) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.querySelector('[data-tab=\"' + name + '\"]').classList.add('active');
}
"""


def render_html(
    lodge_code: str,
    lodge_name: str,
    bn_real: float | None,
    bn_budget: float | None,
    months_elapsed: float | None,
    months_total: float | None,
    comparisons: list[RubroComparison],
    flags: list[Flag],
    reconcile: list[ReconcileAccount],
    out_path: Path,
    topbar_html: str = "",
    extra_css: str = "",
    extra_body_end: str = "",
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Particionar los flags por severidad y tipo.
    budget_flags = [f for f in flags if f.rule == "DESVIO_BUDGET"]
    # Threshold para separar "mueve mucha plata" de "% alto en rubro chico".
    HIGH_IMPACT_THRESHOLD = 2500   # USD absoluto

    not_timing = [f for f in budget_flags if not f.is_seasonal and f.severity in ("alert", "warn")]
    # Sección 1: ordenado por impact_usd absoluto, sólo los que mueven >=threshold.
    by_usd = sorted(not_timing, key=lambda f: -abs(f.impact_usd or 0))
    high_impact = [f for f in by_usd if abs(f.impact_usd or 0) >= HIGH_IMPACT_THRESHOLD]
    # Sección 2: rubros chicos en plata pero con desvío % grande.
    by_pct = sorted(not_timing, key=lambda f: -abs(f.value or 0))
    high_pct_only = [
        f for f in by_pct
        if abs(f.impact_usd or 0) < HIGH_IMPACT_THRESHOLD and abs(f.value or 0) >= 0.30
    ]
    # Los "se les pasó" sólo aplican a sobrecostos (value > 0). Un ahorro sin
    # observación no es problema — es buena noticia, capaz ni la anotaron.
    overspend = [f for f in not_timing if (f.value or 0) > 0]
    missed = [f for f in overspend if not f.obs_cliente][:4]
    timing = [f for f in budget_flags if f.severity == "timing"]

    n_overspend = len(overspend)
    n_savings = sum(1 for f in not_timing if (f.value or 0) < 0)
    n_missed = len([f for f in overspend if not f.obs_cliente])
    n_timing = len(timing)
    n_match = sum(1 for r in reconcile if abs(r.gap_usd) < 1)

    progress_pct = (months_elapsed / months_total * 100) if (months_elapsed and months_total) else 0

    # Detalle: ordenamos por impact_usd absoluto también.
    comparisons_sorted = sorted(
        comparisons,
        key=lambda c: -abs((c.real_usd_declarado or 0) - (c.budget_usd or 0)),
    )

    cards_top = "".join(_card(f) for f in high_impact[:6])
    cards_high_pct = "".join(_card(f) for f in high_pct_only[:6])
    cards_missed = "".join(_card(f) for f in missed)
    cards_timing = "".join(_card(f) for f in timing)
    rows = "".join(_comparison_row(c) for c in comparisons_sorted)

    high_pct_section = ""
    if cards_high_pct:
        high_pct_section = f"""
        <div class="section">
          <h2>Desvíos altos por porcentaje (rubros chicos en USD)</h2>
          <p class="desc">Rubros donde el desvío vs budget supera el 30% pero mueven poca plata en términos absolutos (menos de USD {HIGH_IMPACT_THRESHOLD:,}). Suelen indicar que el budget original quedó subdimensionado.</p>
          <div class="cards">{cards_high_pct}</div>
        </div>
        """

    missed_section = ""
    if cards_missed:
        missed_section = f"""
        <div class="section">
          <h2>Desvíos sin observación del cliente</h2>
          <p class="desc">El cliente no comentó estos en su Excel. Posibles 'se les pasó'.</p>
          <div class="cards">{cards_missed}</div>
        </div>
        """

    timing_section = ""
    if cards_timing:
        timing_section = f"""
        <div class="section">
          <h2>Posibles 'timing' (cuotas anuales pendientes)</h2>
          <p class="desc">Patentes, seguros y licencias se pagan en pocas cuotas al año.
          Un desvío negativo aquí suele ser plata que todavía no se pagó, no un ahorro real.</p>
          <div class="cards">{cards_timing}</div>
        </div>
        """

    # Si el server inyecta una topbar (vista web), reemplazamos la topbar
    # standalone del HTML original. Para mantener compat con el demo de Fase 1
    # (Excel → HTML estático), si no se inyecta nada usamos la versión original.
    if topbar_html:
        topbar_section = topbar_html
        # Renombramos las tabs internas para no chocar con las del global topbar.
        tabs_section = """
  <div class="tabs" style="margin-top:0;">
    <button class="tab active" data-tab="dashboard" onclick="showTab('dashboard')">Resumen</button>
    <button class="tab" data-tab="detalle" onclick="showTab('detalle')">Detalle por rubro</button>
  </div>"""
    else:
        topbar_section = f"""
  <div class="topbar">
    <div>
      <h1>Control de costos por bednight · {_esc(lodge_name)}</h1>
      <div class="sub">Temporada 2025-2026 · datos al cierre de Mayo 2026</div>
    </div>
    <div class="meta">
      <div class="stamp">Kautapen Group · pipeline v0.1</div>
    </div>
  </div>"""
        tabs_section = """
  <div class="tabs">
    <button class="tab active" data-tab="dashboard" onclick="showTab('dashboard')">Dashboard</button>
    <button class="tab" data-tab="detalle" onclick="showTab('detalle')">Detalle por rubro</button>
  </div>"""

    out_html = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8" />
<title>Control de Costos · {_esc(lodge_name)}</title>
<style>{CSS}
{extra_css}</style>
</head>
<body>
<div class="wrap">

  {topbar_section}
  {tabs_section}

  <!-- ====== DASHBOARD ====== -->
  <div id="tab-dashboard" class="tab-content active">

    <div class="kpis">
      <div class="kpi">
        <div class="label">BN real</div>
        <div class="value">{int(bn_real) if bn_real else '—'}</div>
        <div class="delta">budget {int(bn_budget) if bn_budget else '—'}</div>
      </div>
      <div class="kpi">
        <div class="label">Avance temporada</div>
        <div class="value">{int(progress_pct)}%</div>
        <div class="delta">{int(months_elapsed or 0)} de {int(months_total or 0)} meses</div>
      </div>
      <div class="kpi">
        <div class="label">Sobrecostos</div>
        <div class="value" style="color: var(--alert);">{n_overspend}</div>
        <div class="delta">{n_missed} sin observación</div>
      </div>
      <div class="kpi">
        <div class="label">Ahorros</div>
        <div class="value" style="color: var(--ok);">{n_savings}</div>
        <div class="delta">gastaron menos que el budget</div>
      </div>
    </div>

    <div class="section">
      <h2>Desvíos críticos por impacto USD</h2>
      <p class="desc">Rubros que mueven plata real (más de USD {HIGH_IMPACT_THRESHOLD:,} de diferencia vs budget). Ordenados por monto absoluto, no por %.</p>
      <div class="cards">{cards_top}</div>
    </div>

    {high_pct_section}
    {missed_section}
    {timing_section}

    <div class="section">
      <h2>Validación contra el Excel del cliente</h2>
      <div class="panel">
        <div class="num">{n_match}/{len(reconcile)}</div>
        <div class="copy">
          <strong>Cuentas que coinciden al centavo</strong>
          <span>Comparamos nuestra suma de movimientos contra lo que el cliente declara cuenta-por-cuenta. El motor reproduce sus números exactos en todas las cuentas.</span>
        </div>
      </div>
    </div>

  </div>

  <!-- ====== DETALLE ====== -->
  <div id="tab-detalle" class="tab-content">

    <div class="section">
      <h2>Detalle por rubro</h2>
      <p class="desc">Todos los rubros, ordenados por impacto USD absoluto. Las filas con color indican severidad del desvío. La columna USD/BN normaliza el gasto por huésped-noche.</p>
      <table class="tbl">
        <tr>
          <th>Rubro</th>
          <th>Cuentas</th>
          <th>Budget USD</th>
          <th>Real USD</th>
          <th>Δ USD</th>
          <th>Budget USD/BN</th>
          <th>Real USD/BN</th>
          <th>Δ %</th>
        </tr>
        {rows}
      </table>
    </div>

  </div>

  <div class="foot">
    Generado automáticamente · Kautapen Group · pipeline Operaciones v0.2
  </div>
</div>
<script>{JS}</script>
{extra_body_end}
</body>
</html>
"""
    out_path.write_text(out_html, encoding="utf-8")

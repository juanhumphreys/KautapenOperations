/**
 * Tipos compartidos: deben matchear con los JSON que devuelve el backend FastAPI.
 * Cuando agreguemos un cliente OpenAPI más adelante, estos se autogeneran.
 */

export type Severity = "alert" | "warn" | "info" | "ok" | "timing";

export type LodgeSummary = {
  code: string;
  name: string;
  region: string | null;
  currency: string;
};

export type RubroComparison = {
  rubro_id: string | null;
  rubro: string;
  criterio: string | null;
  account_codes: string[];
  budget_usd: number | null;
  real_usd: number | null;
  budget_per_bn: number | null;
  real_per_bn: number | null;
  variance_pct: number | null;
  observation: string | null;
  is_income: boolean;
};

export type AccountBreakdown = {
  code: string;
  name: string;
  total_usd: number;
  n_movements: number;
};

export type RubroDetail = {
  lodge: { code: string; name: string };
  rubro: { id: string; name: string; criterio: string | null };
  season: { bn_real: number | null; bn_budget: number | null };
  budget_usd: number | null;
  real_usd: number;
  budget_per_bn: number | null;
  real_per_bn: number | null;
  variance_pct: number | null;
  observation: string | null;
  is_income: boolean;
  accounts: AccountBreakdown[];
};

export type MonthlySpend = {
  month_key: string;
  total_usd: number;
  n_movements: number;
};

export type AccountDetail = {
  lodge: { code: string; name: string };
  account: {
    code: string;
    name: string;
    rubro_principal: string | null;
    rubro_secundario: string | null;
    rubro_final: string | null;
    is_income: boolean;
  };
  total_usd: number;
  n_movements: number;
  first_date: string | null;
  last_date: string | null;
  monthly: MonthlySpend[];
};

export type Flag = {
  rubro: string;
  rule: string;
  severity: Severity;
  value: number | null;
  impact_usd: number | null;
  reason: string;
  obs_cliente: string | null;
  is_seasonal: boolean;
  is_income: boolean;
};

export type DashboardPayload = {
  lodge: {
    code: string;
    name: string;
    region: string | null;
  };
  season: {
    bn_real: number | null;
    bn_budget: number | null;
    months_elapsed: number | null;
    months_total: number | null;
  };
  comparisons: RubroComparison[];
  flags: Flag[];
  mom_flags: Flag[];
};

export type MovementsFilters = {
  page?: number;
  pageSize?: number;
  from_date?: string;
  to_date?: string;
  account?: string;
};

export type AccountOption = {
  code: string;
  name: string;
  rubro_secundario: string | null;
  rubro_final: string | null;
};

export type Movement = {
  id: string;
  lodge_id: string;
  account_code: string;
  date: string;
  amount_local: string;
  currency: string;
  fx_rate: string;
  amount_usd: string;
  concept: string | null;
  subdiario: string | null;
  comprobante: string | null;
  proveedor: string | null;
  tax_id: string | null;
  observation: string | null;
  source: string;
  created_at: string;
  void: boolean;
};

export type MovementsList = {
  total: number;
  page: number;
  page_size: number;
  items: Movement[];
};

export type MovementCreate = {
  date: string;
  account_code: string;
  amount_local: string;
  fx_rate: string;
  currency: string;
  subdiario: string;
  concept?: string | null;
  description?: string | null;
  comprobante?: string | null;
  proveedor?: string | null;
  tax_id?: string | null;
  observation?: string | null;
  attachment_url?: string | null;
};

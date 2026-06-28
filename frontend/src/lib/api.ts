/**
 * Cliente HTTP tipado contra el backend FastAPI.
 * NEXT_PUBLIC_API_URL en .env.local; default a localhost en dev.
 */
import type {
  AccountOption,
  DashboardPayload,
  LodgeSummary,
  Movement,
  MovementCreate,
  MovementsList,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  const text = await res.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }
  if (!res.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? (body as { detail: unknown }).detail
        : body;
    throw new ApiError(
      typeof detail === "string" ? detail : `HTTP ${res.status}`,
      res.status,
      detail,
    );
  }
  return body as T;
}

export const api = {
  health: () => request<{ status: string }>("/api/health"),
  listLodges: () => request<LodgeSummary[]>("/api/lodges"),
  dashboard: (code: string) =>
    request<DashboardPayload>(`/api/lodges/${code}/dashboard`),
  accounts: (code: string) =>
    request<AccountOption[]>(`/api/lodges/${code}/accounts`),
  listMovements: (code: string, page = 1, pageSize = 50) =>
    request<MovementsList>(
      `/api/lodges/${code}/movements?page=${page}&page_size=${pageSize}`,
    ),
  createMovement: (code: string, payload: MovementCreate) =>
    request<Movement>(`/api/lodges/${code}/movements`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

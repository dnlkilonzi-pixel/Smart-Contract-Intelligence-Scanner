// API client — thin wrapper around fetch pointing at the FastAPI backend.

import type { ScanResponse, WalletIntelligenceOut, WalletGraph } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  return res.json() as Promise<T>;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  return res.json() as Promise<T>;
}

// --- Contract scanning ---

export interface ScanRequest {
  source_code?: string;
  address?: string;
  compiler_version?: string;
  enable_mythril?: boolean;
}

export async function scanContract(req: ScanRequest): Promise<ScanResponse> {
  return post<ScanResponse>("/api/v1/scanner/scan", req);
}

// --- Wallet intelligence ---

export async function getWalletIntelligence(
  address: string
): Promise<WalletIntelligenceOut> {
  return get<WalletIntelligenceOut>(`/api/v1/wallet/${address}/intelligence`);
}

// --- Wallet graph ---

export async function getWalletGraph(
  address: string,
  depth = 1
): Promise<WalletGraph> {
  return get<WalletGraph>(`/api/v1/graph/wallet/${address}?depth=${depth}`);
}

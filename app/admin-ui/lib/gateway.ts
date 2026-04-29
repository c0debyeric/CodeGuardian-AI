/**
 * Server-only helper for talking to the LLM Gateway admin API.
 *
 * The admin key lives on the Next.js server (env: ADMIN_API_KEY) and is
 * injected into every request. The browser never sees it; client components
 * fetch from the same-origin /api/gateway/* proxy instead.
 */

import "server-only";

const BASE = process.env.GATEWAY_URL ?? "http://backend:8000";
const ADMIN_KEY = process.env.ADMIN_API_KEY ?? "";

export async function gatewayFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const url = `${BASE.replace(/\/$/, "")}${path.startsWith("/") ? path : `/${path}`}`;
  const headers = new Headers(init.headers);
  if (ADMIN_KEY) headers.set("X-Admin-Key", ADMIN_KEY);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(url, {
    ...init,
    headers,
    // Admin views are dynamic; don't let Next cache them.
    cache: "no-store",
  });
}

export async function gatewayJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await gatewayFetch(path, init);
  if (!res.ok) {
    throw new Error(`Gateway ${path} -> ${res.status}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

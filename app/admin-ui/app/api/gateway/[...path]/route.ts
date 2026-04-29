/**
 * Catch-all proxy: /api/gateway/<path> -> <gateway>/<path>
 *
 * Forwards method + body, attaches the admin key on the server so the
 * browser never possesses it. Used by client components for mutations
 * (creating tenants, revoking keys) and live polling.
 */

import { NextRequest, NextResponse } from "next/server";
import { gatewayFetch } from "@/lib/gateway";

export const dynamic = "force-dynamic";

async function proxy(req: NextRequest, ctx: { params: { path?: string[] } }) {
  const path = "/" + (ctx.params.path?.join("/") ?? "");
  const search = req.nextUrl.search;
  const body = req.method === "GET" || req.method === "HEAD" ? undefined : await req.text();
  const upstream = await gatewayFetch(path + search, {
    method: req.method,
    body,
    headers: { "Content-Type": req.headers.get("content-type") ?? "application/json" },
  });
  const contentType = upstream.headers.get("content-type") ?? "application/json";
  const text = await upstream.text();
  return new NextResponse(text, {
    status: upstream.status,
    headers: { "content-type": contentType },
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;

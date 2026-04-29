"use client";

import { useEffect, useState } from "react";

interface RecentItem {
  ts: string;
  request_id: string;
  tenant_id: string;
  requested_model: string;
  upstream_provider: string;
  upstream_model: string;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number | null;
  latency_ms: number;
  cache_status: string;
  fallback_used: boolean;
}

export default function RecentPage() {
  const [rows, setRows] = useState<RecentItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [auto, setAuto] = useState(true);

  async function refresh() {
    try {
      const r = await fetch("/api/gateway/admin/usage/recent?limit=100");
      if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
      setRows(await r.json());
      setError(null);
    } catch (e: any) { setError(String(e.message ?? e)); }
  }

  useEffect(() => {
    refresh();
    if (!auto) return;
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, [auto]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Recent requests</h1>
          <p className="text-muted text-sm">Live tail of the last 100 completions, refreshes every 5s.</p>
        </div>
        <div className="flex gap-2 items-center">
          <label className="text-sm flex items-center gap-2 text-muted">
            <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} />
            auto-refresh
          </label>
          <button className="btn" onClick={refresh}>Refresh now</button>
        </div>
      </div>

      {error && <div className="card border-red-500/40 text-red-400 text-sm">{error}</div>}

      <div className="card p-0 overflow-x-auto">
        <table>
          <thead><tr>
            <th>Time</th><th>Tenant</th><th>Requested</th><th>Provider</th><th>Upstream</th>
            <th>Tokens</th><th>Cost</th><th>Latency</th><th>Cache</th><th>Fallback</th>
          </tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={10} className="text-muted">no requests yet</td></tr>}
            {rows.map((r) => (
              <tr key={r.request_id}>
                <td className="text-muted text-xs">{new Date(r.ts).toLocaleTimeString()}</td>
                <td className="text-accent2">{r.tenant_id}</td>
                <td>{r.requested_model}</td>
                <td>{r.upstream_provider}</td>
                <td className="text-muted">{r.upstream_model}</td>
                <td>{r.prompt_tokens}/{r.completion_tokens}</td>
                <td>{r.cost_usd != null ? `$${r.cost_usd.toFixed(5)}` : "—"}</td>
                <td>{r.latency_ms.toFixed(0)} ms</td>
                <td>
                  <span className={`tag ${r.cache_status === "hit" ? "bg-emerald-500/15 text-emerald-300" : "bg-[#1a1f2a] text-muted"}`}>
                    {r.cache_status}
                  </span>
                </td>
                <td>
                  {r.fallback_used
                    ? <span className="tag bg-amber-500/15 text-amber-300">yes</span>
                    : <span className="text-muted">no</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

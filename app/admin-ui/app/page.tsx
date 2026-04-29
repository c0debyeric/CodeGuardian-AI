/**
 * Overview / dashboard. Server-rendered: aggregates the same admin API that
 * powers the rest of the console, so what you see here always matches the
 * tenant + usage tables.
 */

import { gatewayJson } from "@/lib/gateway";

interface TenantSummary { id: string; name: string; rpm_limit: number; tpm_limit: number; monthly_budget_usd: number | null }
interface UsageItem { tenant_id: string; requests: number; total_tokens: number; cost_usd: number }
interface ModelItem { upstream_model: string; requests: number; cost_usd: number }
interface ProviderHealth { name: string; healthy: boolean; circuit_state?: string; default_model?: string; last_error?: string | null }
interface HealthResponse { status: string; providers: ProviderHealth[] }

async function safe<T>(p: Promise<T>, fallback: T): Promise<T> {
  try { return await p; } catch { return fallback; }
}

export default async function OverviewPage() {
  const [tenants, usage, models, health] = await Promise.all([
    safe(gatewayJson<TenantSummary[]>("/admin/tenants"), []),
    safe(gatewayJson<UsageItem[]>("/admin/usage/by-tenant"), []),
    safe(gatewayJson<ModelItem[]>("/admin/usage/by-model"), []),
    safe(gatewayJson<HealthResponse>("/health"), { status: "unknown", providers: [] }),
  ]);

  const totalCost = usage.reduce((a, b) => a + (b.cost_usd ?? 0), 0);
  const totalRequests = usage.reduce((a, b) => a + b.requests, 0);
  const totalTokens = usage.reduce((a, b) => a + b.total_tokens, 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Overview</h1>
        <p className="text-muted text-sm">Last 24 hours, aggregated from the usage table.</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <Kpi label="Spend (24h)" value={`$${totalCost.toFixed(4)}`} />
        <Kpi label="Requests (24h)" value={totalRequests.toLocaleString()} />
        <Kpi label="Tokens (24h)" value={totalTokens.toLocaleString()} />
        <Kpi label="Tenants" value={tenants.length.toString()} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="card">
          <div className="label mb-3">Provider health</div>
          {health.providers.length === 0 ? (
            <div className="text-muted text-sm">no providers reporting</div>
          ) : (
            <table>
              <thead><tr><th>Provider</th><th>State</th><th>Default model</th></tr></thead>
              <tbody>
                {health.providers.map((p) => (
                  <tr key={p.name}>
                    <td>{p.name}</td>
                    <td>
                      <span className={`tag ${p.healthy ? "bg-emerald-500/15 text-emerald-300" : "bg-red-500/15 text-red-300"}`}>
                        {p.circuit_state ?? (p.healthy ? "ok" : "down")}
                      </span>
                    </td>
                    <td className="text-muted">{p.default_model ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="card">
          <div className="label mb-3">Top models by spend</div>
          {models.length === 0 ? (
            <div className="text-muted text-sm">no usage yet</div>
          ) : (
            <table>
              <thead><tr><th>Model</th><th>Requests</th><th>Cost</th></tr></thead>
              <tbody>
                {models
                  .sort((a, b) => b.cost_usd - a.cost_usd)
                  .slice(0, 8)
                  .map((m) => (
                    <tr key={m.upstream_model}>
                      <td>{m.upstream_model}</td>
                      <td>{m.requests}</td>
                      <td>${m.cost_usd.toFixed(4)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="card">
      <div className="label">{label}</div>
      <div className="kpi mt-1">{value}</div>
    </div>
  );
}

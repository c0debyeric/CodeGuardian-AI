import { gatewayJson } from "@/lib/gateway";

interface TenantUsage { tenant_id: string; requests: number; total_tokens: number; cost_usd: number }
interface ModelUsage { upstream_model: string; requests: number; cost_usd: number }

async function safe<T>(p: Promise<T>, fallback: T): Promise<T> {
  try { return await p; } catch { return fallback; }
}

export default async function UsagePage() {
  const [byTenant, byModel] = await Promise.all([
    safe(gatewayJson<TenantUsage[]>("/admin/usage/by-tenant"), []),
    safe(gatewayJson<ModelUsage[]>("/admin/usage/by-model"), []),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Usage</h1>
        <p className="text-muted text-sm">Aggregated over the last 24 hours.</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="card p-0 overflow-hidden">
          <div className="px-4 pt-3 pb-2 label border-b border-border">By tenant</div>
          <table>
            <thead><tr><th>Tenant</th><th>Requests</th><th>Tokens</th><th>Cost</th></tr></thead>
            <tbody>
              {byTenant.length === 0 && <tr><td colSpan={4} className="text-muted">no usage yet</td></tr>}
              {byTenant
                .sort((a, b) => b.cost_usd - a.cost_usd)
                .map((r) => (
                  <tr key={r.tenant_id}>
                    <td className="text-accent2">{r.tenant_id}</td>
                    <td>{r.requests}</td>
                    <td>{r.total_tokens.toLocaleString()}</td>
                    <td>${r.cost_usd.toFixed(4)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>

        <div className="card p-0 overflow-hidden">
          <div className="px-4 pt-3 pb-2 label border-b border-border">By upstream model</div>
          <table>
            <thead><tr><th>Model</th><th>Requests</th><th>Cost</th></tr></thead>
            <tbody>
              {byModel.length === 0 && <tr><td colSpan={3} className="text-muted">no usage yet</td></tr>}
              {byModel
                .sort((a, b) => b.cost_usd - a.cost_usd)
                .map((r) => (
                  <tr key={r.upstream_model}>
                    <td>{r.upstream_model}</td>
                    <td>{r.requests}</td>
                    <td>${r.cost_usd.toFixed(4)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

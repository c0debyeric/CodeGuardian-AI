"use client";

import { useEffect, useState } from "react";

interface TenantSummary { id: string; name: string; rpm_limit: number; tpm_limit: number; monthly_budget_usd: number | null }

export default function TenantsPage() {
  const [tenants, setTenants] = useState<TenantSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [issuedKey, setIssuedKey] = useState<{ tenant_id: string; api_key: string } | null>(null);

  // create form
  const [id, setId] = useState("");
  const [name, setName] = useState("");
  const [rpm, setRpm] = useState(60);
  const [tpm, setTpm] = useState(100000);

  async function refresh() {
    setLoading(true); setError(null);
    try {
      const r = await fetch("/api/gateway/admin/tenants");
      if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
      setTenants(await r.json());
    } catch (e: any) { setError(String(e.message ?? e)); }
    finally { setLoading(false); }
  }

  useEffect(() => { refresh(); }, []);

  async function createTenant(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const r = await fetch("/api/gateway/admin/tenants", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, name, rpm_limit: rpm, tpm_limit: tpm }),
    });
    if (!r.ok) { setError(`${r.status}: ${await r.text()}`); return; }
    const data = await r.json();
    setIssuedKey({ tenant_id: data.tenant_id, api_key: data.api_key });
    setId(""); setName("");
    refresh();
  }

  async function revoke(tenantId: string) {
    if (!confirm(`Revoke ALL keys for ${tenantId}? This is immediate.`)) return;
    const r = await fetch(`/api/gateway/admin/tenants/${tenantId}/keys`, { method: "DELETE" });
    if (!r.ok) { setError(`${r.status}: ${await r.text()}`); return; }
    refresh();
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Tenants</h1>
        <p className="text-muted text-sm">Create, list, and revoke API keys.</p>
      </div>

      {issuedKey && (
        <div className="card border-accent/40 bg-accent/5">
          <div className="label text-accent">New key for {issuedKey.tenant_id} — shown once</div>
          <div className="mt-2 text-sm break-all select-all bg-bg p-3 rounded border border-border">
            {issuedKey.api_key}
          </div>
          <div className="mt-2 flex gap-2">
            <button className="btn" onClick={() => navigator.clipboard.writeText(issuedKey.api_key)}>Copy</button>
            <button className="btn" onClick={() => setIssuedKey(null)}>Dismiss</button>
          </div>
        </div>
      )}

      <form onSubmit={createTenant} className="card grid grid-cols-5 gap-3 items-end">
        <div className="col-span-1"><label className="label">ID</label><input className="input mt-1" required value={id} onChange={(e) => setId(e.target.value)} placeholder="acme" /></div>
        <div className="col-span-1"><label className="label">Name</label><input className="input mt-1" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Acme Corp" /></div>
        <div><label className="label">RPM</label><input type="number" className="input mt-1" value={rpm} onChange={(e) => setRpm(parseInt(e.target.value))} /></div>
        <div><label className="label">TPM</label><input type="number" className="input mt-1" value={tpm} onChange={(e) => setTpm(parseInt(e.target.value))} /></div>
        <button type="submit" className="btn btn-primary">Create + issue key</button>
      </form>

      {error && <div className="card border-red-500/40 text-red-400 text-sm">{error}</div>}

      <div className="card p-0 overflow-hidden">
        <table>
          <thead><tr><th>ID</th><th>Name</th><th>RPM</th><th>TPM</th><th>Budget</th><th></th></tr></thead>
          <tbody>
            {loading && <tr><td colSpan={6} className="text-muted">loading…</td></tr>}
            {!loading && tenants.length === 0 && <tr><td colSpan={6} className="text-muted">no tenants yet</td></tr>}
            {tenants.map((t) => (
              <tr key={t.id}>
                <td className="text-accent2">{t.id}</td>
                <td>{t.name}</td>
                <td>{t.rpm_limit}</td>
                <td>{t.tpm_limit.toLocaleString()}</td>
                <td>{t.monthly_budget_usd != null ? `$${t.monthly_budget_usd}` : <span className="text-muted">—</span>}</td>
                <td><button className="btn btn-danger" onClick={() => revoke(t.id)}>Revoke keys</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

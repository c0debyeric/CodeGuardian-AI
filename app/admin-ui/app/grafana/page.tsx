/**
 * Embedded Grafana dashboard.
 *
 * We don't reimplement charts in React — Grafana already has the right tools
 * (templating, range picker, drilldowns). Anonymous viewer access must be
 * enabled on the Grafana side; in prod, an auth proxy fronts both apps so
 * the iframe inherits the user's session.
 */

const GRAFANA_URL = process.env.NEXT_PUBLIC_GRAFANA_URL ?? "http://localhost:3001";
const DASHBOARD_UID = process.env.NEXT_PUBLIC_GRAFANA_DASHBOARD_UID ?? "llm-gateway";

export default function GrafanaPage() {
  const src = `${GRAFANA_URL}/d/${DASHBOARD_UID}/llm-gateway?orgId=1&kiosk&theme=dark`;
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Cost & latency dashboard</h1>
        <p className="text-muted text-sm">
          Backed by the same Prometheus metrics this gateway emits. Drill in for per-tenant slicing.
        </p>
      </div>
      <div className="card p-0 overflow-hidden">
        <iframe
          src={src}
          title="LLM Gateway Grafana dashboard"
          className="w-full h-[calc(100vh-220px)] bg-bg"
          frameBorder={0}
        />
      </div>
      <div className="text-xs text-muted">
        Iframe target: <code>{src}</code>. Configure with{" "}
        <code>NEXT_PUBLIC_GRAFANA_URL</code> and{" "}
        <code>NEXT_PUBLIC_GRAFANA_DASHBOARD_UID</code>.
      </div>
    </div>
  );
}

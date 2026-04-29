# LLM Gateway — Admin UI

Lightweight Next.js admin console for the LLM Gateway. Built with the App Router,
TypeScript, and Tailwind. Server-side proxies the gateway admin API so the
`X-Admin-Key` never reaches the browser.

## Pages

- `/` — overview (KPIs, provider health, top models)
- `/tenants` — create, list, revoke API keys
- `/usage` — aggregate spend + tokens by tenant and by model
- `/recent` — live tail of recent completions, auto-refreshes every 5 s
- `/grafana` — embedded Grafana dashboard (cost & latency)

## Run

```bash
npm install
GATEWAY_URL=http://localhost:8000 \
ADMIN_API_KEY=dev-admin-key-change-me \
npm run dev
```

Visit http://localhost:3000.

In production both `GATEWAY_URL` and `ADMIN_API_KEY` come from Kubernetes secrets;
see `app/helm-chart/admin-ui/`.

<p align="center">
  <img src="https://img.shields.io/badge/AWS-Bedrock-FF9900?style=for-the-badge&logo=amazon-aws&logoColor=white" alt="AWS Bedrock"/>
  <img src="https://img.shields.io/badge/OpenAI-API_Compatible-412991?style=for-the-badge&logo=openai&logoColor=white" alt="OpenAI Compatible"/>
  <img src="https://img.shields.io/badge/Kubernetes-EKS-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white" alt="Kubernetes"/>
  <img src="https://img.shields.io/badge/Terraform-IaC-7B42BC?style=for-the-badge&logo=terraform&logoColor=white" alt="Terraform"/>
  <img src="https://img.shields.io/badge/GitOps-ArgoCD-EF7B4D?style=for-the-badge&logo=argo&logoColor=white" alt="ArgoCD"/>
  <img src="https://img.shields.io/badge/Observability-OpenTelemetry-425CC7?style=for-the-badge&logo=opentelemetry&logoColor=white" alt="OTel"/>
</p>

<h1 align="center">LLM Gateway</h1>

<p align="center">
  <strong>A multi-provider LLM inference platform — built like internal AI infrastructure at a real company.</strong>
</p>

<p align="center">
  <em>One OpenAI-compatible API in front of AWS Bedrock and OpenAI, with per-tenant quotas, automatic provider failover,
  PII guardrails, semantic caching, full cost attribution, and end-to-end OpenTelemetry tracing — running on EKS via GitOps.</em>
</p>

---

## What this project actually solves

When a company starts using LLMs in production, the same problems show up regardless of which model they pick:

- **Provider lock-in** — code calls `openai.chat.completions.create(...)` directly, so switching to Bedrock or Anthropic requires touching every service.
- **No cost visibility** — finance can't tell which team or feature is burning the AWS Bedrock bill.
- **No rate limiting per consumer** — one runaway notebook hammers the API and breaks production for everyone else.
- **No fallback story** — Bedrock has a regional outage, the whole product is down.
- **No PII boundary** — random user inputs are flowing straight to a third-party model.
- **No cache** — the same five prompts are generating Claude calls all day.

This project is the **platform layer that solves all of those at once**. Applications speak the OpenAI Chat Completions API to the gateway and get all of those features for free.

---

## What it does

| Capability | How |
|---|---|
| **OpenAI-compatible API** | `POST /v1/chat/completions` — drop-in for the OpenAI SDK. Migrate any existing app by changing the base URL. |
| **Multi-provider routing** | Ships with AWS Bedrock (Claude 3.5/4) and OpenAI (GPT-4o family). Add a provider by implementing one ABC. |
| **Automatic failover** | Per-provider circuit breakers (closed → open → half-open). On retryable errors the router transparently retries on the next provider. |
| **Per-tenant API keys + quotas** | Sliding-window RPM and TPM limits. Per-tenant model allowlists. Optional per-tenant monthly budget. |
| **Cost attribution** | Every request is priced from a maintained price table; cost per tenant / per model / per feature is exposed via Prometheus and queryable in Grafana. |
| **Semantic cache** | Deterministic-key cache for now (extensible to embeddings). Cuts upstream cost on repeated prompts. Bounded LRU + TTL. |
| **PII guardrails** | Inbound messages are scanned for SSN, credit card, email, US phone, etc. Detected types are redacted before the prompt ever leaves the cluster, and emitted as a metric for audit. |
| **Distributed state** | Rate limiter and cache are pluggable: in-memory by default for dev, Redis in prod (sliding-window via sorted sets). |
| **Usage history** | Every completion is persisted to Postgres (request id, tenant, model, tokens, cost, latency, fallback?, cache?). Powers admin endpoints and dashboards. |
| **OpenTelemetry tracing** | OTel auto-instrumentation for FastAPI / httpx / botocore. Every span is enriched with the GenAI semantic-conventions attributes (`gen_ai.system`, `gen_ai.response.model`, `gen_ai.usage.input_tokens`, …) plus gateway-specific attrs. |
| **Prometheus metrics** | LLM-specific metrics — request rate, P95 latency by provider, tokens by direction, USD cost, cache hit rate, guardrail events, provider failures. |
| **Admin API** | Create/list tenants, view usage by tenant or by model, all guarded by an `X-Admin-Key` separate from tenant keys. |

---

## Why I built it this way

| Decision | Rationale |
|---|---|
| **OpenAI-compatible API** | Zero migration cost for any team already using the OpenAI SDK. The most realistic adoption path for an internal platform. |
| **Provider abstraction as an ABC** | Adding the next provider (Anthropic direct, Azure OpenAI, Google) is a focused PR — implement four methods. No router changes. |
| **Routes for `auto`/`cheapest`/`fastest` aliases, but concrete models stay literal** | If a caller asks for `gpt-4o`, they get GPT-4o or a 503 — never silently get Claude. Quietly substituting models breaks evaluations and cost forecasts. |
| **Separate sliding-window rate limit (RPM) from token limit (TPM)** | These are independent failure modes — a small number of huge prompts can blow the TPM budget without ever hitting RPM. |
| **Cost is computed in the gateway, not pulled from provider invoices** | Real-time per-request cost, no day-late bill reconciliation. Token counts come back in every provider response. |
| **Sliding-window via Redis sorted sets** | O(log N), atomic via Lua script, no clock-drift issues, scales to multiple gateway pods. |
| **Pluggable backends with in-memory defaults** | The full test suite runs in-process with `aiosqlite::memory:` and dict-based stores. No Docker required to develop. |
| **Lifespan handler over deprecated `on_event`** | Aligned with current FastAPI guidance; the lifespan also drives `init_db()` so schema is ready before the first request. |
| **GenAI OpenTelemetry semantic conventions** | Future-proof — vendors are converging on `gen_ai.*` attributes. Our spans drop straight into Tempo / Datadog / Honeycomb LLM views. |

---

## Architecture

```mermaid
flowchart LR
    subgraph Clients["Application teams"]
        A1["Backend service<br/>(OpenAI SDK)"]
        A2["Notebook"]
        A3["Internal tool"]
    end

    subgraph Gateway["LLM Gateway (FastAPI on EKS)"]
        Auth["API key auth<br/>+ RPM/TPM limits"]
        Guard["PII guardrails"]
        Cache["Semantic cache"]
        Router["Router<br/>+ circuit breakers"]
        Cost["Pricing + usage<br/>recording"]
    end

    subgraph State["Cluster state"]
        Redis[("Redis<br/>(rate limit + cache)")]
        Postgres[("RDS Postgres<br/>(usage history)")]
    end

    subgraph Providers["Upstream providers"]
        Bedrock["AWS Bedrock<br/>Claude 3.5/4"]
        OpenAI["OpenAI<br/>GPT-4o family"]
    end

    subgraph Telemetry["Observability"]
        Otel["OTel Collector"]
        Prom["Prometheus"]
        Graf["Grafana<br/>(cost dashboard)"]
    end

    A1 & A2 & A3 -->|"POST /v1/chat/completions"| Auth
    Auth --> Guard --> Cache --> Router --> Cost
    Router -->|primary| Bedrock
    Router -.->|fallback on retryable error| OpenAI
    Auth <--> Redis
    Cache <--> Redis
    Cost --> Postgres
    Gateway -.->|spans + metrics| Otel
    Otel --> Prom --> Graf
```

### Request lifecycle

1. **Auth** — `Authorization: Bearer sk-<tenant>-...` is hashed (SHA-256) and looked up. Anonymous mode is supported for dev.
2. **Quotas** — Sliding-window RPM check first (rejects with 429 + `Retry-After`). Token budget pre-check.
3. **Model allowlist** — If the tenant isn't allowed to call `gpt-4o`, 403 before any provider is contacted.
4. **Guardrails** — If enabled, messages are regex-scanned for PII; matches are replaced with `[REDACTED-{type}]` and counted as a Prometheus event.
5. **Cache** — Deterministic key over (model, canonicalized messages, sampling params). Hits return immediately and are recorded as `cache="hit"`.
6. **Routing** — Concrete model → providers that serve it. Aliases (`auto`/`cheapest`/`fastest`) → the price-ranked or default chain. Fallback walks the chain on retryable errors only.
7. **Charge + persist** — Token usage is debited against the tenant's TPM budget and a `UsageRecord` is written to Postgres.
8. **Telemetry** — Counters, histograms, and OTel `gen_ai.*` span attributes are emitted on the way out.

---

## API

### Chat completions (OpenAI-compatible)

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-demo-localdev-rotateme" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "Write a haiku about Kubernetes."}]
  }' | jq
```

Response (truncated):

```jsonc
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "model": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
  "choices": [{ "message": { "role": "assistant", "content": "..." }, "finish_reason": "stop" }],
  "usage": { "prompt_tokens": 18, "completion_tokens": 22, "total_tokens": 40 },
  "gateway": {
    "provider": "bedrock",
    "upstream_model": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "latency_ms": 612,
    "cache": "miss",
    "fallback_used": false,
    "attempts": ["bedrock"],
    "cost_usd": 0.000384
  }
}
```

The `gateway` object is the gateway's value-add — provider used, fallback story, real cost, real latency.

### Models

```
GET /v1/models           # OpenAI-compatible model list (with aliases)
GET /health              # Provider health states + circuit-breaker status
GET /metrics             # Prometheus scrape endpoint
```

### Admin (requires `X-Admin-Key`)

```
POST /admin/tenants                  # Create tenant + return plaintext API key (shown once)
GET  /admin/tenants                  # List tenants and their limits
GET  /admin/usage/by-tenant?since=   # Aggregate cost / tokens per tenant
GET  /admin/usage/by-model?since=    # Aggregate cost / tokens per upstream model
```

---

## Quick start (local)

Requires Docker and `uv` (or Python 3.13).

```bash
# 1. Bring up backend + Redis + Postgres + OTel collector
docker compose up --build

# 2. (in another shell) hit the gateway
curl -s http://localhost:8000/v1/models \
  -H "Authorization: Bearer sk-demo-localdev-rotateme" | jq
```

Run the test suite:

```bash
cd app/backend
uv sync
uv run pytest -v
```

35+ tests cover routing, fallback, circuit breakers, auth, RPM/TPM limits, admin endpoints, usage persistence, PII guardrails, semantic cache, and Prometheus metrics — all in-process, no Docker required.

---

## Deploy to AWS

End-to-end bootstrap is automated:

```bash
python RUNME.py preflight       # Verify aws/kubectl/terraform/helm/docker
python RUNME.py terraform --env dev   # VPC + EKS + RDS + ECR + Secrets Manager
python RUNME.py images          # Build + push backend image to ECR
python RUNME.py deploy          # Apply ArgoCD root-app; everything syncs from Git
python RUNME.py validate        # Hit /health and confirm provider state
```

What you get:
- **VPC** with public / private / database subnets across 3 AZs
- **EKS 1.34** with Karpenter autoscaling and IRSA for Bedrock access
- **RDS Postgres** in the database subnets (usage history)
- **In-cluster Redis** (Bitnami chart, ArgoCD-managed)
- **ECR** for the backend image
- **Secrets Manager** entries for DB creds and the admin API key, surfaced via External Secrets Operator
- **ArgoCD** as the single sync target — every workload (gateway, Redis, observability stack, dashboards) is GitOps-driven from `argocd/`
- **Prometheus + Grafana + Loki + OTel collector** in the `monitoring` namespace

When you're done:

```bash
python RUNME.py destroy --env dev
```

---

## Repository layout

```
.
├── app/
│   ├── backend/               # FastAPI gateway (this is the project)
│   │   ├── src/
│   │   │   ├── api/           # FastAPI routes + OpenAI-compatible schemas
│   │   │   ├── auth/          # API keys, tenants, sliding-window rate limiter
│   │   │   ├── core/          # Settings (pydantic-settings), logging
│   │   │   ├── middleware/    # PII guardrails, semantic cache
│   │   │   ├── observability/ # Prometheus metrics + OTel GenAI attrs
│   │   │   ├── providers/     # Provider ABC, Bedrock, OpenAI, registry, pricing
│   │   │   ├── routing/       # Routing policies + fallback router
│   │   │   └── usage/         # SQLAlchemy usage table + repository
│   │   └── tests/             # 35+ tests, all in-process
│   └── helm-chart/
│       └── backend/           # Production Helm chart (HPA, PDB, NetworkPolicy, ServiceMonitor, ExternalSecret)
├── argocd/
│   ├── apps/codeguardian/     # ArgoCD Applications: gateway, Redis, namespace
│   ├── dashboards/            # Grafana dashboard JSON (LLM cost + latency)
│   └── root-app.yaml          # App-of-apps entry point
├── terraform/
│   ├── modules/{networking,eks,rds,ecr,acm,secrets-manager,vpc-endpoints,s3}/
│   └── environments/{dev,prod}/
├── docker-compose.yml         # Local stack: gateway + Redis + Postgres + OTel
└── RUNME.py                   # Bootstrap CLI (typer + rich)
```

---

## Roadmap

The platform pieces below are designed-for but not yet implemented. They're called out so the architecture choices above make sense.

- **Real upstream streaming** — `stream=true` already returns a valid OpenAI-compatible `text/event-stream` (the OpenAI Python SDK works against it unmodified). It currently buffers the upstream response and chunks it into deltas; per-provider native streaming (Bedrock `invoke_model_with_response_stream`, OpenAI `stream=true`) is a drop-in next step that won't change the wire shape.
- **Production-grade embedder** — `SEMANTIC_CACHE_MODE=semantic` enables embedding + cosine NN matching today, backed by a dependency-free hashing embedder. Swap `set_embedder(...)` for an OpenAI / Bedrock Titan / sentence-transformers model and the cache code stays the same.
- **Admin UI** — REST is in place; a small React/Next.js dashboard for tenants, keys, and live cost is the natural follow-up.
- **WAF / rate limit at the edge** — currently relies on application-layer limits.

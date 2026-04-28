<p align="center">
  <img src="https://img.shields.io/badge/AWS-Bedrock-FF9900?style=for-the-badge&logo=amazon-aws&logoColor=white" alt="AWS Bedrock"/>
  <img src="https://img.shields.io/badge/Kubernetes-EKS-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white" alt="Kubernetes"/>
  <img src="https://img.shields.io/badge/Terraform-IaC-7B42BC?style=for-the-badge&logo=terraform&logoColor=white" alt="Terraform"/>
  <img src="https://img.shields.io/badge/Python-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/GitOps-ArgoCD-EF7B4D?style=for-the-badge&logo=argo&logoColor=white" alt="ArgoCD"/>
</p>

<h1 align="center">🛡️ CodeGuardian AI</h1>

<p align="center">
  <strong>AI-Powered Security Code Reviewer | Production-Grade on AWS EKS</strong>
</p>

<p align="center">
  <em>Catch vulnerabilities before deployment with real-time, context-aware security analysis powered by AWS Bedrock Claude</em>
</p>

---

## 🎯 What Is This?

**CodeGuardian AI** is a **production-grade AI security platform** deployed on AWS EKS. Developers submit code (Python, JavaScript, Terraform), and the system returns real-time security findings with:

- ⚠️ **Severity Ratings** (Critical → Info)
- 📍 **Exact Line Numbers**  
- 🔧 **Fix Suggestions** with code examples
- 📚 **CWE/OWASP Mappings** for compliance

---

## 💡 Why I Built This

Most AI demos stop at "call an API and display the result." This project proves I can take an AI capability and deploy it as a **production-ready platform service** — with the same infrastructure, security, and observability standards I'd use at work.

Every component reflects a deliberate engineering decision:
- **Why EKS over Lambda?** Real workloads need persistent connections, autoscaling control, and sidecar observability — not cold starts.
- **Why ArgoCD over kubectl apply?** GitOps ensures every deployment is auditable, reproducible, and rollback-ready.
- **Why 6 layers of security?** Defense in depth isn't optional when you're processing untrusted code input through an LLM.
- **Why Terraform modules?** The same infrastructure patterns I use at enterprise scale (~200 AWS accounts) applied to a focused project.

**This is not a tutorial project. It's a platform I'd deploy at work.**

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🤖 **AI-Powered Analysis** | Claude Sonnet 4.5 via AWS Bedrock for intelligent vulnerability detection |
| 🏗️ **Infrastructure as Code** | 100% Terraform-managed AWS infrastructure with modular design |
| ☸️ **Kubernetes Native** | Deployed on EKS with auto-scaling via Karpenter |
| 🔐 **Zero-Trust Security** | EKS Pod Identity, Network Policies, Pod Security Standards, runtime monitoring |
| 📦 **GitOps Deployment** | ArgoCD for declarative, Git-driven deployments |
| 📊 **Full Observability** | Prometheus + Grafana + Loki + OpenTelemetry stack |
| 🚀 **CI/CD Pipeline** | GitHub Actions → Security scans → ECR → Auto-deploy |

---

## 🏛️ Architecture

### High-Level Infrastructure

```mermaid
flowchart LR
    subgraph Internet["🌐 Internet"]
        User["👤 Developer"]
    end
    
    subgraph AWS["☁️ AWS Cloud (us-east-2)"]
        subgraph Public["Public Subnets"]
            ALB["⚖️ ALB"]
            NAT["🔀 NAT<br/>Gateway"]
        end
        
        subgraph Private["Private Subnets - EKS Cluster v1.34"]
            FastAPI["🔒 FastAPI<br/>Backend"]
            Streamlit["🎨 Streamlit<br/>UI"]
            ArgoCD["📦 ArgoCD"]
            Prom["📊 Prometheus"]
            Grafana["📈 Grafana"]
            Loki["📋 Loki"]
        end
        
        subgraph Database["Database Subnets"]
            RDS[("🗄️ PostgreSQL<br/>RDS")]
        end
        
        subgraph Managed["AWS Managed Services"]
            Bedrock["🤖 Bedrock<br/>Claude 4.5"]
            Secrets["🔑 Secrets<br/>Manager"]
            ECR["🐳 ECR<br/>Registry"]
            S3["📦 S3<br/>Buckets"]
        end
        
        subgraph Endpoints["VPC Endpoints"]
            ECREP["ECR Interface<br/>$43/mo"]
            S3EP["S3 Gateway<br/>FREE"]
        end
    end
    
    User -->|HTTPS| ALB
    ALB --> FastAPI
    ALB --> Streamlit
    FastAPI --> RDS
    FastAPI -->|via NAT| Bedrock
    FastAPI -->|via NAT| Secrets
    FastAPI --> Prom
    FastAPI --> Loki
    Prom --> Grafana
    Loki --> Grafana
    ArgoCD -.->|GitOps| FastAPI
    ArgoCD -.->|GitOps| Streamlit
    Private -->|Pull Images| ECREP
    ECREP --> ECR
    Private --> S3EP
    S3EP --> S3
    
    classDef userStyle fill:#4A90E2,stroke:#2E5C8A,stroke-width:2px,color:#fff
    classDef awsService fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef compute fill:#009688,stroke:#00695C,stroke-width:2px,color:#fff
    classDef database fill:#527FFF,stroke:#3D5FBF,stroke-width:2px,color:#fff
    classDef security fill:#DD344C,stroke:#A32535,stroke-width:2px,color:#fff
    classDef platform fill:#7B42BC,stroke:#5A2F8F,stroke-width:2px,color:#fff
    
    class User userStyle
    class ALB,NAT,ECREP,S3EP awsService
    class FastAPI,Streamlit compute
    class RDS database
    class Bedrock,Secrets,ECR,S3 security
    class ArgoCD,Prom,Grafana,Loki platform
```

### 🔄 Request Flow & Data Path

```mermaid
sequenceDiagram
    participant User as 👤 Developer
    participant ALB as ⚖️ ALB
    participant FastAPI as 🔒 FastAPI Pod
    participant RDS as 🗄️ PostgreSQL
    participant ESO as 🔐 ESO
    participant Secrets as 🔑 Secrets Mgr
    participant Bedrock as 🤖 Bedrock AI
    participant Prom as 📊 Prometheus
    participant Loki as 📋 Loki
    
    User->>ALB: POST /analyze (code)
    ALB->>FastAPI: Route request
    
    Note over FastAPI,ESO: Startup: Fetch DB credentials
    ESO->>Secrets: Get credentials (via NAT)
    Secrets-->>ESO: Return secrets
    ESO-->>FastAPI: Inject as env vars
    
    FastAPI->>RDS: Check analysis cache
    RDS-->>FastAPI: Cache miss
    
    FastAPI->>Bedrock: Analyze code (via NAT)
    Note over Bedrock: Claude Sonnet 4.5<br/>Security Analysis
    Bedrock-->>FastAPI: Return findings
    
    FastAPI->>RDS: Store analysis results
    FastAPI->>Prom: Record metrics (latency, tokens)
    FastAPI->>Loki: Ship structured logs
    
    FastAPI-->>ALB: JSON response
    ALB-->>User: Security findings
    
    Note over Prom,Loki: Observability Stack<br/>Grafana dashboards<br/>Alertmanager rules
```

### 💰 Cost-Optimized VPC Endpoints Strategy

| Service | Access Method | Monthly Cost | Rationale |
|---------|---------------|--------------|-----------|
| **S3** | Gateway Endpoint | **$0** | Free - always include |
| **ECR** | Interface Endpoint | **~$43** | Multi-GB image pulls justify cost |
| **Bedrock** | NAT Gateway | **~$2-10** | API payloads <50KB, infrequent |
| **Secrets Mgr** | NAT Gateway | **<$1** | Fetched once at pod startup |
| **Other AWS APIs** | NAT Gateway | **Included** | Low volume traffic |

> **Total VPC Endpoint Savings:** ~$64/month vs. having endpoints for all services

---

## 🛠️ Technology Stack

### Infrastructure Layer
| Category | Technology | Purpose |
|:---------|:-----------|:--------|
| **IaC** | Terraform | Modular AWS provisioning |
| **Compute** | EKS Auto Mode | Managed Kubernetes with Karpenter |
| **Networking** | VPC + VPC CNI | Isolated network with native NetworkPolicy |
| **Storage** | S3 (encrypted) | Document & state storage |
| **Secrets** | AWS Secrets Manager + ESO | Zero hardcoded credentials |
| **Certificates** | ACM + cert-manager | TLS everywhere |

### Platform Layer (Kubernetes Add-ons)
| Category | Components |
|:---------|:-----------|
| **GitOps** | ArgoCD (App of Apps pattern) |
| **Security** | Kyverno • Falco • Trivy |
| **Observability** | Prometheus • Grafana • Loki • Tempo |
| **Networking** | AWS Load Balancer Controller • VPC CNI |
| **Operations** | Velero • Kubecost |

### Application Layer
| Component | Technology |
|:----------|:-----------|
| **Backend API** | Python 3.13 + FastAPI |
| **Frontend UI** | Streamlit |
| **AI Engine** | AWS Bedrock (Claude Sonnet 4.5) |
| **Logging** | Structlog (JSON format) |
| **Testing** | Pytest + pytest-asyncio |

---

## 🔒 Security Model (Defense in Depth)

This project implements **6 layers of security controls**:

```
┌─────────────────────────────────────────────────────────────────┐
│  🌐 NETWORK         VPC isolation • Security Groups            │
│                     VPC CNI Network Policies • Private subnets │
├─────────────────────────────────────────────────────────────────┤
│  🔑 IDENTITY        EKS Pod Identity • Least-privilege IAM     │
│                     RBAC • No long-lived credentials           │
├─────────────────────────────────────────────────────────────────┤
│  🔐 DATA            KMS encryption at rest • TLS in transit    │
│                     Secrets Manager • No secrets in code       │
├─────────────────────────────────────────────────────────────────┤
│  🛡️ RUNTIME         Pod Security Standards • Falco monitoring  │
│                     Non-root containers • Read-only filesystems│
├─────────────────────────────────────────────────────────────────┤
│  📦 SUPPLY CHAIN    Trivy scanning in CI • Signed images       │
│                     Kyverno blocking unsigned deployments      │
├─────────────────────────────────────────────────────────────────┤
│  📊 AUDIT           CloudTrail • Centralized logging (Loki)    │
│                     Prometheus alerting • Full traceability    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📂 Project Structure

```
CodeGuardian-AI/
├── 📁 app/
│   ├── backend/              # FastAPI security analysis service
│   │   ├── src/
│   │   │   ├── api/          # Routes, schemas, endpoints
│   │   │   ├── services/     # Bedrock client, analyzer logic
│   │   │   └── core/         # Config, prompts, settings
│   │   ├── tests/            # Unit & integration tests
│   │   └── Dockerfile        # Multi-stage production build
│   ├── frontend/             # Streamlit UI application
│   └── helm-chart/           # Kubernetes deployment charts
│
├── 📁 terraform/
│   ├── modules/
│   │   ├── networking/       # VPC, subnets, NAT, flow logs
│   │   ├── eks/              # EKS cluster, Pod Identity, Helm addons
│   │   ├── ecr/              # Container registry
│   │   ├── secrets-manager/  # Secrets management
│   │   └── ...               # Additional modules
│   └── environments/         # dev.tfvars, prod.tfvars
│
├── 📁 docs/                  # Architecture & planning docs
├── 📄 docker-compose.yml     # Local development stack
└── 📄 Makefile               # Common automation commands
```

---

## 🚀 Quick Start

### Prerequisites
- AWS Account with Bedrock access (Claude enabled)
- Docker & Docker Compose
- Terraform ≥ 1.0
- kubectl & AWS CLI configured

### Local Development

```bash
# Clone the repository
git clone https://github.com/yourusername/CodeGuardian-AI.git
cd CodeGuardian-AI

# Set up environment variables
cp .env.example .env
# Edit .env with your AWS credentials

# Start the application
docker-compose up

# Access the services
# Backend API:  http://localhost:8000/docs
# Frontend UI:  http://localhost:8501
```

### Deploy to AWS

```bash
# Initialize Terraform
cd terraform
terraform init

# Deploy infrastructure
terraform plan -var-file=environments/dev.tfvars
terraform apply -var-file=environments/dev.tfvars

# Configure kubectl
aws eks update-kubeconfig --name codeguardian-dev

# Verify deployment
kubectl get nodes
kubectl get pods -A
```

---

## 📡 API Reference

### `POST /analyze` — Analyze Code for Vulnerabilities

**Request:**
```json
{
  "code": "user_id = request.args.get('id')\nquery = f'SELECT * FROM users WHERE id = {user_id}'",
  "language": "python",
  "context": "This is a Flask web application"
}
```

**Response:**
```json
{
  "findings": [
    {
      "id": "f1",
      "severity": "CRITICAL",
      "line_start": 2,
      "line_end": 2,
      "vulnerability_type": "SQL Injection",
      "cwe_id": "CWE-89",
      "owasp_category": "A03:2021-Injection",
      "title": "SQL Injection vulnerability detected",
      "description": "User input directly concatenated into SQL query",
      "recommendation": "Use parameterized queries",
      "fix_example": "cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))"
    }
  ],
  "summary": {
    "total": 1,
    "critical": 1,
    "high": 0,
    "medium": 0,
    "low": 0
  },
  "metadata": {
    "language_detected": "python",
    "lines_analyzed": 2,
    "scan_time_ms": 1250,
    "model_used": "claude-sonnet-4-5"
  }
}
```

### `GET /health` — Health Check
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "bedrock_connected": true
}
```

---

## 📊 Observability Stack

| Component | Tool | Purpose |
|:----------|:-----|:--------|
| **Metrics** | Prometheus + Grafana | Resource utilization, API latency, error rates |
| **Logs** | Loki | Centralized log aggregation with LogQL |
| **Traces** | OpenTelemetry → Tempo | Distributed request tracing |
| **Alerts** | Alertmanager | Incident notification & escalation |
| **Runtime** | Falco | Security event detection |

---

## 🎓 Skills Demonstrated

### ☁️ Cloud & Infrastructure
- **AWS Services:** EKS, Bedrock, VPC, IAM, Secrets Manager, ECR, ALB, S3, KMS
- **Infrastructure as Code:** Terraform with modular design — same patterns used across ~200 production accounts
- **Kubernetes:** Deployments, Services, RBAC, Network Policies, Helm charts, Karpenter autoscaling

### 🤖 AI / LLM Integration
- **Model Integration:** AWS Bedrock (Claude Sonnet 4.5) with structured prompt engineering
- **Prompt Design:** Security-domain system prompts producing structured JSON with CWE/OWASP mappings
- **Production Patterns:** Error handling, retry logic, response validation, token tracking

### 🔐 Security & DevSecOps
- **Zero-Trust Architecture:** EKS Pod Identity, pod-level IAM, no static credentials
- **Policy Enforcement:** Kyverno admission policies, Pod Security Standards
- **Runtime Security:** Falco syscall monitoring for anomaly detection
- **Supply Chain Security:** Trivy container scanning, Checkov IaC scanning, multi-stage CI gates

### 📊 Observability & SRE
- **Metrics:** Prometheus with custom application metrics, Grafana dashboards
- **Logging:** Structured JSON logging (structlog) → Loki with LogQL
- **Tracing:** OpenTelemetry auto-instrumentation → Tempo
- **Alerting:** Alertmanager with escalation rules

### 🚀 CI/CD & GitOps
- **GitOps:** ArgoCD with App of Apps pattern — single source of truth
- **Pipelines:** GitHub Actions with security-first gates (Gitleaks, Semgrep, Snyk, Checkov, Trivy)
- **Container Registry:** ECR with automated vulnerability scanning on push

---

<p align="center">
  <a href="#-what-is-this">Back to Top</a>
</p>

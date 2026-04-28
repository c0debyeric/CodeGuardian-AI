# CodeGuardian AI - Build Order

A phased approach to building the production-grade RAG application on EKS.

---

## 🎯 Build Philosophy

**Principle:** Build incrementally with validation gates. Each phase must be working before moving to the next.

```
Foundation → Platform → Application → Pipeline → Hardening → Documentation
```

---

## 📋 Phase Overview

| Phase | Name | Duration | Outcome |
|-------|------|----------|---------|
| 0 | Local Development | 2-3 days | App works locally with Bedrock |
| 1 | Foundation Infrastructure | 3-4 days | VPC + EKS cluster running |
| 2 | Platform Bootstrap | 2-3 days | ArgoCD + basic observability |
| 3 | Security Foundation | 2-3 days | Secrets, IRSA, Network Policies |
| 4 | Application Deployment | 2-3 days | App running on EKS via ArgoCD |
| 5 | Observability Stack | 2-3 days | Full metrics, logs, traces |
| 6 | Security Hardening | 2-3 days | Falco, Kyverno, scanning |
| 7 | CI/CD Pipeline | 2-3 days | GitHub Actions → ECR → ArgoCD |
| 8 | Testing & Validation | 2-3 days | Load testing, chaos testing |
| 9 | Documentation & Demo | 1-2 days | README, architecture diagrams |

**Total Estimated Time:** 3-4 weeks (part-time) or 2 weeks (full-time)

---

## 🔨 Phase 0: Local Development Environment ✅

**Goal:** Application working locally before any cloud infrastructure.

### Tasks
- [x] **0.1** Set up Python environment (uv)
- [x] **0.2** Build FastAPI backend skeleton
  - Health check endpoint (`/health`)
  - Code analysis endpoint (`/analyze`)
  - Bedrock client integration
- [x] **0.3** Build Streamlit UI
  - Code input textarea
  - Results display with severity highlighting
- [x] **0.4** Test Bedrock integration locally
  - Configure AWS credentials
  - Validate Claude Sonnet 4.5 responses
- [x] **0.5** Dockerize both services
  - Multi-stage Dockerfile for FastAPI
  - Dockerfile for Streamlit
  - docker-compose for local testing
- [x] **0.6** Unit tests (23 tests passing)

### Validation Gate
```bash
# Both containers running and communicating
docker-compose up
curl http://localhost:8000/health  # Returns 200
# Streamlit accessible at http://localhost:8501
# Code analysis returns Bedrock response
```

### Deliverables
- `app/backend/` - FastAPI application
- `app/frontend/` - Streamlit application
- `docker-compose.yml` - Local development stack
- Working Bedrock integration

---

## 🏗️ Phase 1: Foundation Infrastructure

**Goal:** Core AWS infrastructure provisioned via Terraform.

### Tasks
- [x] **1.1** Terraform project structure
  ```
  terraform/
  ├── main-caller.tf
  ├── variables.tf
  ├── outputs.tf
  ├── environments/
  │   ├── dev.tfvars
  │   └── prod.tfvars
  └── modules/
      ├── networking/
      ├── eks/
      ├── s3-state/
      └── ...
  ```
- [x] **1.2** S3 backend for Terraform state
  - S3 bucket with versioning
  - DynamoDB table for locking
- [x] **1.3** VPC module
  - 3 AZ deployment
  - Public subnets (ALB, NAT)
  - Private subnets (EKS nodes)
  - VPC Flow Logs enabled
- [x] **1.4** EKS cluster module
  - EKS Auto Mode
  - Private API endpoint
  - OIDC provider for IRSA
- [x] **1.5** ECR repositories
  - `codeguardian/backend`
  - `codeguardian/frontend`
- [x] **1.6** Initial security groups
  - ALB ingress
  - EKS cluster
  - Node-to-node communication
- [x] **1.7** Additional modules created
  - ACM (codeguardian.eric-n.com)
  - Secrets Manager
  - VPC Endpoints (S3, ECR)
  - RDS PostgreSQL
- [x] **1.8** EKS Pod Identity (modern IRSA replacement)
  - AWS Load Balancer Controller
  - External Secrets Operator
  - Velero, Loki, Tempo, EBS CSI

### Validation Gate
```bash
terraform validate  # ✅ Passed
terraform apply -var-file=environments/dev.tfvars  # ⏳ Awaiting AWS credentials
aws eks update-kubeconfig --name codeguardian-dev
kubectl get nodes  # Nodes in Ready state
```

### Deliverables
- Working Terraform modules
- EKS cluster accessible via kubectl
- ECR repositories created

---

## 🚀 Phase 2: Platform Bootstrap

**Goal:** ArgoCD deployed and managing itself (GitOps foundation).

### Tasks
- [ ] **2.1** Create Helm values structure
  ```
  app/backend/helm-chart/
  ├── Chart.yaml
  ├── values.yaml
  └── templates/
  ```
- [x] **2.2** Deploy ArgoCD via Terraform/Helm
  - Install ArgoCD in `argocd` namespace
  - Configure admin credentials
  - Expose via LoadBalancer or Ingress
- [x] **2.3** Create App of Apps pattern *(manifests pre-built)*
  ```yaml
  # argocd/root-app.yaml - CREATED
  # argocd/projects/platform.yaml - CREATED
  ```
- [ ] **2.4** Deploy AWS Load Balancer Controller
  - IRSA role for ALB controller
  - Helm chart via ArgoCD
- [x] **2.5** Deploy basic Prometheus + Grafana *(manifest pre-built)*
  - kube-prometheus-stack Helm chart
  - Basic cluster dashboards

> **Note:** ArgoCD manifests exist in `argocd/` folder but haven't been deployed to cluster yet.

### Validation Gate
```bash
# ArgoCD UI accessible
kubectl port-forward svc/argocd-server -n argocd 8080:443
# Login and see apps syncing
# ALB created for test ingress
```

### Deliverables
- ArgoCD managing cluster add-ons
- App of Apps pattern established
- ALB Controller working

---

## 🔐 Phase 3: Security Foundation

**Goal:** Secrets management and identity foundation in place.

> **Note:** Pod Identity roles already configured in Terraform (Phase 1.8) - no OIDC provider config needed!

### Tasks
- [x] **3.1** AWS Secrets Manager secrets *(Terraform module created)*
  ```bash
  # Secrets created via Terraform secrets-manager module
  # codeguardian/database, codeguardian/app-config
  ```
- [x] **3.2** Deploy External Secrets Operator *(Helm release in Terraform)*
  - Helm chart installed via Terraform
  - Pod Identity for ESO (no IRSA annotations needed)
- [ ] **3.3** Create ExternalSecret resources
  ```yaml
  apiVersion: external-secrets.io/v1beta1
  kind: ExternalSecret
  metadata:
    name: database-credentials
  spec:
    secretStoreRef:
      name: aws-secrets-manager
    target:
      name: db-credentials
    data:
      - secretKey: password
        remoteRef:
          key: codeguardian/database
          property: password
  ```
- [x] **3.4** Pod Identity roles for workloads *(configured in Phase 1)*
  - ALB Controller: ELB management
  - External Secrets: Secrets Manager read
  - Velero: S3 backup access
  - Loki/Tempo: S3 storage access
  - EBS CSI: Volume management
- [ ] **3.5** Basic Network Policies
  - Default deny all ingress
  - Allow specific pod-to-pod traffic
  - Allow egress to AWS services

### Validation Gate
```bash
# ExternalSecret syncing
kubectl get externalsecrets -A
# Secret created from AWS Secrets Manager
kubectl get secret db-credentials -o yaml
# Network policies applied
kubectl get networkpolicies -A
```

### Deliverables
- Zero secrets in Git
- Pod Identity configured for all service accounts
- Network policies blocking unauthorized traffic

---

## 📦 Phase 4: Application Deployment

**Goal:** CodeGuardian app running on EKS, deployed via ArgoCD.

> **Status:** 🟡 This is the main gap - Helm chart templates need to be created!

### Tasks
- [ ] **4.1** Push images to ECR
  ```bash
  # Build and push backend
  docker build -t codeguardian-backend ./app/backend
  docker tag codeguardian-backend:latest $ECR_URI/codeguardian/backend:v1.0.0
  docker push $ECR_URI/codeguardian/backend:v1.0.0
  
  # Build and push frontend
  docker build -t codeguardian-frontend ./app/frontend
  docker tag codeguardian-frontend:latest $ECR_URI/codeguardian/frontend:v1.0.0
  docker push $ECR_URI/codeguardian/frontend:v1.0.0
  ```
- [ ] **4.2** Create Helm chart for CodeGuardian
  ```
  app/helm-chart/
  ├── Chart.yaml
  ├── values.yaml
  ├── values-dev.yaml
  ├── values-prod.yaml
  └── templates/
      ├── _helpers.tpl
      ├── backend-deployment.yaml
      ├── backend-service.yaml
      ├── frontend-deployment.yaml
      ├── frontend-service.yaml
      ├── ingress.yaml           # ALB Ingress for both services
      ├── hpa.yaml               # HorizontalPodAutoscaler
      ├── pdb.yaml               # PodDisruptionBudget
      ├── serviceaccount.yaml    # With Pod Identity
      ├── secret-store.yaml      # ClusterSecretStore for ESO
      ├── external-secret.yaml   # Pull secrets from AWS
      └── network-policy.yaml    # Default deny + allow rules
  ```
- [ ] **4.3** Create ArgoCD Application for CodeGuardian
  ```yaml
  # argocd/apps/codeguardian/application.yaml
  apiVersion: argoproj.io/v1alpha1
  kind: Application
  metadata:
    name: codeguardian
    namespace: argocd
  spec:
    project: default
    source:
      repoURL: https://github.com/YOUR_USERNAME/CodeGuardian-AI
      targetRevision: main
      path: app/helm-chart
      helm:
        valueFiles:
          - values-dev.yaml
    destination:
      server: https://kubernetes.default.svc
      namespace: codeguardian
    syncPolicy:
      automated:
        prune: true
        selfHeal: true
      syncOptions:
        - CreateNamespace=true
  ```
- [ ] **4.4** Add Pod Identity for backend (Bedrock access)
  - Create IAM role for Bedrock InvokeModel
  - Associate with backend service account
- [ ] **4.5** Validate end-to-end flow
  - User accesses Streamlit UI via ALB
  - Submits code for analysis
  - Backend calls Bedrock
  - Results displayed with findings

### Validation Gate
```bash
# Pods running
kubectl get pods -n codeguardian
# Ingress created with ALB
kubectl get ingress -n codeguardian
# Test the endpoint
curl https://codeguardian.yourdomain.com/health
# UI accessible and analysis working
```

### Deliverables
- Application running on EKS
- Accessible via ALB with TLS
- End-to-end analysis working

---

## 📊 Phase 5: Observability Stack

**Goal:** Complete visibility into application and cluster health.

> **Pre-built:** ArgoCD manifests exist in `argocd/apps/observability/` - ready for deployment.

### Tasks
- [x] **5.1** Prometheus configuration *(manifest pre-built)*
  - ServiceMonitor for FastAPI metrics
  - Custom recording rules
  - Alert rules (high latency, errors)
- [ ] **5.2** Grafana dashboards
  - Application dashboard (request rate, latency, errors)
  - Bedrock API dashboard (tokens, latency, costs)
  - Kubernetes cluster dashboard
  - Node health dashboard
- [x] **5.3** Deploy Grafana Loki *(manifest pre-built)*
  - Helm chart via ArgoCD
  - S3 backend for log storage
  - Retention policies
- [ ] **5.4** Configure log collection
  - Promtail DaemonSet
  - Parse JSON logs from FastAPI
  - Add Kubernetes labels
- [x] **5.5** Deploy Tempo for traces *(manifest pre-built)*
  - Helm chart via ArgoCD
  - S3 backend for trace storage
- [x] **5.6** OpenTelemetry Collector *(manifest pre-built)*
  - Helm chart via ArgoCD
  - Collect from all sources
- [ ] **5.7** Add OpenTelemetry to application
  - Install `opentelemetry-sdk` in FastAPI
  - Instrument Bedrock calls
  - Trace context propagation

### Validation Gate
```bash
# Grafana accessible
kubectl port-forward svc/grafana -n monitoring 3000:80
# Dashboards showing data
# Logs visible in Loki via Grafana
# Traces visible in Tempo via Grafana
```

### Deliverables
- Grafana dashboards for all layers
- Logs aggregated and searchable
- Distributed traces working
- Alerts configured

---

## 🛡️ Phase 6: Security Hardening

**Goal:** Runtime security and policy enforcement active.

> **Pre-built:** ArgoCD manifests exist in `argocd/apps/security/` - ready for deployment.

### Tasks
- [x] **6.1** Deploy Kyverno *(manifest pre-built)*
  - Helm chart via ArgoCD
  - Basic policies enabled
- [x] **6.2** Kyverno policies *(manifest pre-built)*
  ```yaml
  # Require non-root
  # Require resource limits
  # Require labels
  # Block privileged containers
  # Require image from ECR only
  ```
- [x] **6.3** Deploy Falco *(manifest pre-built)*
  - Helm chart via ArgoCD
  - Custom rules for CodeGuardian
- [ ] **6.4** Falco rules
  ```yaml
  # Alert on shell spawned in container
  # Alert on sensitive file access
  # Alert on network connection to suspicious IP
  # Alert on privilege escalation attempt
  ```
- [ ] **6.5** Configure Falco alerts
  - Send to Prometheus/Alertmanager
  - Forward to Grafana Loki
- [ ] **6.6** Pod Security Standards
  - Enforce `restricted` profile on app namespace
  - Audit mode on other namespaces
- [ ] **6.7** Image scanning in cluster
  - Trivy operator for continuous scanning
  - Kyverno policy to block high-severity CVEs

### Validation Gate
```bash
# Kyverno blocking non-compliant pods
kubectl apply -f test-privileged-pod.yaml  # Should fail
# Falco generating alerts
kubectl exec -it test-pod -- /bin/bash  # Triggers alert
# View Falco alerts in Grafana
```

### Deliverables
- Kyverno enforcing security policies
- Falco detecting runtime threats
- Pod Security Standards enforced
- Continuous image scanning

---

## 🔄 Phase 7: CI/CD Pipeline

**Goal:** Automated pipeline from code commit to production deployment.

> **Status:** 🟡 Workflows exist but need updates for CodeGuardian naming.

### Tasks
- [x] **7.1** GitHub Actions workflow structure *(pre-built)*
  ```
  .github/workflows/
  ├── build-deploy.yml   # Build & deploy images
  ├── security-scan.yml  # Trivy + Semgrep scans
  ├── terraform.yml      # Infrastructure CI/CD
  └── terraform-docs.yml # Auto-generate TF docs
  ```
- [x] **7.2** CI workflow *(pre-built: security-scan.yml)*
  ```yaml
  # Trigger on PR
  # Run linters (ruff, black)
  # Run unit tests (pytest)
  # Run security scan (Trivy)
  # Run SAST (Semgrep)
  ```
- [x] **7.3** Build workflow *(pre-built: build-deploy.yml)*
  ```yaml
  # Trigger on main merge
  # Build Docker images
  # Tag with git SHA
  # Push to ECR
  # Sign images (cosign)
  ```
- [ ] **7.4** Update workflow with correct names
  ```yaml
  # NEEDS UPDATE in build-deploy.yml:
  env:
    ECR_REPOSITORY_BACKEND: codeguardian/backend   # was: secureai-rag
    ECR_REPOSITORY_FRONTEND: codeguardian/frontend
    EKS_CLUSTER_NAME: codeguardian-dev             # was: secureai-eks-dev
  ```
- [ ] **7.5** Configure GitHub secrets
  ```
  AWS_ACCESS_KEY_ID
  AWS_SECRET_ACCESS_KEY
  COSIGN_PRIVATE_KEY
  COSIGN_PASSWORD
  ```
- [ ] **7.6** Kyverno policy for signed images
  ```yaml
  # Only allow images signed by our key
  ```
- [ ] **7.7** Branch protection rules
  - Require CI passing
  - Require code review
  - No direct push to main

### Validation Gate
```bash
# Push code change
git push origin feature/test
# CI runs automatically
# On merge, image built and pushed
# ArgoCD syncs new version
# Rollback if needed via git revert
```

### Deliverables
- Fully automated CI/CD pipeline
- Security scanning in pipeline
- GitOps deployment flow
- Image signing and verification

---

## 🧪 Phase 8: Testing & Validation

**Goal:** Confidence in reliability and performance.

### Tasks
- [ ] **8.1** Load testing
  ```bash
  # Use k6 or locust
  k6 run load-test.js --vus 50 --duration 5m
  ```
- [ ] **8.2** Chaos testing
  ```bash
  # Pod failure
  kubectl delete pod -l app=codeguardian-backend
  # Node failure (drain)
  kubectl drain node-1 --ignore-daemonsets
  # Network partition (if using chaos mesh)
  ```
- [ ] **8.3** Security testing
  ```bash
  # Run Trivy against running cluster
  trivy k8s --report summary cluster
  # Test Falco detections
  kubectl exec -it test-pod -- cat /etc/shadow
  # Test Kyverno policies
  kubectl apply -f non-compliant-pod.yaml
  ```
- [ ] **8.4** Disaster recovery test
  ```bash
  # Take Velero backup
  velero backup create test-backup
  # Delete namespace
  kubectl delete namespace codeguardian
  # Restore from backup
  velero restore create --from-backup test-backup
  ```
- [ ] **8.5** Cost analysis
  - Review Kubecost dashboard
  - Identify optimization opportunities
  - Right-size resources

### Validation Gate
- Load test: p99 latency < 2s under 50 concurrent users
- Chaos test: Application recovers within 60 seconds
- Security test: All policies working as expected
- DR test: Successful backup and restore

### Deliverables
- Load test results and baseline
- Chaos test runbook
- Security test evidence
- DR procedure documented

---

## 📚 Phase 9: Documentation & Demo

**Goal:** Project ready to showcase.

### Tasks
- [ ] **9.1** README.md
  - Project overview
  - Architecture diagram
  - Quick start guide
  - Tech stack summary
- [ ] **9.2** Architecture documentation
  - Detailed diagrams (draw.io/Lucidchart)
  - Security model explanation
  - Data flow documentation
- [ ] **9.3** Runbooks
  - Incident response
  - Common troubleshooting
  - Scaling procedures
- [ ] **9.4** Demo script
  - 5-minute walkthrough
  - Key features highlight
  - Security features showcase
- [ ] **9.5** Video recording (optional)
  - Architecture walkthrough
  - Live demo
  - Code review

### Deliverables
- Comprehensive README
- Architecture diagrams
- Operational runbooks
- Demo-ready project

---

## 📊 Progress Tracker

### Current Status

| Phase | Status | Started | Completed | Notes |
|-------|--------|---------|-----------|-------|
| Phase 0: Local Dev | ✅ Completed | Jan 28, 2026 | Jan 28, 2026 | FastAPI + Streamlit + 23 tests passing |
| Phase 1: Foundation | ✅ Terraform Ready | Jan 28, 2026 | Jan 28, 2026 | All modules built, `terraform validate` ✅ |
| Phase 2: Platform Bootstrap | ✅ Terraform Ready | Jan 28, 2026 | Jan 28, 2026 | ArgoCD + ALB Controller in helm-addons.tf |
| Phase 3: Security Foundation | ✅ Terraform Ready | Jan 28, 2026 | Jan 28, 2026 | Pod Identity + ESO + Secrets Manager |
| Phase 4: Application Deploy | 🟡 Needs Work | | | Helm chart templates not created |
| Phase 5: Observability | 🟠 Manifests Ready | | | ArgoCD apps exist, need deployment |
| Phase 6: Security Hardening | 🟠 Manifests Ready | | | Falco, Kyverno ArgoCD apps exist |
| Phase 7: CI/CD Pipeline | 🟡 Needs Updates | | | Workflows exist but need CodeGuardian names |
| Phase 8: Testing | ⬜ Not Started | | | |
| Phase 9: Documentation | 🟡 In Progress | Jan 28, 2026 | | README needs updating |

### Status Legend
- ⬜ Not Started
- 🟡 Needs Work (partially done, gaps exist)
- 🟠 Manifests Ready (config exists, awaiting cluster deployment)
- ✅ Completed / Terraform Ready
- ❌ Blocked

---

## 🎯 Gap Analysis: What's Left to Complete

Based on the Project Plan success criteria, here's what still needs to be done:

### 🔴 Critical Path (Must Have)

| Item | Status | What's Missing |
|------|--------|----------------|
| `terraform apply` runs successfully | ⏳ | AWS credentials needed, then apply |
| FastAPI + Streamlit pods on EKS | ❌ | Helm chart templates not created |
| Code analysis returns Bedrock responses | ✅ | Works locally, needs EKS deployment |
| GitHub Actions → ECR → ArgoCD | 🟡 | Workflow exists but uses old names |
| ArgoCD auto-syncs from Git | 🟡 | root-app.yaml needs repo URL update |
| Grafana dashboards | ⏳ | Manifest exists, needs deployment |
| Falco alerts on security events | ⏳ | Manifest exists, needs deployment |
| All secrets from Secrets Manager | ✅ | ESO + SecretStore configured |
| Network policies blocking traffic | ❌ | Not created yet |

### 📁 Files That Need Creation/Updates

```
NEEDS CREATION:
├── app/helm-chart/
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── values-dev.yaml
│   ├── values-prod.yaml
│   └── templates/
│       ├── deployment.yaml      (backend)
│       ├── service.yaml
│       ├── ingress.yaml
│       ├── hpa.yaml
│       ├── pdb.yaml
│       ├── serviceaccount.yaml
│       ├── external-secret.yaml
│       └── network-policy.yaml
├── app/frontend/helm-chart/     (or combined chart)
├── argocd/apps/codeguardian/
│   └── application.yaml         (ArgoCD app for our app)
└── k8s/network-policies/
    └── default-deny.yaml

NEEDS UPDATES:
├── argocd/root-app.yaml         → Update repoURL
├── .github/workflows/build-deploy.yml → Update ECR repo names
└── README.md                    → Full project documentation
```

### 🚀 Recommended Next Steps (Priority Order)

1. **Get AWS credentials** and run `terraform apply`
2. **Create Helm chart** for backend + frontend (`app/helm-chart/`)
3. **Update GitHub workflow** with correct ECR repository names
4. **Update ArgoCD root-app** with your GitHub repo URL
5. **Create ArgoCD Application** for CodeGuardian app
6. **Deploy and validate** end-to-end flow
7. **Add Network Policies** for security hardening
8. **Run load tests** and document results

---

## 🎯 Quick Reference: Remaining Work

Since Phases 0-3 are essentially complete (Terraform ready), here's the focused remaining work:

```
IMMEDIATE (Day 1-2):
├── terraform apply -var-file=environments/dev.tfvars
├── Verify EKS cluster is healthy
├── Verify ArgoCD, ALB Controller, ESO are running
└── Push Docker images to ECR

PHASE 4 - App Deployment (Day 3-5):
├── Create app/helm-chart/ with all templates
├── Create argocd/apps/codeguardian/application.yaml  
├── Add Bedrock Pod Identity for backend
├── Deploy via ArgoCD and test end-to-end
└── Verify: UI → Backend → Bedrock → Response

PHASE 5-6 - Observability & Security (Day 6-7):
├── Apply ArgoCD root-app.yaml (deploys all platform apps)
├── Verify Prometheus, Grafana, Loki, Tempo running
├── Verify Falco, Kyverno running
├── Create Network Policies for codeguardian namespace
└── Test Falco alerts with security event

PHASE 7 - CI/CD Polish (Day 8):
├── Update .github/workflows/build-deploy.yml with correct names
├── Configure GitHub secrets (AWS creds, Cosign keys)
├── Test full pipeline: push → build → scan → deploy
└── Verify ArgoCD auto-syncs new images

PHASE 8-9 - Testing & Docs (Day 9-10):
├── Load test with k6 or locust
├── Document architecture in README.md
├── Create Grafana dashboard screenshots
└── Record demo (optional)
```

---

## 💡 Tips for Success

1. **Don't skip Phase 0** - A working local app makes debugging cloud issues 10x easier ✅ Done!
2. **Validate each gate** - Resist the urge to rush ahead without confirming the current phase works
3. **Git commit frequently** - Small commits with clear messages
4. **Document as you go** - Don't leave all docs for the end
5. **Cost awareness** - Destroy dev resources when not in use (`terraform destroy`)

---

## 📋 Project Inventory

### What Exists Today

| Category | Items |
|----------|-------|
| **Application** | FastAPI backend (src/, tests/), Streamlit frontend (src/), Dockerfiles, docker-compose |
| **Terraform** | 9 modules (networking, eks, rds, ecr, acm, s3, secrets-manager, vpc-endpoints) |
| **EKS Addons** | ALB Controller, ArgoCD, cert-manager, ESO, Gateway API (all in helm-addons.tf) |
| **Pod Identity** | 6 roles (ALB, ESO, Velero, Loki, Tempo, EBS CSI) |
| **ArgoCD Apps** | root-app.yaml, projects/platform.yaml, apps for observability/security/operations |
| **CI/CD** | 4 GitHub Actions workflows (build-deploy, security-scan, terraform, terraform-docs) |

### What Needs Creation

| Category | Items |
|----------|-------|
| **Helm Chart** | app/helm-chart/ with all Kubernetes manifests |
| **ArgoCD App** | argocd/apps/codeguardian/application.yaml |
| **Pod Identity** | Backend role for Bedrock access |
| **Network Policies** | Default deny + allow rules for codeguardian namespace |
| **Documentation** | README.md with full architecture, setup, demo instructions |

---

*Last Updated: January 28, 2026*

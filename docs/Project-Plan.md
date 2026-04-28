# CodeGuardian AI Platform - Production-Grade AI Security Platform on EKS

**Project Goal:** Production-grade AI-powered security code reviewer on AWS EKS with enterprise security, observability, and GitOps delivery


---

## 🎯 Vision

**CodeGuardian AI** is an AI-powered security code reviewer that catches vulnerabilities before deployment. Developers paste code (Python, JavaScript, Terraform) and receive real-time, context-aware security findings with severity ratings and fix examples—powered by AWS Bedrock Claude 3.

**This project demonstrates full-stack DevSecOps:** secure infrastructure, GitOps deployment, runtime protection, and comprehensive observability—all production-grade.

---

## ✅ What "Done" Looks Like

When complete, CodeGuardian AI will have:

| Component | Desired State |
|-----------|---------------|
| **Infrastructure** | Fully provisioned via Terraform (VPC, EKS, RDS, S3, Secrets Manager) |
| **Application** | FastAPI backend + Streamlit UI running on EKS, analyzing code via Bedrock |
| **Security** | Zero-trust: EKS Pod Identity, Network Policies, Pod Security Standards, Falco runtime monitoring |
| **CI/CD** | GitHub Actions → security scans → ECR → ArgoCD auto-deploy |
| **Observability** | Grafana dashboards showing metrics, logs, and traces in one place |
| **GitOps** | ArgoCD syncing all K8s manifests from Git (single source of truth) |

### User Flow (Final State)
```
Developer pastes code → FastAPI receives request → Bedrock analyzes
                                                         ↓
                           ← JSON response with findings ←
                           (Severity, Line #, Fix suggestion, CWE mapping)
```

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AWS Cloud                                      │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                           VPC (10.0.0.0/16)                           │  │
│  │                                                                       │  │
│  │   ┌─────────────┐    ┌─────────────────────────────────────────────┐  │  │
│  │   │   Public    │    │              Private Subnets                │  │  │
│  │   │   Subnets   │    │  ┌─────────────────────────────────────┐   │  │  │
│  │   │             │    │  │            EKS Cluster              │   │  │  │
│  │   │  ┌───────┐  │    │  │  ┌─────────┐  ┌─────────┐          │   │  │  │
│  │   │  │  ALB  │──┼────┼──┼─▶│ FastAPI │  │Streamlit│          │   │  │  │
│  │   │  └───────┘  │    │  │  │   Pod   │  │   Pod   │          │   │  │  │
│  │   │             │    │  │  └────┬────┘  └─────────┘          │   │  │  │
│  │   │  ┌───────┐  │    │  │       │                            │   │  │  │
│  │   │  │  NAT  │  │    │  │  ┌────▼────────────────────────┐   │   │  │  │
│  │   │  └───────┘  │    │  │  │    Platform Components      │   │   │  │  │
│  │   └─────────────┘    │  │  │  • ArgoCD      • Prometheus │   │   │  │  │
│  │                      │  │  │  • Grafana     • Loki       │   │   │  │  │
│  │                      │  │  │  • Falco       • Kyverno    │   │   │  │  │
│  │                      │  │  │  • External Secrets Operator│   │   │  │  │
│  │                      │  │  └─────────────────────────────┘   │   │  │  │
│  │                      │  └─────────────────────────────────────┘   │  │  │
│  │                      └─────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                      │                                      │
│         ┌────────────────────────────┼────────────────────────────┐         │
│         ▼                            ▼                            ▼         │
│  ┌─────────────┐            ┌─────────────┐              ┌─────────────┐    │
│  │   Bedrock   │            │   Secrets   │              │     S3      │    │
│  │  Claude 3   │            │   Manager   │              │  (Docs/KB)  │    │
│  └─────────────┘            └─────────────┘              └─────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow
```
User → ALB → FastAPI → Bedrock (Claude 3) → Response with security findings
              │
              └─→ All requests traced (OpenTelemetry → Tempo)
              └─→ All logs shipped (Loki)
              └─→ Runtime monitored (Falco)
```

---

## 🛠️ Complete Technology Stack

### Infrastructure Layer
| Component | Technology | Purpose |
|-----------|------------|---------|
| IaC | Terraform | All AWS resource provisioning |
| Compute | EKS Auto Mode | Managed Kubernetes with auto-scaling |
| Networking | VPC + ALB Controller | Isolated network with ingress |
| Database | Aurora PostgreSQL / OpenSearch | Vector store for RAG |
| Storage | S3 (encrypted) | Document/knowledge base storage |
| Secrets | AWS Secrets Manager + ESO | Zero hardcoded credentials |
| Certificates | ACM + cert-manager | TLS everywhere |

### Platform Layer (EKS Add-ons)
| Category | Components |
|----------|------------|
| **GitOps** | ArgoCD |
| **Security** | Kyverno (policy), Falco (runtime), Trivy (CI scanning) |
| **Observability** | Prometheus, Grafana, Loki, OpenTelemetry → Tempo |
| **Networking** | AWS VPC CNI (with native NetworkPolicy support) |
| **Operations** | Velero (backup), Kubecost (cost visibility) |

### Application Layer
| Component | Technology |
|-----------|------------|
| Backend API | Python FastAPI |
| Frontend UI | Streamlit |
| AI/ML | AWS Bedrock (Claude 3) |
| RAG Framework | LangChain |
| Packaging | Helm charts |
| CI/CD | GitHub Actions |

---

## 🔒 Security Model (DevSecOps Focus)

### Defense in Depth
```
┌─────────────────────────────────────────────────────────────┐
│  1. NETWORK         VPC isolation, Security Groups,         │
│                     Network Policies (VPC CNI)              │
├─────────────────────────────────────────────────────────────┤
│  2. IDENTITY        EKS Pod Identity, RBAC,                 │
│                     Least-privilege IAM policies            │
├─────────────────────────────────────────────────────────────┤
│  3. DATA            Encryption at rest (KMS), TLS in        │
│                     transit, Secrets Manager                │
├─────────────────────────────────────────────────────────────┤
│  4. RUNTIME         Pod Security Standards, Falco           │
│                     detecting anomalies                     │
├─────────────────────────────────────────────────────────────┤
│  5. SUPPLY CHAIN    Trivy scanning in CI, signed images,    │
│                     Kyverno blocking unsigned               │
├─────────────────────────────────────────────────────────────┤
│  6. OBSERVABILITY   Full audit trail: CloudTrail, Loki      │
│                     logs, Prometheus alerts                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Success Criteria

The project is **complete** when:

- [ ] `terraform apply` provisions all infrastructure successfully *(Terraform ready, awaiting apply)*
- [ ] FastAPI + Streamlit pods running and healthy on EKS *(needs Helm chart)*
- [x] Code analysis queries return valid Bedrock responses *(works locally!)*
- [ ] GitHub Actions pipeline: lint → test → scan → build → push to ECR *(workflows exist, need name updates)*
- [ ] ArgoCD auto-syncs deployments from Git *(manifests ready, need repo URL)*
- [ ] Grafana dashboard shows: request latency, error rates, pod metrics *(ArgoCD app ready)*
- [ ] Falco alerts firing on test security events *(ArgoCD app ready)*
- [x] All secrets pulled from AWS Secrets Manager (zero in Git) *(ESO + Terraform configured)*
- [ ] Network policies blocking unauthorized pod-to-pod traffic *(not created yet)*

### Current Progress: ~60% Complete
- ✅ Phase 0: Local app working with 23 tests
- ✅ Phase 1-3: Terraform modules complete and validated
- 🟡 Phase 4: Need Helm chart (main gap)
- 🟠 Phase 5-7: Manifests/workflows exist, need deployment
- ⬜ Phase 8-9: Testing & documentation

---

## 📱 Application Behavior

### Input
Developer pastes Python / JavaScript / Terraform code

### AI Analysis (Bedrock Claude 3)
- Security vulnerabilities (SQL injection, XSS, secrets in code)
- Misconfigurations (open S3 buckets, weak IAM policies)
- Best practice violations
- Supply chain risks (dangerous dependencies)

### Output
- Severity-rated findings (Critical / High / Medium / Low)
- Exact line numbers with issues
- AI-generated fix suggestions with code snippets
- Compliance mapping (OWASP Top 10, CWE)

### Prompt Strategy
```
System: You are a security code reviewer expert. Analyze code for:
1. Security vulnerabilities (OWASP Top 10)
2. Hardcoded secrets
3. Insecure configurations
4. Best practice violations

Provide line-by-line findings with:
- Severity rating
- Vulnerability type
- Why it's a problem
- How to fix it with code example

User: Analyze this Python code:
[code here]
```

---

## 📚 References

### Security
- [EKS Security Best Practices](https://aws.github.io/aws-eks-best-practices/security/docs/)
- [OWASP Kubernetes Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Kubernetes_Security_Cheat_Sheet.html)
- [AWS Bedrock Security](https://docs.aws.amazon.com/bedrock/latest/userguide/security.html)

### RAG / GenAI
- [AWS Bedrock Knowledge Bases](https://aws.amazon.com/bedrock/knowledge-bases/)
- [LangChain Documentation](https://python.langchain.com/)

### GitOps
- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [GitOps Principles](https://opengitops.dev/)
# Post-mortem: CodeGuardian-AI / LLM Gateway EKS Bootstrap

A walk-through of every issue we hit during the first end-to-end deploy, what
caused it, the fix that worked, and the lesson worth remembering. Read this
before re-running `python RUNME.py all` against a fresh account so you know
*why* each step in the script exists.

---

## 1. RDS InvalidPassword — terraform's `random_password` was a phantom

**Symptom.** Backend pods crash-looping. Logs:
`asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "gateway"`.

**Root cause.** The RDS module is configured with `manage_master_user_password = true`.
When that flag is set, RDS itself generates the master password and stores it
in a Secrets Manager entry that **RDS owns** (named `rds!db-<uuid>`). The
`random_password.db` resource we still had in terraform was being written to a
*different* Secrets Manager entry (`llm-gateway/db-credentials`) and the
ExternalSecret was reading from that one. The two passwords never matched.

**Fix.**
1. `aws rds describe-db-instances ... --query MasterUserSecret.SecretArn` to
   discover the RDS-managed secret.
2. Read its `password` field.
3. `aws secretsmanager put-secret-value` into our app secret with the same
   value (preserving host/port/user/db keys).
4. Annotate the ExternalSecret with a `force-sync=<timestamp>` to trigger
   re-reconcile.
5. `kubectl rollout restart deployment backend`.

This is now step 1 of `python RUNME.py reconcile`.

**Lesson.** When `ManageMasterUserPassword=true`, the source of truth is the
RDS-owned secret. Either drop the `random_password` resource entirely and
point the app at the RDS-managed ARN, or keep a one-way sync job that copies
RDS → app secret. Never assume terraform's random_password "wins".

---

## 2. Bitnami container images vanished (April 2025)

**Symptom.** Redis ArgoCD app stuck in `Progressing` / `ImagePullBackOff`.
`docker.io/bitnami/redis:8.x.x` returns 404.

**Root cause.** Broadcom (Bitnami's parent) deprecated public access to the
`bitnami/*` Docker Hub repos in April 2025. Old tags moved to
`docker.io/bitnamilegacy/*` and the Helm charts ship with a defensive guard
that refuses to install non-`bitnami/*` images unless you opt in.

**Fix.** In every Bitnami chart values block:

```yaml
global:
  security:
    allowInsecureImages: true   # ack the registry move
image:
  repository: bitnamilegacy/redis
metrics:
  image:
    repository: bitnamilegacy/redis-exporter
```

**Lesson.** Pin chart versions and image registries explicitly. Vendor image
moves are the most common reason a previously-green ArgoCD app starts failing
weeks later with no code change on your side.

---

## 3. `rancher/kubectl` is distroless and breaks helm chart Jobs

**Symptom.** Velero / Kyverno cleanup Jobs with
`Error: failed to start container "kubectl": OCI runtime ... exec: "/bin/sh": stat /bin/sh: no such file or directory`.

**Root cause.** The chart authors set `command: ["sh", "-c", "kubectl ..."]`
inside the Job. `rancher/kubectl` is a distroless image — it contains only the
`kubectl` binary, no shell.

**Fix.** Override the kubectl image to a shell-bearing variant:

```yaml
kubectl:
  image:
    repository: docker.io/bitnamilegacy/kubectl
    tag: "1.31.4"
```

**Lesson.** Distroless is great for the chart's *primary* container but
chart-supplied utility Jobs almost always assume `sh`. Read the chart's
Job templates before swapping in a "minimal" image.

---

## 4. Two ExternalSecrets fighting over the same Secret

**Symptom.** `admin-ui` and `backend` both healthy in isolation but the
ExternalSecret controller logged
`secret already managed by another ExternalSecret`. The k8s Secret would
flip-flop between two payloads each reconcile loop.

**Root cause.** ESO (External Secrets Operator) enforces single ownership of a
target Secret. Even with `creationPolicy: Merge` two ESs targeting the same
Secret name end up racing because each tries to set the
`reconcile.external-secrets.io/managed-by` label to itself.

**Fix.** The backend chart already creates the `llm-gateway-admin` Secret;
gate the admin-ui's duplicate ExternalSecret behind a flag:

```yaml
# admin-ui/values.yaml
adminSecret:
  enabled: true
  createExternalSecret: false   # backend owns it
```

```yaml
# admin-ui/templates/deployment.yaml
{{- if and .Values.adminSecret.enabled .Values.adminSecret.createExternalSecret }}
apiVersion: external-secrets.io/v1
kind: ExternalSecret
...
{{- end }}
```

**Lesson.** Decide which chart **owns** each Secret and have the others only
*mount* it. Audit your chart library for duplicate ES definitions before
merging two charts that previously lived independently.

---

## 5. asyncpg + RDS `force_ssl=1` + special characters in passwords

**Symptom.** Backend started up fine the first time but failed after we
rotated to the RDS-managed password. Error mentioned
`InvalidAuthorizationSpecificationError: no pg_hba.conf entry for ... no encryption`
*or* a parse error on the URL itself.

**Root cause — two bugs at once.**

1. RDS `force_ssl=1` requires every connection to be TLS. asyncpg disables
   TLS by default — you must pass `?ssl=require` or `ssl="require"`.
2. The composed URL `postgresql+asyncpg://$(DB_USERNAME):$(DB_PASSWORD)@host/db?ssl=require`
   was set as a Kubernetes env var. Kubernetes `$(VAR)` expansion does **not**
   URL-encode the value. The RDS-managed password contained `#`, which the URL
   parser interpreted as the start of a fragment, truncating the password.

**Fix.** Stop composing the URL in YAML. Move composition into Python where
you can `urllib.parse.quote_plus` each component:

```python
# app/backend/src/usage/db.py
def _resolve_url() -> str:
    user = quote_plus(os.environ["DB_USERNAME"])
    pw   = quote_plus(os.environ["DB_PASSWORD"])
    host = os.environ["DB_HOST"]; port = os.environ.get("DB_PORT", "5432")
    name = os.environ.get("DB_NAME", "gateway")
    return f"postgresql+asyncpg://{user}:{pw}@{host}:{port}/{name}?ssl=require"
```

Then drop the broken `DATABASE_URL` env from the backend Deployment template.

**Lesson.** Treat the database URL as a *computed* value, not a configuration
string. URL encoding belongs in code. K8s `$(VAR)` is plain text substitution
— never use it to assemble URLs containing user-supplied / random data.

---

## 6. `/health` lying about readiness

**Symptom.** Pod reported `Ready 1/1` while every request to `/admin/*` 500'd
with database errors.

**Root cause.** The FastAPI `lifespan` startup tried to initialise the DB,
caught the exception, logged `db.init_failed`, and returned. `/health` only
checked process liveness — it never re-checked the DB. Kubernetes happily kept
the pod in service.

**Fix (recommended, not yet applied).** Add a lightweight DB ping to
`/health` (or a separate `/ready` probe) so a DB outage flips the readiness
probe, removes the pod from the Service endpoints, and surfaces the problem
visibly.

**Lesson.** `liveness` is "is the process alive". `readiness` is "should I
get traffic right now". They are different. If you only have one, you have
the wrong one.

---

## 7. Kyverno restricted policies blocked Velero / kube-system

**Symptom.** Velero node-agent DaemonSet pods rejected at admission:
`policy disallow-privilege-escalation: validation failure`. Same for
`require-run-as-nonroot`, `restrict-seccomp-strict`, `require-drop-all`.

**Root cause.** kyverno-policies' `restricted` profile is intentionally
strict. System workloads (Velero needs hostPath, kubecost needs metrics
gathering, etc.) cannot satisfy them.

**Fix.** In `kyverno-policies` values:

```yaml
failurePolicy: Ignore   # safety net during rollout
policyExclude:
  require-run-as-nonroot:
    any:
      - resources:
          namespaces: [kube-system, velero, kyverno, monitoring,
                       external-secrets, cert-manager, kubecost,
                       argocd, opentelemetry, loki, tempo]
  # ...repeat for restrict-seccomp-strict, disallow-privilege-escalation,
  #    require-drop-all
```

**Lesson.** Cluster-wide restricted policies must always carve out the system
namespaces. Better still: scope policies *only* to your workload namespaces
via `match.any.resources.namespaces` and leave system namespaces alone.

---

## 8. EKS managed-node SG vs. cluster SG

**Symptom.** Backend pods couldn't reach RDS even though we had a SG rule
allowing 5432 from "the cluster security group". Connection timed out at
SYN.

**Root cause.** EKS attaches the **cluster primary security group** to nodes
launched by Karpenter / managed node groups. The terraform module exposes
*two* SG outputs: `cluster_security_group_id` (the EKS control-plane SG) and
`cluster_primary_security_group_id` (the SG actually attached to nodes). We
were allowing traffic from the wrong one.

**Fix.** `terraform/security-groups.tf`:

```hcl
resource "aws_security_group_rule" "rds_from_eks_primary" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = module.rds.security_group_id
  source_security_group_id = module.eks.cluster_primary_security_group_id
  description              = "PostgreSQL from EKS managed nodes"
}
```

**Lesson.** Always check `kubectl get node -o yaml | grep -A2 securityGroups`
when debugging east-west connectivity. The "cluster SG" is rarely the SG you
want.

---

## 9. PowerShell escaping in `kubectl patch -p '{...}'`

**Symptom.** `kubectl patch ... -p '{"spec":{"template":...}}'` succeeded but
applied a literal `\"` instead of an unescaped quote. Patch silently
corrupted resource.

**Root cause.** PowerShell's argument parser doesn't honour `\"` inside
single-quoted strings the way bash does. The string was passed through
verbatim including the backslashes.

**Fix.** Always use `--patch-file`:

```powershell
'{"spec":{"template":{"spec":{"containers":[{"name":"x","image":"y"}]}}}}' |
    Set-Content patch.json
kubectl patch deployment foo --patch-file patch.json
```

**Lesson.** On Windows, never inline JSON into kubectl patch flags. Pipe to a
file or use `kubectl edit`.

---

## 10. GitHub CLI workflow filter takes the *file name*, not the display name

**Symptom.** `gh run list --workflow Terraform` →
`could not find any workflows named Terraform` even though the Actions UI
shows a workflow called "Terraform CI".

**Root cause.** `--workflow` matches one of three things: the workflow's
`.yml` filename, the integer ID, **or** the exact display name from the
`name:` field of the YAML. "Terraform" doesn't match `terraform.yml` or
`Terraform CI`.

**Fix.** Use `gh workflow list` first to discover the canonical names, then
use either the full display name or the file name:

```powershell
gh workflow list
gh run list --workflow "Terraform CI" --limit 1 --json databaseId
```

Also: `gh run list` truncates IDs in its default table view. If you copy
those IDs, `gh run view <truncated>` returns 404. Always pull full IDs via
`--json databaseId`.

**Lesson.** `gh` truncates aggressively in human-readable mode. Use `--json`
whenever you'll feed an ID back into another command.

---

## 11. CI: `aquasecurity/trivy-action@0.33.1` does not exist

**Symptom.** Every push triggered `Terraform CI` to fail in 6 seconds during
"Set up job" with
`Unable to resolve action aquasecurity/trivy-action@0.33.1`.

**Root cause.** Trivy action's released tags are `master`, `0.28.0`, etc.
There is no `0.33.1`.

**Fix.** Use `@master` (or pin to an existing release). The same workflow
also lacked a `working-directory: terraform` default, so even after the
action was resolvable, `terraform fmt -check` would have failed at the repo
root (no `.tf` files there).

**Lesson.** Pin third-party actions, but verify the tag exists. When pinning
fails uniformly across every commit, the cause is almost always "set up job"
not "the code".

---

## 12. CI: container scan tried to build `./app` (no Dockerfile there)

**Symptom.** Security Scan workflow's `container-scan` job failed with
`failed to read dockerfile: open Dockerfile: no such file or directory`.

**Root cause.** The repo split into two services (`app/backend` and
`app/admin-ui`), each with its own Dockerfile. The Security workflow still
referenced the original monolith path `./app`.

**Fix.** Convert the job into a matrix:

```yaml
strategy:
  matrix:
    include:
      - component: backend
        context: ./app/backend
      - component: admin-ui
        context: ./app/admin-ui
```

And distinguish SARIF outputs per component (`trivy-${{ matrix.component }}.sarif`)
plus `category:` so GitHub Security shows them separately.

**Lesson.** When you split a monolith into services, grep your CI for the old
path before merging. SARIF uploads with identical filenames silently
overwrite each other.

---

## 13. CI: Checkov `soft_fail: false` blocks every commit

**Symptom.** `IaC Security Scanning` failed with
`Failed checks: 61, Passed checks: 116`. Every commit. Forever.

**Root cause.** The terraform-aws-modules upstream charts (VPC, EKS, RDS, ...)
ship with ~60 opinionated warnings (e.g. "RDS storage should be encrypted
with CMK", "ALB access logging not enabled") that are either intentional for
a sandbox or already mitigated elsewhere. With `soft_fail: false` the entire
workflow exits non-zero.

Also: Checkov was scanning module sources without
`download_external_modules: true`, so it couldn't even resolve half the
findings — a noisy failure on top of the real one.

**Fix.** Audit-mode + module download:

```yaml
- uses: bridgecrewio/checkov-action@master
  continue-on-error: true
  with:
    soft_fail: true
    download_external_modules: true
    output_format: sarif
    output_file_path: checkov-results.sarif
```

Findings still appear in the GitHub Security tab via SARIF upload, but they
no longer block merges. Hardening is tracked separately.

**Lesson.** `soft_fail: false` on day one of a greenfield repo means your
pipeline is red on day one. Start audit-only, triage findings into either
"fix now", "fix in N weeks", or "documented exception", then turn on hard
fail.

---

## 14. CI: `returntocorp/semgrep-action@v1` is archived

**Symptom.** SAST job failed with
`Error: Unable to resolve action returntocorp/semgrep-action`.

**Root cause.** Semgrep moved its GitHub org from `returntocorp` to
`semgrep` in 2024 and archived the old repo.

**Fix.** `uses: semgrep/semgrep-action@v1`.

**Lesson.** Vendor org renames break stable refs. Run a quarterly
`gh actions list-deprecations` (or grep your workflows for archived repos)
and bump.

---

## 15. CI: Snyk required even when no token is configured

**Symptom.** `Dependency Scanning` failed because `SNYK_TOKEN` was empty.

**Fix.** Gate the entire job on a repo variable `ENABLE_SNYK`:

```yaml
dependency-scan:
  if: ${{ vars.ENABLE_SNYK == 'true' }}
```

Until you set `gh variable set ENABLE_SNYK --body true`, the job is skipped.
The `security-report` aggregator uses `if: always()` so a skipped job no
longer breaks the workflow.

**Lesson.** Optional integrations should self-disable when their secret/var
is missing — never make a free CI tier dependent on a paid token.

---

## TL;DR — the things that bit hardest

| # | Class           | One-line lesson                                                          |
|---|-----------------|--------------------------------------------------------------------------|
| 1 | Terraform/AWS   | RDS-managed passwords win. Don't keep a parallel `random_password`.       |
| 2 | Helm/Vendors    | Bitnami images live at `bitnamilegacy/*` since April 2025.               |
| 3 | Containers      | Distroless utility images break shell-based Jobs.                         |
| 4 | ESO             | One Secret, one ExternalSecret. Always.                                   |
| 5 | Python/asyncpg  | URL-encode credentials in code, not in Kubernetes env var expansion.      |
| 6 | K8s probes      | `/health` should fail when the DB is down or it's lying.                  |
| 7 | Kyverno         | Restricted policies must exclude system namespaces.                       |
| 8 | EKS networking  | `cluster_primary_security_group_id` ≠ `cluster_security_group_id`.        |
| 9 | Windows tooling | Don't inline JSON into `kubectl patch -p` from PowerShell.                |
|10 | GH CLI          | `--workflow` wants file name or display name, never a substring.          |
|11 | GH Actions      | Pin third-party actions to *existing* tags, default to `@master` if SHA. |
|12 | CI              | Update CI paths when you split a monolith.                                |
|13 | Security tools  | Start `soft_fail: true`. Promote to hard-fail after triage.               |
|14 | Vendors         | Vendor org renames are a real source of CI breakage.                      |
|15 | CI              | Optional integrations must self-skip when unconfigured.                  |

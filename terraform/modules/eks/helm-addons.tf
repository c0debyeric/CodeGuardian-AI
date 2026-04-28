# ============================================================================
# Helm-based Addons Installation
# ============================================================================
# These addons are NOT available as EKS managed addons and must be installed
# via Helm charts after the cluster is created

# Note: Metrics Server is now available as an EKS managed community addon
# (see main.tf addons block)

# AWS Load Balancer Controller - Manages ALB/NLB ingress
# Uses EKS Pod Identity for AWS credentials (configured in pod-identity.tf)
# No IRSA annotations needed - Pod Identity Agent handles credential injection
resource "helm_release" "aws_load_balancer_controller" {
  name       = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  version    = "3.0.0"
  namespace  = "kube-system"

  set {
    name  = "clusterName"
    value = var.cluster_name
  }

  set {
    name  = "vpcId"
    value = var.vpc_id
  }

  set {
    name  = "region"
    value = var.region
  }

  # Create service account - Pod Identity doesn't require annotations
  # The Pod Identity Agent automatically injects credentials based on
  # the aws_eks_pod_identity_association created in pod-identity.tf
  set {
    name  = "serviceAccount.create"
    value = "true"
  }

  set {
    name  = "serviceAccount.name"
    value = "aws-load-balancer-controller"
  }

  # High availability
  set {
    name  = "replicaCount"
    value = "2"
  }

  depends_on = [
    module.eks,
    module.aws_lb_controller_pod_identity
  ]
}

# ============================================================================
# ArgoCD - GitOps Controller
# ============================================================================
# Bootstrap ArgoCD via Terraform, then ArgoCD manages all other apps
resource "kubernetes_namespace_v1" "argocd" {
  metadata {
    name = "argocd"
  }

  timeouts {
    delete = "2m"
  }

  depends_on = [module.eks]
}

resource "helm_release" "argocd" {
  name       = "argocd"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argo-cd"
  version    = "9.4.0"
  namespace  = kubernetes_namespace_v1.argocd.metadata[0].name

  # Server configuration
  # ClusterIP avoids creating an AWS NLB + security groups outside of Terraform
  # state, which would otherwise block VPC deletion on `terraform destroy`.
  # Access ArgoCD locally via: kubectl port-forward svc/argocd-server -n argocd 8080:443
  set {
    name  = "server.service.type"
    value = "ClusterIP"
  }

  # Disable insecure access (HTTPS only)
  set {
    name  = "configs.params.server\\.insecure"
    value = "false"
  }

  # HA mode for production
  set {
    name  = "controller.replicas"
    value = "1"
  }

  set {
    name  = "server.replicas"
    value = "2"
  }

  set {
    name  = "repoServer.replicas"
    value = "2"
  }

  depends_on = [
    module.eks,
    helm_release.aws_load_balancer_controller
  ]
}

# ============================================================================
# cert-manager - TLS Certificate Management
# ============================================================================
resource "kubernetes_namespace_v1" "cert_manager" {
  metadata {
    name = "cert-manager"
  }

  timeouts {
    delete = "2m"
  }

  depends_on = [module.eks]
}

resource "helm_release" "cert_manager" {
  name       = "cert-manager"
  repository = "https://charts.jetstack.io"
  chart      = "cert-manager"
  version    = "1.19.3"
  namespace  = kubernetes_namespace_v1.cert_manager.metadata[0].name

  # Install CRDs
  set {
    name  = "crds.enabled"
    value = "true"
  }

  depends_on = [module.eks]
}

# ============================================================================
# External Secrets Operator - Sync AWS Secrets Manager to K8s
# ============================================================================
# Uses EKS Pod Identity for AWS credentials (configured in pod-identity.tf)
resource "kubernetes_namespace_v1" "external_secrets" {
  metadata {
    name = "external-secrets"
  }

  timeouts {
    delete = "2m"
  }

  depends_on = [module.eks]
}

resource "helm_release" "external_secrets" {
  name       = "external-secrets"
  repository = "https://charts.external-secrets.io"
  chart      = "external-secrets"
  version    = "1.3.2"
  namespace  = kubernetes_namespace_v1.external_secrets.metadata[0].name

  # Create service account - Pod Identity doesn't require annotations
  # The Pod Identity Agent automatically injects credentials based on
  # the aws_eks_pod_identity_association created in pod-identity.tf
  set {
    name  = "serviceAccount.create"
    value = "true"
  }

  set {
    name  = "serviceAccount.name"
    value = "external-secrets"
  }

  depends_on = [
    module.eks,
    module.external_secrets_pod_identity
  ]
}

# Gateway API CRDs are installed via kubectl manifests, not Helm
# (no standard Helm chart exists in that repository)

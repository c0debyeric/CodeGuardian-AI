# EKS Pod Identity - Simplified IAM for Kubernetes Service Accounts
# Pod Identity is the modern replacement for IRSA, requiring no OIDC provider configuration

# ============================================================================
# Data Sources
# ============================================================================
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# ============================================================================
# AWS Load Balancer Controller Pod Identity
# ============================================================================
module "aws_lb_controller_pod_identity" {
  source  = "terraform-aws-modules/eks-pod-identity/aws"
  version = "~> 1.0"

  name = "${var.cluster_name}-aws-lbc"

  attach_aws_lb_controller_policy = true

  associations = {
    main = {
      cluster_name    = module.eks.cluster_name
      namespace       = "kube-system"
      service_account = "aws-load-balancer-controller"
    }
  }

  tags = var.tags
}

# ============================================================================
# External Secrets Operator Pod Identity
# ============================================================================
module "external_secrets_pod_identity" {
  source  = "terraform-aws-modules/eks-pod-identity/aws"
  version = "~> 1.0"

  name = "${var.cluster_name}-external-secrets"

  attach_external_secrets_policy        = true
  external_secrets_secrets_manager_arns = ["arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:${var.secret_name_prefix}/*"]

  associations = {
    main = {
      cluster_name    = module.eks.cluster_name
      namespace       = "external-secrets"
      service_account = "external-secrets"
    }
  }

  tags = var.tags
}

# ============================================================================
# Velero Pod Identity
# ============================================================================
module "velero_pod_identity" {
  source  = "terraform-aws-modules/eks-pod-identity/aws"
  version = "~> 1.0"

  name = "${var.cluster_name}-velero"

  attach_velero_policy       = true
  velero_s3_bucket_arns      = [var.velero_bucket_arn]
  velero_s3_bucket_path_arns = ["${var.velero_bucket_arn}/*"]

  associations = {
    main = {
      cluster_name    = module.eks.cluster_name
      namespace       = "velero"
      service_account = "velero"
    }
  }

  tags = var.tags
}

# ============================================================================
# Loki Pod Identity (for S3 storage)
# ============================================================================
module "loki_pod_identity" {
  source  = "terraform-aws-modules/eks-pod-identity/aws"
  version = "~> 1.0"

  name = "${var.cluster_name}-loki"

  # Custom policy for S3 access
  attach_custom_policy    = true
  source_policy_documents = [data.aws_iam_policy_document.loki_s3.json]

  associations = {
    main = {
      cluster_name    = module.eks.cluster_name
      namespace       = "monitoring"
      service_account = "loki"
    }
  }

  tags = var.tags
}

data "aws_iam_policy_document" "loki_s3" {
  statement {
    sid    = "LokiS3Access"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:DeleteObject",
      "s3:PutObject",
      "s3:ListBucket"
    ]
    resources = [
      var.observability_bucket_arn,
      "${var.observability_bucket_arn}/loki/*"
    ]
  }
}

# ============================================================================
# Tempo Pod Identity (for S3 storage)
# ============================================================================
module "tempo_pod_identity" {
  source  = "terraform-aws-modules/eks-pod-identity/aws"
  version = "~> 1.0"

  name = "${var.cluster_name}-tempo"

  # Custom policy for S3 access
  attach_custom_policy    = true
  source_policy_documents = [data.aws_iam_policy_document.tempo_s3.json]

  associations = {
    main = {
      cluster_name    = module.eks.cluster_name
      namespace       = "monitoring"
      service_account = "tempo"
    }
  }

  tags = var.tags
}

data "aws_iam_policy_document" "tempo_s3" {
  statement {
    sid    = "TempoS3Access"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:DeleteObject",
      "s3:PutObject",
      "s3:ListBucket"
    ]
    resources = [
      var.observability_bucket_arn,
      "${var.observability_bucket_arn}/tempo/*"
    ]
  }
}

# ============================================================================
# EBS CSI Driver Pod Identity
# Note: When using EKS managed addon, Pod Identity can be configured via
# the addon's pod_identity_association parameter in the EKS module
# ============================================================================
module "ebs_csi_pod_identity" {
  source  = "terraform-aws-modules/eks-pod-identity/aws"
  version = "~> 1.0"

  name = "${var.cluster_name}-ebs-csi"

  attach_aws_ebs_csi_policy = true

  associations = {
    main = {
      cluster_name    = module.eks.cluster_name
      namespace       = "kube-system"
      service_account = "ebs-csi-controller-sa"
    }
  }

  tags = var.tags
}

# ============================================================================
# Backend Application Pod Identity (Bedrock + Secrets Manager)
# ============================================================================
module "backend_pod_identity" {
  source  = "terraform-aws-modules/eks-pod-identity/aws"
  version = "~> 1.0"

  name = "${var.cluster_name}-backend"

  # Custom policy for Bedrock and Secrets Manager access
  attach_custom_policy    = true
  source_policy_documents = [data.aws_iam_policy_document.backend.json]

  associations = {
    main = {
      cluster_name    = module.eks.cluster_name
      namespace       = "codeguardian"
      service_account = "codeguardian-backend"
    }
  }

  tags = var.tags
}

data "aws_iam_policy_document" "backend" {
  statement {
    sid    = "BedrockInvoke"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream"
    ]
    resources = [
      "arn:aws:bedrock:*::foundation-model/*",
      "arn:aws:bedrock:*:${data.aws_caller_identity.current.account_id}:inference-profile/*"
    ]
  }

  statement {
    sid    = "SecretsManagerRead"
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret"
    ]
    resources = [
      "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:${var.secret_name_prefix}/*"
    ]
  }
}

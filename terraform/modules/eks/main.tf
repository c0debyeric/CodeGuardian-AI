module "eks" {
  # Provider module
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.10"

  # Cluster identity
  name               = var.cluster_name
  kubernetes_version = var.cluster_version

  # Networking
  vpc_id     = var.vpc_id
  subnet_ids = var.private_subnets
  # control_plane_subnet_ids = var.private_subnets

  # Security groups - use only the centrally managed cluster SG
  create_security_group      = false
  security_group_id          = var.cluster_security_group_id
  create_node_security_group = false

  # Access / IAM
  # Auto Mode requires creation of some IAM resources for the controller/operator
  create_auto_mode_iam_resources = true
  # Allow admin permissions to the cluster creator when using Auto Mode
  enable_cluster_creator_admin_permissions = true

  # API access restrictions - enable public access so Terraform can reach the API
  endpoint_public_access       = true
  endpoint_private_access      = true
  endpoint_public_access_cidrs = var.cluster_endpoint_public_access_cidrs

  # Compute (EKS Auto Mode)
  compute_config = {
    enabled    = true
    node_pools = ["general-purpose"]
  }

  # Managed cluster add-ons.
  addons = {
    coredns = {
      most_recent = true
    }

    kube-proxy = {
      most_recent = true
    }

    # Amazon VPC CNI - Manages pod networking and IP address allocation
    vpc-cni = {
      most_recent = true
    }

    # AWS EBS CSI Driver - uses Pod Identity (configured in pod-identity.tf)
    aws-ebs-csi-driver = {
      most_recent = true
      # Pod Identity association is created separately via eks-pod-identity module
    }

    # Pod Identity Agent - Required for EKS Pod Identity
    eks-pod-identity-agent = {
      most_recent = true
    }

    # Metrics Server - EKS managed community addon (announced March 2025)
    # Provides resource metrics for kubectl top, HPA, and VPA
    metrics-server = {
      most_recent = true
    }
  }

  # Note: AWS Load Balancer Controller is NOT an EKS managed addon
  # It is installed via ArgoCD (see argocd/apps/networking/aws-lb-controller.yaml)
  # Pod Identity IAM is configured in pod-identity.tf

  # Metadata tags applied to created resources
  tags = var.tags
}

# gp3 StorageClass - default for all PVCs
resource "kubernetes_storage_class_v1" "gp3" {
  metadata {
    name = "gp3"
    annotations = {
      "storageclass.kubernetes.io/is-default-class" = "true"
    }
  }
  storage_provisioner    = "ebs.csi.eks.amazonaws.com"
  reclaim_policy         = "Delete"
  volume_binding_mode    = "WaitForFirstConsumer"
  allow_volume_expansion = true
  parameters = {
    type      = "gp3"
    encrypted = "true"
  }

  depends_on = [module.eks]
}

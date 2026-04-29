# ============================================================================
# CodeGuardian AI - Main Infrastructure Caller
# ============================================================================

# S3 State Backend
module "s3_state" {
  source = "./modules/s3"

  bucket_name                 = "terraform-state-${data.aws_caller_identity.current.account_id}"
  region                      = var.region
  tags                        = var.tags
  create_observability_bucket = true
  create_velero_bucket        = true
}

# ============================================================================
# Networking
# ============================================================================
module "networking" {
  source = "./modules/networking"

  vpc_name              = var.cluster_name
  vpc_cidr              = var.vpc_cidr
  tags                  = var.tags
  log_retention_in_days = var.log_retention_in_days
}

# ============================================================================
# EKS Cluster
# ============================================================================
module "eks" {
  source = "./modules/eks"

  region                               = var.region
  cluster_name                         = var.cluster_name
  cluster_version                      = var.cluster_version
  vpc_id                               = module.networking.vpc_id
  private_subnets                      = module.networking.private_subnets
  cluster_security_group_id            = local.security_group_ids.eks_cluster
  tags                                 = var.tags
  cluster_endpoint_public_access_cidrs = var.cluster_endpoint_public_access_cidrs
  secret_name_prefix                    = var.secret_name_prefix

  # S3 buckets for IRSA policies
  velero_bucket_arn        = module.s3_state.velero_bucket_arn
  observability_bucket_arn = module.s3_state.observability_bucket_arn
}

# ============================================================================
# RDS PostgreSQL (LLM Gateway usage history: per-request tokens, cost, latency)
# ============================================================================
module "rds" {
  source = "./modules/rds"

  cluster_name              = var.cluster_name
  vpc_id                    = module.networking.vpc_id
  db_subnets                = module.networking.database_subnets
  security_group_id         = local.security_group_ids.rds
  instance_class            = var.rds_instance_class
  db_username               = var.db_username
  multi_az                  = var.environment == "prod" ? true : false
  backup_retention_days     = var.environment == "prod" ? 30 : 7
  skip_final_snapshot       = var.environment == "prod" ? false : true
  final_snapshot_identifier = var.environment == "prod" ? "${var.cluster_name}-final-snapshot-${formatdate("YYYY-MM-DD-hhmm", timestamp())}" : null
  deletion_protection       = var.environment == "prod" ? true : false
  tags                      = var.tags
}

# ============================================================================
# ECR Repositories
# ============================================================================
module "ecr" {
  source = "./modules/ecr"

  repository_prefix              = var.ecr_repository_prefix
  backend_repo_name              = var.ecr_backend_repo_name
  admin_ui_repo_name             = var.ecr_admin_ui_repo_name
  image_tag_mutability           = var.environment == "prod" ? "IMMUTABLE" : "MUTABLE"
  scan_on_push                   = true
  tagged_image_retention_count   = var.environment == "prod" ? 30 : 10
  untagged_image_retention_count = var.environment == "prod" ? 3 : 5
  lifecycle_tag_prefix           = var.ecr_lifecycle_tag_prefix
  tags                           = var.tags
}

# ============================================================================
# ACM Certificate (Manual DNS validation via Cloudflare)
# ============================================================================
module "acm" {
  source = "./modules/acm"

  domain_name = var.domain_name
  tags        = var.tags
}

# ============================================================================
# Secrets Manager
# ============================================================================
module "secrets_manager" {
  source = "./modules/secrets-manager"

  secret_name_prefix         = var.secret_name_prefix
  db_credentials_secret_name = var.db_credentials_secret_name
  recovery_window_in_days    = var.environment == "prod" ? 30 : 7
  db_username                = var.db_username
  db_password                = module.rds.db_password
  db_host                    = module.rds.db_address
  db_port                    = var.db_port
  db_name                    = var.db_name
  tags                       = var.tags
}

# ============================================================================
# VPC Endpoints (cost-optimized: S3 gateway + ECR interface endpoints only)
# ============================================================================
module "vpc_endpoints" {
  source = "./modules/vpc-endpoints"

  app_name                = var.cluster_name
  vpc_id                  = module.networking.vpc_id
  region                  = var.region
  private_subnets         = module.networking.private_subnets
  private_route_table_ids = module.networking.private_route_table_ids
  security_group_id       = local.security_group_ids.vpc_endpoints
  tags                    = var.tags
}

# ============================================================================
# Pre-VPC-destroy cleanup of orphaned K8s-created security groups
# ============================================================================
# The AWS Load Balancer Controller and other Kubernetes controllers create
# security groups in AWS that are NOT tracked by Terraform (e.g. for NLBs,
# ALBs, and service meshes). These orphaned SGs block VPC deletion.
#
# This null_resource depends_on module.networking so its destroy provisioner
# runs BEFORE the VPC is deleted. By that point the EKS cluster and all Helm
# releases (including LBC) have already been destroyed, so no controller can
# recreate the SGs after cleanup.
resource "null_resource" "cleanup_k8s_sgs" {
  triggers = {
    vpc_id       = module.networking.vpc_id
    cluster_name = var.cluster_name
    region       = var.region
  }

  provisioner "local-exec" {
    when        = destroy
    on_failure  = continue
    interpreter = ["pwsh", "-NoProfile", "-Command"]
    command     = <<-EOT
      Write-Host "Cleaning up orphaned K8s security groups in VPC ${self.triggers.vpc_id}..."

      $allSGs = @()

      # SGs tagged by the AWS Load Balancer Controller or EKS
      $tagged = aws ec2 describe-security-groups `
        --region "${self.triggers.region}" `
        --filters "Name=vpc-id,Values=${self.triggers.vpc_id}" "Name=tag-key,Values=kubernetes.io/cluster/${self.triggers.cluster_name}" `
        --query "SecurityGroups[?GroupName!='default'].GroupId" `
        --output json 2>$null | ConvertFrom-Json
      if ($tagged) { $allSGs += $tagged }

      # SGs with k8s-* name patterns (LBC-created, may lack cluster tag)
      $k8s = aws ec2 describe-security-groups `
        --region "${self.triggers.region}" `
        --filters "Name=vpc-id,Values=${self.triggers.vpc_id}" "Name=group-name,Values=k8s-*" `
        --query "SecurityGroups[?GroupName!='default'].GroupId" `
        --output json 2>$null | ConvertFrom-Json
      if ($k8s) { $allSGs += $k8s }

      # Fleet Manager / EKS auto-created SGs
      $fm = aws ec2 describe-security-groups `
        --region "${self.triggers.region}" `
        --filters "Name=vpc-id,Values=${self.triggers.vpc_id}" "Name=group-name,Values=FMManagedSecurityGroup*" `
        --query "SecurityGroups[?GroupName!='default'].GroupId" `
        --output json 2>$null | ConvertFrom-Json
      if ($fm) { $allSGs += $fm }

      $allSGs = $allSGs | Sort-Object -Unique

      if ($allSGs.Count -eq 0) {
        Write-Host "No orphaned K8s security groups found."
      } else {
        Write-Host "Deleting orphaned SGs: $($allSGs -join ', ')"
        foreach ($sg in $allSGs) {
          Write-Host "  Deleting $sg..."
          aws ec2 delete-security-group --group-id $sg --region "${self.triggers.region}" 2>$null
          if ($LASTEXITCODE -ne 0) { Write-Host "  Warning: could not delete $sg (may already be gone)" }
        }
      }
      Write-Host "Cleanup complete."
    EOT
  }

  depends_on = [module.networking]
}


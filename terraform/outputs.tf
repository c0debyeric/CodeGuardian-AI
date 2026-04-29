# ============================================================================
# CodeGuardian AI - Terraform Outputs
# ============================================================================

# Networking
output "vpc_id" {
  description = "VPC ID"
  value       = module.networking.vpc_id
}

output "private_subnets" {
  description = "Private subnet IDs"
  value       = module.networking.private_subnets
}

# EKS
output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "EKS cluster API endpoint"
  value       = module.eks.cluster_endpoint
}

output "eks_cluster_oidc_issuer_url" {
  description = "OIDC issuer URL for IRSA"
  value       = module.eks.cluster_oidc_issuer_url
}

# RDS
output "rds_endpoint" {
  description = "RDS database endpoint"
  value       = module.rds.db_endpoint
}

output "rds_address" {
  description = "RDS database address (host only)"
  value       = module.rds.db_address
}

# ECR
output "ecr_backend_url" {
  description = "ECR repository URL for backend"
  value       = module.ecr.backend_url
}

output "ecr_admin_ui_url" {
  description = "ECR repository URL for admin-ui (Next.js console)"
  value       = module.ecr.admin_ui_url
}

# ACM
output "acm_certificate_arn" {
  description = "ARN of the ACM certificate for codeguardian.eric-n.com"
  value       = module.acm.certificate_arn
}

output "acm_validation_records" {
  description = "DNS CNAME records to add to Cloudflare for certificate validation"
  value       = module.acm.validation_records
}

# Secrets Manager
output "secrets_db_credentials_arn" {
  description = "ARN of the database credentials secret"
  value       = module.secrets_manager.db_credentials_arn
}

# Backend Pod Identity
output "backend_role_arn" {
  description = "IAM role ARN for backend application (Bedrock + Secrets access)"
  value       = module.eks.backend_role_arn
}

# Region
output "region" {
  description = "AWS region"
  value       = var.region
}


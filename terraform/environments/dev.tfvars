# Development Environment Configuration
# Deploy with: terraform apply -var-file="environments/dev.tfvars"

# Core Configuration
region       = "us-east-1"
environment  = "dev"
cluster_name = "codeguardian-dev"

# Network configuration
vpc_cidr = "10.0.0.0/16"

# EKS configuration
cluster_version                      = "1.34"
cluster_endpoint_public_access_cidrs = ["0.0.0.0/0"] # Restrict this in production!

# Logging
log_retention_in_days = 7 # 7 days for dev

# RDS configuration (when enabled)
rds_instance_class = "db.t3.small"

# Tags
tags = {
  Project     = "CodeGuardian-AI"
  Owner       = "eric"
  cost-center = "yo-mama"
  Environment = "dev"
}

# ============================================================================
# ECR Configuration
# ============================================================================
ecr_repository_prefix     = "codeguardian"
ecr_backend_repo_name     = "backend"
ecr_frontend_repo_name    = "frontend"
ecr_lifecycle_tag_prefix  = ["v", "release"]

# ============================================================================
# Domain Configuration
# ============================================================================
domain_name = "codeguardian.eric-n.com"

# ============================================================================
# Database Configuration
# ============================================================================
db_username = "codeguardian"
db_port     = 5432
db_name     = "codeguardian"

# ============================================================================
# Secrets Manager Configuration
# ============================================================================
secret_name_prefix         = "codeguardian"
db_credentials_secret_name = "db-credentials"

# Production Environment Configuration
# Deploy with: terraform apply -var-file="environments/prod.tfvars"

# Core Configuration
region       = "us-east-1"
environment  = "prod"
cluster_name = "codeguardian-prod"

# Network configuration
vpc_cidr = "10.1.0.0/16" # Different CIDR from dev

# EKS configuration
cluster_version                      = "1.31"
cluster_endpoint_public_access_cidrs = ["YOUR_OFFICE_IP/32"] # Restrict to your IP ranges

# Logging
log_retention_in_days = 90 # 90 days for production

# RDS configuration (when enabled)
rds_instance_class = "db.r5.large"

# Tags
tags = {
  Project     = "CodeGuardian-AI"
  Owner       = "platform-team"
  CostCenter  = "engineering-prod"
  Environment = "prod"
}

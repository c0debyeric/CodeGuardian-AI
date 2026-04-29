variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-2"
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]{1,64}$", var.cluster_name))
    error_message = "Cluster name must be lowercase alphanumeric with hyphens (max 64 chars)."
  }
}

variable "cluster_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.33"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.10.0.0/16"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "log_retention_in_days" {
  description = "CloudWatch log retention"
  type        = number
  default     = 7
}

variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.small"

  validation {
    condition     = can(regex("^db\\.", var.rds_instance_class))
    error_message = "RDS instance class must start with 'db.'."
  }
}

variable "tags" {
  description = "Additional tags"
  type        = map(string)
  default     = {}
}

variable "cluster_endpoint_public_access_cidrs" {
  type        = list(string)
  description = "List of CIDR blocks allowed to access the cluster endpoint publicly"
}

# ============================================================================
# ECR Configuration
# ============================================================================
variable "ecr_repository_prefix" {
  description = "Prefix for ECR repository names"
  type        = string
  default     = "codeguardian"
}

variable "ecr_backend_repo_name" {
  description = "Name for the backend ECR repository"
  type        = string
  default     = "backend"
}

variable "ecr_admin_ui_repo_name" {
  description = "Name for the admin-ui ECR repository (Next.js console)"
  type        = string
  default     = "admin-ui"
}

variable "ecr_lifecycle_tag_prefix" {
  description = "Tag prefixes for ECR lifecycle policy"
  type        = list(string)
  default     = ["v", "release"]
}

# ============================================================================
# Domain Configuration
# ============================================================================
variable "domain_name" {
  description = "Domain name for ACM certificate"
  type        = string
}

# ============================================================================
# Database Configuration
# ============================================================================
variable "db_username" {
  description = "Database username"
  type        = string
  default     = "codeguardian"
  sensitive   = true
}

variable "db_port" {
  description = "Database port"
  type        = number
  default     = 5432
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "codeguardian"
}

# ============================================================================
# Secrets Manager Configuration
# ============================================================================
variable "secret_name_prefix" {
  description = "Prefix for secret names in Secrets Manager"
  type        = string
  default     = "codeguardian"
}

variable "db_credentials_secret_name" {
  description = "Name for database credentials secret"
  type        = string
  default     = "db-credentials"
}
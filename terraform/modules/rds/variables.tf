variable "cluster_name" {
  type        = string
  description = "Name of the cluster"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID"
}

variable "db_subnets" {
  type        = list(string)
  description = "List of private subnet IDs"
}

variable "security_group_id" {
  type        = string
  description = "Security group ID for RDS instance"
}

variable "instance_class" {
  type        = string
  default     = "db.t3.micro"
  description = "Database instance class"
}

variable "db_username" {
  type        = string
  sensitive   = true
  description = "Database username"
}

variable "db_password" {
  type        = string
  sensitive   = true
  default     = null
  description = "Database password"
}

variable "multi_az" {
  type        = bool
  default     = false
  description = "Enable Multi-AZ deployment"
}

variable "backup_retention_days" {
  type        = number
  default     = 7
  description = "Database backup retention in days"
}

variable "skip_final_snapshot" {
  type        = bool
  default     = true
  description = "Skip final snapshot when destroying database"
}

variable "final_snapshot_identifier" {
  type        = string
  default     = null
  description = "Final snapshot identifier when destroying"
}

variable "deletion_protection" {
  type        = bool
  default     = false
  description = "Enable deletion protection"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to all resources"
}

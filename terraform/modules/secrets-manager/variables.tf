variable "secret_name_prefix" {
  type        = string
  description = "Prefix for secret names"
  default     = "codeguardian"
}

variable "db_credentials_secret_name" {
  type        = string
  description = "Name for the database credentials secret"
  default     = "db-credentials"
}

variable "recovery_window_in_days" {
  type        = number
  description = "Number of days to retain secret after deletion"
  default     = 7

  validation {
    condition     = var.recovery_window_in_days >= 7 && var.recovery_window_in_days <= 30
    error_message = "Recovery window must be between 7 and 30 days."
  }
}

variable "db_username" {
  type        = string
  sensitive   = true
  description = "Database username"

  validation {
    condition     = var.db_username != null && length(var.db_username) > 0
    error_message = "db_username is required and cannot be empty."
  }
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "Database password from the RDS module"

  validation {
    condition     = var.db_password != null && length(var.db_password) > 0
    error_message = "db_password is required and cannot be empty."
  }
}

variable "db_host" {
  type        = string
  description = "Database host address"
}

variable "db_port" {
  type        = number
  description = "Database port"
  default     = 5432
}

variable "db_name" {
  type        = string
  description = "Database name"
  default     = "codeguardian"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to all resources"
}

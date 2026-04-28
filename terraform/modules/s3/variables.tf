variable "bucket_name" {
  type        = string
  description = "Name of the S3 bucket"
}
variable "region" {
  type        = string
  description = "AWS region for the S3 bucket"
}
variable "tags" {
  type        = map(string)
  description = "Tags to apply to all resources"
}

variable "create_observability_bucket" {
  type        = bool
  description = "Whether to create the observability bucket for Loki/Tempo"
  default     = true
}

variable "create_velero_bucket" {
  type        = bool
  description = "Whether to create the Velero backup bucket"
  default     = true
}

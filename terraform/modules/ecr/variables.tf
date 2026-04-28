variable "repository_prefix" {
  type        = string
  description = "Prefix for ECR repository names"
}

variable "backend_repo_name" {
  type        = string
  description = "Name for the backend repository"
  default     = "backend"
}

variable "frontend_repo_name" {
  type        = string
  description = "Name for the frontend repository"
  default     = "frontend"
}

variable "image_tag_mutability" {
  type        = string
  description = "Image tag mutability setting (MUTABLE or IMMUTABLE)"
  default     = "MUTABLE"

  validation {
    condition     = contains(["MUTABLE", "IMMUTABLE"], var.image_tag_mutability)
    error_message = "Image tag mutability must be either MUTABLE or IMMUTABLE."
  }
}

variable "scan_on_push" {
  type        = bool
  description = "Enable image scanning on push"
  default     = true
}

variable "tagged_image_retention_count" {
  type        = number
  description = "Number of tagged images to retain"
  default     = 10
}

variable "untagged_image_retention_count" {
  type        = number
  description = "Number of untagged images to retain"
  default     = 5
}

variable "lifecycle_tag_prefix" {
  type        = list(string)
  description = "Tag prefixes to match for lifecycle policy"
  default     = ["v"]
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to all resources"
}

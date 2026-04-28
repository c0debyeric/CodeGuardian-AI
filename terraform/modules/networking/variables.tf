variable "vpc_name" {
  type        = string
  description = "Name of the VPC"
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block for the VPC"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to all resources"
}

variable "log_retention_in_days" {
  type        = number
  description = "CloudWatch log retention in days"
  default     = 7
}

variable "private_subnet_cidrs" {
  type        = list(string)
  description = "CIDR blocks for private subnets (workloads - 1 per AZ)"
  default = [
    "10.0.0.0/19",  # AZ1 - Private (workloads)
    "10.0.64.0/19", # AZ2 - Private (workloads)
    "10.0.128.0/19" # AZ3 - Private (workloads)
  ]
}

variable "database_subnets" {
  type        = list(string)
  description = "CIDR blocks for database subnets (1 per AZ)"
  default = [
    "10.0.32.0/27", # AZ1 - Database
    "10.0.96.0/27", # AZ2 - Database
    "10.0.160.0/27" # AZ3 - Database
  ]
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "CIDR blocks for public subnets (1 per AZ by default)"
  default = [
    "10.0.192.0/24", # AZ1 - Public
    "10.0.193.0/24", # AZ2 - Public
    "10.0.194.0/24"  # AZ3 - Public
  ]
}

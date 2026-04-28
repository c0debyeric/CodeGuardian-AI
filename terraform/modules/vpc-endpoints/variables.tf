variable "app_name" {
  type        = string
  description = "Name of the application"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID"
}

variable "private_subnets" {
  type        = list(string)
  description = "List of private subnet IDs for interface endpoints"
}

variable "private_route_table_ids" {
  type        = list(string)
  description = "List of private route table IDs for gateway endpoints"
}

variable "region" {
  type        = string
  description = "AWS region"
}

variable "security_group_id" {
  type        = string
  description = "Security group ID for VPC endpoints"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to all resources"
}

output "vpc_id" {
  value       = module.vpc.vpc_id
  description = "VPC ID"
}

output "private_subnets" {
  value       = module.vpc.private_subnets
  description = "List of private subnet IDs"
}

output "public_subnets" {
  value       = module.vpc.public_subnets
  description = "List of public subnet IDs"
}

output "private_route_table_ids" {
  value       = module.vpc.private_route_table_ids
  description = "List of private route table IDs"
}

output "vpc_arn" {
  value       = module.vpc.vpc_arn
  description = "ARN of the VPC"
}

output "vpc_cidr_block" {
  value       = module.vpc.vpc_cidr_block
  description = "Primary CIDR block of the VPC"
}

output "public_route_table_ids" {
  value       = module.vpc.public_route_table_ids
  description = "List of public route table IDs"
}

output "availability_zones" {
  value       = data.aws_availability_zones.available.names
  description = "Availability Zones used by the VPC/subnets"
}

output "nat_gateway_ids" {
  value       = module.vpc.natgw_ids
  description = "IDs of NAT Gateways created for the VPC"
}

output "internet_gateway_id" {
  value       = module.vpc.igw_id
  description = "ID of the Internet Gateway attached to the VPC"
}

output "private_subnet_ipv4_cidr_blocks" {
  value       = module.vpc.private_subnets_cidr_blocks
  description = "IPv4 CIDR blocks for private subnets"
}

output "public_subnet_ipv4_cidr_blocks" {
  value       = module.vpc.public_subnets_cidr_blocks
  description = "IPv4 CIDR blocks for public subnets"
}

output "database_subnets" {
  value       = module.vpc.database_subnets
  description = "List of database subnet IDs (if configured)"
}

output "flow_log_id" {
  value       = module.vpc_flow_log.id
  description = "ID of the VPC Flow Log"
}

output "flow_log_arn" {
  value       = module.vpc_flow_log.arn
  description = "ARN of the VPC Flow Log"
}

output "flow_log_cloudwatch_log_group_name" {
  value       = module.vpc_flow_log.cloudwatch_log_group_name
  description = "CloudWatch Log Group name for VPC Flow Logs"
}

output "flow_log_cloudwatch_log_group_arn" {
  value       = module.vpc_flow_log.cloudwatch_log_group_arn
  description = "CloudWatch Log Group ARN for VPC Flow Logs"
}

output "flow_log_iam_role_arn" {
  value       = module.vpc_flow_log.iam_role_arn
  description = "IAM role ARN for VPC Flow Logs"
}

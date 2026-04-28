################################################################################
# Cluster
################################################################################

output "cluster_arn" {
  description = "The Amazon Resource Name (ARN) of the cluster"
  value       = module.eks.cluster_arn
}

output "cluster_certificate_authority_data" {
  description = "Base64 encoded certificate data required to communicate with the cluster"
  value       = module.eks.cluster_certificate_authority_data
  sensitive   = true
}

output "cluster_endpoint" {
  description = "Endpoint for your Kubernetes API server"
  value       = module.eks.cluster_endpoint
}

output "cluster_id" {
  description = "The ID of the EKS cluster. Note: currently a value is returned only for local EKS clusters created on Outposts"
  value       = module.eks.cluster_id
}

output "cluster_name" {
  description = "The name of the EKS cluster"
  value       = module.eks.cluster_name
}

################################################################################
# Addons
################################################################################

output "alb_controller_role_arn" {
  description = "IAM role ARN for AWS Load Balancer Controller (Pod Identity)"
  value       = module.aws_lb_controller_pod_identity.iam_role_arn
}

output "alb_controller_role_name" {
  description = "IAM role name for AWS Load Balancer Controller (Pod Identity)"
  value       = module.aws_lb_controller_pod_identity.iam_role_name
}

output "cluster_oidc_issuer_url" {
  description = "The URL on the EKS cluster for the OpenID Connect identity provider"
  value       = module.eks.cluster_oidc_issuer_url
}

output "cluster_platform_version" {
  description = "The platform version for the cluster"
  value       = module.eks.cluster_platform_version
}

output "cluster_status" {
  description = "Status of the EKS cluster. One of `CREATING`, `ACTIVE`, `DELETING`, `FAILED`"
  value       = module.eks.cluster_status
}

output "cluster_primary_security_group_id" {
  description = "Cluster security group that was created by Amazon EKS for the cluster. Managed node groups use this security group for control-plane-to-data-plane communication. Referred to as 'Cluster security group' in the EKS console"
  value       = module.eks.cluster_primary_security_group_id
}

output "cluster_version" {
  description = "The Kubernetes version for the cluster"
  value       = module.eks.cluster_version
}

################################################################################
# Access Entry
################################################################################

output "access_entries" {
  description = "Map of access entries created and their attributes"
  value       = module.eks.access_entries
}

################################################################################
# Security Group
################################################################################

output "cluster_security_group_arn" {
  description = "Amazon Resource Name (ARN) of the cluster security group"
  value       = module.eks.cluster_security_group_arn
}

output "cluster_security_group_id" {
  description = "ID of the cluster security group"
  value       = module.eks.cluster_security_group_id
}

output "node_security_group_arn" {
  description = "Amazon Resource Name (ARN) of the node shared security group"
  value       = module.eks.node_security_group_arn
}

output "node_security_group_id" {
  description = "ID of the node shared security group"
  value       = module.eks.node_security_group_id
}

################################################################################
# IRSA
################################################################################

output "oidc_provider" {
  description = "The OpenID Connect identity provider (issuer URL without leading `https://`)"
  value       = module.eks.oidc_provider
}

output "oidc_provider_arn" {
  description = "ARN of the OIDC Provider for IRSA"
  value       = module.eks.oidc_provider_arn
}

output "backend_role_arn" {
  description = "IAM role ARN for backend application (Pod Identity)"
  value       = module.backend_pod_identity.iam_role_arn
}

################################################################################
# IAM Role
################################################################################

output "cluster_iam_role_name" {
  description = "IAM role name of the EKS cluster"
  value       = module.eks.cluster_iam_role_name
}

output "cluster_iam_role_arn" {
  description = "IAM role ARN of the EKS cluster"
  value       = module.eks.cluster_iam_role_arn
}

output "cluster_iam_role_unique_id" {
  description = "Stable and unique string identifying the IAM role"
  value       = module.eks.cluster_iam_role_unique_id
}

################################################################################
# EKS Addons
################################################################################

output "cluster_addons" {
  description = "Map of attribute maps for all EKS cluster addons enabled"
  value       = module.eks.cluster_addons
}

################################################################################
# Auto Mode
################################################################################

output "node_iam_role_name" {
  description = "Name of the IAM role for Auto Mode nodes"
  value       = module.eks.node_iam_role_name
}

output "node_iam_role_arn" {
  description = "ARN of the IAM role for Auto Mode nodes"
  value       = module.eks.node_iam_role_arn
}

output "node_iam_role_unique_id" {
  description = "Stable and unique string identifying the IAM role for Auto Mode nodes"
  value       = module.eks.node_iam_role_unique_id
}

################################################################################
# CloudWatch Log Group
################################################################################

output "cloudwatch_log_group_name" {
  description = "Name of cloudwatch log group created"
  value       = module.eks.cloudwatch_log_group_name
}

output "cloudwatch_log_group_arn" {
  description = "Arn of cloudwatch log group created"
  value       = module.eks.cloudwatch_log_group_arn
}

################################################################################
# Pod Identity Roles (created in this module)
################################################################################

output "ebs_csi_driver_role_arn" {
  description = "ARN of the IAM role for EBS CSI driver (Pod Identity)"
  value       = module.ebs_csi_pod_identity.iam_role_arn
}

output "external_secrets_role_arn" {
  description = "ARN of the IAM role for External Secrets Operator (Pod Identity)"
  value       = module.external_secrets_pod_identity.iam_role_arn
}

output "velero_role_arn" {
  description = "ARN of the IAM role for Velero (Pod Identity)"
  value       = module.velero_pod_identity.iam_role_arn
}

output "loki_role_arn" {
  description = "ARN of the IAM role for Loki (Pod Identity)"
  value       = module.loki_pod_identity.iam_role_arn
}

output "tempo_role_arn" {
  description = "ARN of the IAM role for Tempo (Pod Identity)"
  value       = module.tempo_pod_identity.iam_role_arn
}

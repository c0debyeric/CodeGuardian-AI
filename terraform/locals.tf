
# Reuse centrally managed security groups across all tiers
locals {
  security_group_ids = {
    eks_cluster   = module.eks_cluster_sg.security_group_id
    rds           = module.rds_sg.security_group_id
    vpc_endpoints = module.vpc_endpoints_sg.security_group_id
  }
}

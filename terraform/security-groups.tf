# Security Groups Module
# Centralized security group management for all infrastructure layers
# Using official terraform-aws-modules/security-group/aws module

# ==========================================
# ALB Security Group (Public-facing)
# ==========================================
module "alb_sg" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "~> 5.0"

  name        = "${var.cluster_name}-alb-sg"
  description = "Security group for Application Load Balancer"
  vpc_id      = module.networking.vpc_id

  ingress_with_cidr_blocks = [
    {
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      cidr_blocks = "0.0.0.0/0"
      description = "HTTPS from internet"
    },
    {
      from_port   = 80
      to_port     = 80
      protocol    = "tcp"
      cidr_blocks = "0.0.0.0/0"
      description = "HTTP from internet"
    }
  ]

  egress_with_source_security_group_id = [
    {
      from_port                = 0
      to_port                  = 65535
      protocol                 = "tcp"
      source_security_group_id = module.eks_cluster_sg.security_group_id
      description              = "Traffic to EKS cluster"
    }
  ]

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-alb-sg"
  })
}

# ==========================================
# EKS Cluster Security Group
# ==========================================
module "eks_cluster_sg" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "~> 5.0"

  name        = "${var.cluster_name}-eks-cluster-sg"
  description = "Security group for EKS cluster control plane and nodes"
  vpc_id      = module.networking.vpc_id

  ingress_with_source_security_group_id = [
    {
      from_port                = 0
      to_port                  = 65535
      protocol                 = "tcp"
      source_security_group_id = module.alb_sg.security_group_id
      description              = "Traffic from ALB"
    }
  ]

  ingress_with_self = [
    {
      from_port   = 0
      to_port     = 65535
      protocol    = "-1"
      description = "Allow all traffic within cluster"
    }
  ]

  egress_with_source_security_group_id = [
    {
      from_port                = 5432
      to_port                  = 5432
      protocol                 = "tcp"
      source_security_group_id = module.rds_sg.security_group_id
      description              = "PostgreSQL to RDS"
    },
    {
      from_port                = 443
      to_port                  = 443
      protocol                 = "tcp"
      source_security_group_id = module.vpc_endpoints_sg.security_group_id
      description              = "HTTPS to VPC endpoints"
    }
  ]

  egress_with_cidr_blocks = [
    {
      from_port   = 0
      to_port     = 0
      protocol    = "-1"
      cidr_blocks = "0.0.0.0/0"
      description = "Allow all outbound traffic"
    }
  ]

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-eks-cluster-sg"
  })
}

# ==========================================
# RDS Security Group
# ==========================================
module "rds_sg" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "~> 5.0"

  name        = "${var.cluster_name}-rds-sg"
  description = "Security group for RDS PostgreSQL database"
  vpc_id      = module.networking.vpc_id

  ingress_with_source_security_group_id = [
    {
      from_port                = 5432
      to_port                  = 5432
      protocol                 = "tcp"
      source_security_group_id = module.eks_cluster_sg.security_group_id
      description              = "PostgreSQL from EKS cluster"
    }
  ]

  # No outbound rules - RDS doesn't need egress
  egress_rules = []

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-rds-sg"
  })
}

# EKS managed-node-group nodes are attached to the EKS-created cluster
# primary security group, NOT our custom eks_cluster_sg above. Allow
# Postgres from that SG so backend pods can reach RDS.
resource "aws_security_group_rule" "rds_from_eks_primary" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = module.rds_sg.security_group_id
  source_security_group_id = module.eks.cluster_primary_security_group_id
  description              = "PostgreSQL from EKS primary cluster SG (managed node group)"
}

# ==========================================
# VPC Endpoints Security Group
# ==========================================
module "vpc_endpoints_sg" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "~> 5.0"

  name        = "${var.cluster_name}-vpc-endpoints-sg"
  description = "Security group for VPC endpoints"
  vpc_id      = module.networking.vpc_id

  ingress_with_source_security_group_id = [
    {
      from_port                = 443
      to_port                  = 443
      protocol                 = "tcp"
      source_security_group_id = module.eks_cluster_sg.security_group_id
      description              = "HTTPS from EKS cluster"
    }
  ]

  ingress_with_cidr_blocks = [
    {
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      cidr_blocks = var.vpc_cidr
      description = "HTTPS from VPC"
    }
  ]

  egress_with_cidr_blocks = [
    {
      from_port   = 0
      to_port     = 0
      protocol    = "-1"
      cidr_blocks = "0.0.0.0/0"
      description = "Allow all outbound traffic"
    }
  ]

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-vpc-endpoints-sg"
  })
}

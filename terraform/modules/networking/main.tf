# VPC Module - Creates the network foundation for EKS cluster
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 6.6"

  name = "${var.vpc_name}-vpc"
  cidr = var.vpc_cidr

  # Distribute subnets across first 3 AZs for high availability
  azs = slice(data.aws_availability_zones.available.names, 0, 3)

  # Public subnets (/24) - Host internet-facing load balancers and NAT gateways
  public_subnets = var.public_subnet_cidrs

  # Private subnets (/19) - Host EKS worker nodes and application workloads
  private_subnets = var.private_subnet_cidrs
  # Database subnets (/27) - Isolated subnets for RDS instances
  database_subnets = var.database_subnets

  # One NAT Gateway per availability zone
  enable_nat_gateway     = true
  single_nat_gateway     = false
  one_nat_gateway_per_az = true

  # Required for EKS nodes to resolve service endpoints
  enable_dns_hostnames = true
  enable_dns_support   = true

  # Internet gateway for public subnet internet access
  create_igw = true

  # Tag public subnets for AWS Load Balancer Controller to create internet-facing load balancers
  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }

  # Tag private subnets for AWS Load Balancer Controller to create internal load balancers
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
  }

  tags = var.tags
}
# Data source to dynamically fetch available AZs in the current region
data "aws_availability_zones" "available" {
  state = "available"
}

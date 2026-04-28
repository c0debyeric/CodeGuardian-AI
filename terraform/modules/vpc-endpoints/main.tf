# VPC Endpoints for CodeGuardian AI
# Cost-optimized set: S3 (free), ECR API + DKR (required for container image data transfer)
# Use NAT Gateway for: STS (tiny tokens), Bedrock (API calls), Secrets Manager, CloudWatch

# ============================================================================
# Gateway Endpoints (FREE)
# ============================================================================

# S3 Gateway Endpoint (no cost - always include)
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = var.private_route_table_ids

  tags = merge(var.tags, {
    Name = "${var.app_name}-s3-endpoint"
  })
}

# ============================================================================
# Interface Endpoints (REQUIRED for private EKS)
# ============================================================================

# ECR API Interface Endpoint - Required for pulling container images
resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.region}.ecr.api"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnets
  security_group_ids  = [var.security_group_id]
  private_dns_enabled = true

  tags = merge(var.tags, {
    Name = "${var.app_name}-ecr-api-endpoint"
  })
}

# ECR DKR Interface Endpoint - Required for pulling container images
resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id              = var.vpc_id
  service_name        = "com.amazonaws.${var.region}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.private_subnets
  security_group_ids  = [var.security_group_id]
  private_dns_enabled = true

  tags = merge(var.tags, {
    Name = "${var.app_name}-ecr-dkr-endpoint"
  })
}


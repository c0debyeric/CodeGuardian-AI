output "s3_endpoint_id" {
  value       = aws_vpc_endpoint.s3.id
  description = "ID of the S3 VPC endpoint"
}

output "ecr_api_endpoint_id" {
  value       = aws_vpc_endpoint.ecr_api.id
  description = "ID of the ECR API VPC endpoint"
}

output "ecr_dkr_endpoint_id" {
  value       = aws_vpc_endpoint.ecr_dkr.id
  description = "ID of the ECR DKR VPC endpoint"
}

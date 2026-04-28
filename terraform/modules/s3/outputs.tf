output "bucket_id" {
  value       = aws_s3_bucket.terraform_state.id
  description = "The ID of the S3 bucket"
}

output "bucket_arn" {
  value       = aws_s3_bucket.terraform_state.arn
  description = "The ARN of the S3 bucket"
}

output "bucket_name" {
  value       = aws_s3_bucket.terraform_state.bucket
  description = "The name of the S3 bucket"
}

# Observability bucket outputs
output "observability_bucket_name" {
  value       = var.create_observability_bucket ? aws_s3_bucket.observability[0].bucket : null
  description = "The name of the observability S3 bucket"
}

output "observability_bucket_arn" {
  value       = var.create_observability_bucket ? aws_s3_bucket.observability[0].arn : null
  description = "The ARN of the observability S3 bucket"
}

# Velero bucket outputs
output "velero_bucket_name" {
  value       = var.create_velero_bucket ? aws_s3_bucket.velero[0].bucket : null
  description = "The name of the Velero backup S3 bucket"
}

output "velero_bucket_arn" {
  value       = var.create_velero_bucket ? aws_s3_bucket.velero[0].arn : null
  description = "The ARN of the Velero backup S3 bucket"
}

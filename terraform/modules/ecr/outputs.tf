output "backend_url" {
  value       = aws_ecr_repository.backend.repository_url
  description = "URL of the backend ECR repository"
}

output "admin_ui_url" {
  value       = aws_ecr_repository.admin_ui.repository_url
  description = "URL of the admin-ui ECR repository"
}

output "registry_id" {
  value       = aws_ecr_repository.backend.registry_id
  description = "The account ID of the registry"
}

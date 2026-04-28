output "backend_url" {
  value       = aws_ecr_repository.backend.repository_url
  description = "URL of the backend ECR repository"
}

output "frontend_url" {
  value       = aws_ecr_repository.frontend.repository_url
  description = "URL of the frontend ECR repository"
}

output "registry_id" {
  value       = aws_ecr_repository.backend.registry_id
  description = "The account ID of the registry"
}

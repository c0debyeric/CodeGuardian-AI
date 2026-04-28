output "db_credentials_arn" {
  value       = aws_secretsmanager_secret.db_credentials.arn
  description = "ARN of the database credentials secret"
}

output "db_credentials_name" {
  value       = aws_secretsmanager_secret.db_credentials.name
  description = "Name of the database credentials secret"
}

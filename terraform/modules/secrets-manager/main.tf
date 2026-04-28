# CodeGuardian AI - Secrets Manager
# Stores database credentials and application secrets

# Database Credentials Secret
resource "aws_secretsmanager_secret" "db_credentials" {
  name                    = "${var.secret_name_prefix}/${var.db_credentials_secret_name}"
  description             = "PostgreSQL database credentials for CodeGuardian"
  recovery_window_in_days = var.recovery_window_in_days

  tags = var.tags
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = var.db_username
    password = var.db_password
    host     = var.db_host
    port     = var.db_port
    dbname   = var.db_name
  })
}


resource "random_password" "db_password" {
  length  = 32
  special = true
}

module "db" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.13"

  identifier = "${var.cluster_name}-db"

  engine               = "postgres"
  engine_version       = "18.1"
  family               = "postgres18"
  major_engine_version = "18"
  instance_class       = var.instance_class

  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = replace(var.cluster_name, "-", "")
  username = var.db_username
  password = coalesce(var.db_password, random_password.db_password.result)
  port     = 5432

  multi_az               = var.multi_az
  db_subnet_group_name   = aws_db_subnet_group.group.name
  vpc_security_group_ids = [var.security_group_id]

  maintenance_window      = "sun:04:00-sun:05:00"
  backup_window           = "03:00-04:00"
  backup_retention_period = var.backup_retention_days

  skip_final_snapshot = var.skip_final_snapshot

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  create_cloudwatch_log_group     = true

  deletion_protection   = var.deletion_protection
  copy_tags_to_snapshot = true

  tags = var.tags
}

# DB Subnet Group (still created manually for flexibility)
resource "aws_db_subnet_group" "group" {
  name       = "${var.cluster_name}-db-subnet-group"
  subnet_ids = var.db_subnets

  tags = merge(var.tags, {
    Name = "${var.cluster_name}-db-subnet-group"
  })
}


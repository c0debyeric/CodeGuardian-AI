# generate backend configuration file after apply
# resource "local_file" "backend_config" {
#   filename = "${path.root}/gen-backend.tf"
#   content  = <<EOF
# terraform {
#   backend "s3" {
#     bucket       = "${aws_s3_bucket.terraform_state.bucket}"
#     key          = "project.tfstate"
#     region       = "${var.region}"
#     use_lockfile = true
#     encrypt      = true
#   }
# }
# EOF
# }


# S3 bucket for Terraform state files
resource "aws_s3_bucket" "terraform_state" {
  bucket = var.bucket_name
  tags   = var.tags
}


# Enable versioning for state file history
resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Enable server-side encryption with AWS-managed KMS key
resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
      # Uses AWS-managed key alias/aws/s3 by default (no additional cost)
    }
    bucket_key_enabled = true
  }
}

# Block public access on state bucket
resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}


# Bucket policy for enhanced security
resource "aws_s3_bucket_policy" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.terraform_state.arn,
          "${aws_s3_bucket.terraform_state.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
      {
        Sid       = "DenyUnencryptedObjectUploads"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.terraform_state.arn}/*"
        Condition = {
          StringNotEquals = {
            "s3:x-amz-server-side-encryption" = ["aws:kms", "AES256"]
          }
        }
      }
    ]
  })
}

# Lifecycle configuration to manage old versions
resource "aws_s3_bucket_lifecycle_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    id     = "cleanup_old_versions"
    status = "Enabled"

    filter {
      prefix = "tfstate/"
    }

    # Delete noncurrent versions after 90 days
    noncurrent_version_expiration {
      noncurrent_days = 90
    }

    # Move noncurrent versions to cheaper storage after 30 days
    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "STANDARD_IA"
    }

    # For very old versions, move to Glacier
    noncurrent_version_transition {
      noncurrent_days = 60
      storage_class   = "GLACIER"
    }
  }
}

# ============================================================================
# Observability S3 Bucket (Loki logs + Tempo traces)
# ============================================================================
resource "aws_s3_bucket" "observability" {
  count  = var.create_observability_bucket ? 1 : 0
  bucket = "${var.bucket_name}-observability"
  tags   = merge(var.tags, { Purpose = "observability" })
}

resource "aws_s3_bucket_versioning" "observability" {
  count  = var.create_observability_bucket ? 1 : 0
  bucket = aws_s3_bucket.observability[0].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "observability" {
  count  = var.create_observability_bucket ? 1 : 0
  bucket = aws_s3_bucket.observability[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "observability" {
  count  = var.create_observability_bucket ? 1 : 0
  bucket = aws_s3_bucket.observability[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "observability" {
  count  = var.create_observability_bucket ? 1 : 0
  bucket = aws_s3_bucket.observability[0].id

  rule {
    id     = "loki_logs_lifecycle"
    status = "Enabled"

    filter {
      prefix = "loki/"
    }

    # Move logs to IA after 30 days
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    # Delete logs after 90 days
    expiration {
      days = 90
    }
  }

  rule {
    id     = "tempo_traces_lifecycle"
    status = "Enabled"

    filter {
      prefix = "tempo/"
    }

    # Move traces to IA after 30 days (AWS minimum for STANDARD_IA)
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    # Delete traces after 60 days (must be > transition days of 30)
    expiration {
      days = 60
    }
  }
}

# ============================================================================
# Velero Backup S3 Bucket
# ============================================================================
resource "aws_s3_bucket" "velero" {
  count  = var.create_velero_bucket ? 1 : 0
  bucket = "${var.bucket_name}-velero-backups"
  tags   = merge(var.tags, { Purpose = "velero-backups" })
}

resource "aws_s3_bucket_versioning" "velero" {
  count  = var.create_velero_bucket ? 1 : 0
  bucket = aws_s3_bucket.velero[0].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "velero" {
  count  = var.create_velero_bucket ? 1 : 0
  bucket = aws_s3_bucket.velero[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "velero" {
  count  = var.create_velero_bucket ? 1 : 0
  bucket = aws_s3_bucket.velero[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "velero" {
  count  = var.create_velero_bucket ? 1 : 0
  bucket = aws_s3_bucket.velero[0].id

  rule {
    id     = "velero_backup_lifecycle"
    status = "Enabled"

    filter {
      prefix = "backups/"
    }

    # Move backups to IA after 30 days
    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    # Move to Glacier after 90 days
    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    # Delete after 365 days
    expiration {
      days = 365
    }
  }
}



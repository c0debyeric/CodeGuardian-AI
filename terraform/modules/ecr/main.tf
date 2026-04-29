# ECR Repositories

resource "aws_ecr_repository" "backend" {
  name                 = "${var.repository_prefix}/${var.backend_repo_name}"
  image_tag_mutability = var.image_tag_mutability
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = var.scan_on_push
  }

  tags = var.tags
}

resource "aws_ecr_repository" "admin_ui" {
  name                 = "${var.repository_prefix}/${var.admin_ui_repo_name}"
  image_tag_mutability = var.image_tag_mutability
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = var.scan_on_push
  }

  tags = var.tags
}

resource "aws_ecr_lifecycle_policy" "retention" {
  for_each = toset([
    aws_ecr_repository.backend.name,
    aws_ecr_repository.admin_ui.name
  ])

  repository = each.value

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last ${var.tagged_image_retention_count} tagged images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = var.lifecycle_tag_prefix
          countType     = "imageCountMoreThan"
          countNumber   = var.tagged_image_retention_count
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Keep last ${var.untagged_image_retention_count} untagged images"
        selection = {
          tagStatus   = "untagged"
          countType   = "imageCountMoreThan"
          countNumber = var.untagged_image_retention_count
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

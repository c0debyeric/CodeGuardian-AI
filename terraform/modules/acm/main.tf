resource "aws_acm_certificate" "cert" {
  domain_name       = var.domain_name
  validation_method = "DNS"

  tags = var.tags

  lifecycle {
    create_before_destroy = true
  }
}

# We do NOT include the aws_acm_certificate_validation resource
# because the DNS records are managed externally (Cloudflare).
# Terraform will create the request and finish.
# The cert will stay in "Pending Validation" until the user adds the CNAMEs.

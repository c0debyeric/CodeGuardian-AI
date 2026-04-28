output "certificate_arn" {
  description = "ARN of the ACM certificate"
  value       = aws_acm_certificate.cert.arn
}

output "validation_records" {
  description = "List of DNS records to add to Cloudflare for validation"
  value = [
    for dvo in aws_acm_certificate.cert.domain_validation_options : {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  ]
}

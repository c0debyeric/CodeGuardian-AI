# VPC Flow Logs using standalone module (best practice as of v6.x)
# In-module flow logs are deprecated and will be removed in v7.0
module "vpc_flow_log" {
  source  = "terraform-aws-modules/vpc/aws//modules/flow-log"
  version = "~> 6.6"

  name   = "${var.vpc_name}-vpc-flow-log"
  vpc_id = module.vpc.vpc_id

  # CloudWatch Logs destination (default)
  log_destination_type = "cloud-watch-logs"

  # CloudWatch Log Group configuration
  create_cloudwatch_log_group            = true
  cloudwatch_log_group_retention_in_days = var.log_retention_in_days
  cloudwatch_log_group_class             = "STANDARD"

  # Create IAM role for CloudWatch delivery
  create_iam_role = true

  # Capture all traffic (ACCEPT, REJECT, ALL)
  traffic_type = "ALL"

  # Aggregate flows every 10 minutes (cost optimization vs 1 minute)
  max_aggregation_interval = 600

  tags = var.tags
}

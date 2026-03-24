# SNS topic for alarm notifications
resource "aws_sns_topic" "alarms" {
  name = "${local.name_prefix}-alarms"
}

# Email subscription (you must confirm the subscription email)
resource "aws_sns_topic_subscription" "alarms_email" {
  count     = local.notifications_enabled ? 1 : 0
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.budget_email
}

output "alarms_sns_topic_arn" {
  value = aws_sns_topic.alarms.arn
}
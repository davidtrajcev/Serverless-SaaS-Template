resource "aws_sqs_queue" "jobs" {
  name                       = "${local.name_prefix}-jobs"
  visibility_timeout_seconds = 30
  message_retention_seconds  = 86400 # 1 day
}

output "jobs_queue_url" {
  value = aws_sqs_queue.jobs.url
}

output "jobs_queue_arn" {
  value = aws_sqs_queue.jobs.arn
}
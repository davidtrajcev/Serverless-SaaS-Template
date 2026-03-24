# If messages are sitting too long, worker is stuck or failing
resource "aws_cloudwatch_metric_alarm" "sqs_age_oldest" {
  alarm_name          = "${local.name_prefix}-sqs-age-oldest"
  alarm_description   = "SQS oldest message age too high"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateAgeOfOldestMessage"
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 300
  comparison_operator = "GreaterThanOrEqualToThreshold"

  dimensions = {
    QueueName = aws_sqs_queue.jobs.name
  }
}
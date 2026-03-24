# Alarm when API Lambda has errors
resource "aws_cloudwatch_metric_alarm" "api_lambda_errors" {
  alarm_name          = "${local.name_prefix}-api-lambda-errors"
  alarm_description   = "API Lambda errors > 0"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"

  dimensions = {
    FunctionName = aws_lambda_function.api.function_name
  }
}

# Alarm when worker Lambda has errors
resource "aws_cloudwatch_metric_alarm" "worker_lambda_errors" {
  alarm_name          = "${local.name_prefix}-worker-lambda-errors"
  alarm_description   = "Worker Lambda errors > 0"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"

  dimensions = {
    FunctionName = aws_lambda_function.worker.function_name
  }
}

# Optional: throttles (usually should be 0)
resource "aws_cloudwatch_metric_alarm" "api_lambda_throttles" {
  alarm_name          = "${local.name_prefix}-api-lambda-throttles"
  alarm_description   = "API Lambda throttles > 0"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
  namespace           = "AWS/Lambda"
  metric_name         = "Throttles"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"

  dimensions = {
    FunctionName = aws_lambda_function.api.function_name
  }
}
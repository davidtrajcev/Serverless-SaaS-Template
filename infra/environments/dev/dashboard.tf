resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${local.name_prefix}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric",
        x      = 0,
        y      = 0,
        width  = 12,
        height = 6,
        properties = {
          title  = "API Lambda Errors (sum)",
          region = data.aws_region.current.name,
          stat   = "Sum",
          period = 300,
          metrics = [
            ["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.api.function_name]
          ]
        }
      },
      {
        type   = "metric",
        x      = 12,
        y      = 0,
        width  = 12,
        height = 6,
        properties = {
          title  = "API Lambda Duration p95 (ms)",
          region = data.aws_region.current.name,
          stat   = "p95",
          period = 300,
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", aws_lambda_function.api.function_name]
          ]
        }
      },
      {
        type   = "metric",
        x      = 0,
        y      = 6,
        width  = 12,
        height = 6,
        properties = {
          title  = "Worker Lambda Errors (sum)",
          region = data.aws_region.current.name,
          stat   = "Sum",
          period = 300,
          metrics = [
            ["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.worker.function_name]
          ]
        }
      },
      {
        type   = "metric",
        x      = 12,
        y      = 6,
        width  = 12,
        height = 6,
        properties = {
          title  = "SQS Age Of Oldest Message (max, seconds)",
          region = data.aws_region.current.name,
          stat   = "Maximum",
          period = 300,
          metrics = [
            ["AWS/SQS", "ApproximateAgeOfOldestMessage", "QueueName", aws_sqs_queue.jobs.name]
          ]
        }
      }
    ]
  })
}

output "cloudwatch_dashboard_name" {
  value = aws_cloudwatch_dashboard.main.dashboard_name
}
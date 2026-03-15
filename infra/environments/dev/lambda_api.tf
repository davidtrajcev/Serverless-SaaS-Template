data "archive_file" "api_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../../../services/api"
  output_path = "${path.module}/.build/api.zip"
}

resource "aws_iam_role" "api_lambda_role" {
  name = "${local.name_prefix}-api-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "lambda.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "api_basic" {
  role       = aws_iam_role.api_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Least-privilege DynamoDB permissions for this Lambda
resource "aws_iam_role_policy" "api_ddb" {
  role = aws_iam_role.api_lambda_role.name
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "dynamodb:PutItem",
          "dynamodb:Query",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem"
        ],
        Resource = [aws_dynamodb_table.app.arn]
      },
      {
        Effect   = "Allow",
        Action   = ["sqs:SendMessage"],
        Resource = [aws_sqs_queue.jobs.arn]
      }
    ]
  })
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${local.name_prefix}-api"
  retention_in_days = 7
}

resource "aws_lambda_function" "api" {
  function_name = "${local.name_prefix}-api"
  role          = aws_iam_role.api_lambda_role.arn
  runtime       = "python3.12"
  handler       = "app.handler"

  filename         = data.archive_file.api_zip.output_path
  source_code_hash = data.archive_file.api_zip.output_base64sha256

  timeout     = 10
  memory_size = 128

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.app.name
      QUEUE_URL  = aws_sqs_queue.jobs.url
    }
  }

  depends_on = [aws_cloudwatch_log_group.api]
}

output "api_lambda_name" {
  value = aws_lambda_function.api.function_name
}
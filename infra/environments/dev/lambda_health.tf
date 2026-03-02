data "archive_file" "health_zip" {
  type        = "zip"
  source_dir  = "${path.root}/../../../services/health"
  output_path = "${path.root}/.build/health.zip"
}

resource "aws_iam_role" "health_lambda_role" {
  name = "${local.name_prefix}-health-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "lambda.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "health_basic" {
  role       = aws_iam_role.health_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_cloudwatch_log_group" "health" {
  name              = "/aws/lambda/${local.name_prefix}-health"
  retention_in_days = 7
}

resource "aws_lambda_function" "health" {
  function_name = "${local.name_prefix}-health"
  role          = aws_iam_role.health_lambda_role.arn
  runtime       = "python3.12"
  handler       = "app.handler"

  filename         = data.archive_file.health_zip.output_path
  source_code_hash = data.archive_file.health_zip.output_base64sha256

  timeout     = 5
  memory_size = 128

  depends_on = [aws_cloudwatch_log_group.health]
}

output "health_lambda_name" {
  value = aws_lambda_function.health.function_name
}

output "health_lambda_arn" {
  value = aws_lambda_function.health.arn
}
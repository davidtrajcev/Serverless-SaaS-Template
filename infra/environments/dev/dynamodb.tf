resource "aws_dynamodb_table" "app" {
  name         = "${local.name_prefix}-app"
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "PK"
  range_key = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  # Good safety feature, still cheap
  point_in_time_recovery {
    enabled = true
  }
}

output "dynamodb_table_name" {
  value = aws_dynamodb_table.app.name
}

output "dynamodb_table_arn" {
  value = aws_dynamodb_table.app.arn
}
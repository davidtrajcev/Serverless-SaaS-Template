# HTTP API (API Gateway v2)
resource "aws_apigatewayv2_api" "http" {
  name          = "${local.name_prefix}-http"
  protocol_type = "HTTP"
  cors_configuration {
    allow_origins = [
      "https://${aws_cloudfront_distribution.frontend.domain_name}"
    ]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["authorization", "content-type", "x-tenant-id"]
    max_age       = 3600
  }
}

# JWT authorizer using Cognito
resource "aws_apigatewayv2_authorizer" "cognito_jwt" {
  api_id           = aws_apigatewayv2_api.http.id
  name             = "${local.name_prefix}-jwt"
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]

  jwt_configuration {
    issuer   = "https://cognito-idp.${data.aws_region.current.name}.amazonaws.com/${aws_cognito_user_pool.this.id}"
    audience = [aws_cognito_user_pool_client.this.id]
  }
}

# Lambda integration
resource "aws_apigatewayv2_integration" "health" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.health.invoke_arn
  payload_format_version = "2.0"
}

# Route: GET /health (JWT protected)
resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.health.id}"

  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito_jwt.id
}

# Default stage (auto-deploy)
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true
  default_route_settings {
    throttling_rate_limit  = 10 # steady rate (req/s)
    throttling_burst_limit = 20 # burst
  }
}

# Allow API Gateway to invoke the Lambda
resource "aws_lambda_permission" "allow_apigw_health" {
  statement_id  = "AllowInvokeFromApiGatewayHealth"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.health.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}

output "http_api_endpoint" {
  value = aws_apigatewayv2_api.http.api_endpoint
}
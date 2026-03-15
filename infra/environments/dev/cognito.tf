data "aws_region" "current" {}

resource "aws_cognito_user_pool" "this" {
  name = "${local.name_prefix}-users"

  # Keep it simple + secure
  password_policy {
    minimum_length    = 12
    require_lowercase = true
    require_numbers   = true
    require_uppercase = true
    require_symbols   = false
  }

  # Optional, but nice for SaaS: require verified email
  auto_verified_attributes = ["email"]
}

resource "aws_cognito_user_pool_client" "this" {
  name         = "${local.name_prefix}-web-client"
  user_pool_id = aws_cognito_user_pool.this.id

  generate_secret = false

  # Simple auth flows for development
  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["implicit"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  supported_identity_providers         = ["COGNITO"]

  callback_urls = [
    "https://${aws_cloudfront_distribution.frontend.domain_name}/"
  ]

  logout_urls = [
    "https://${aws_cloudfront_distribution.frontend.domain_name}/"
  ]
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.this.id
}

output "cognito_user_pool_client_id" {
  value = aws_cognito_user_pool_client.this.id
}

# JWT issuer for API Gateway JWT authorizer later
output "cognito_issuer" {
  value = "https://cognito-idp.${data.aws_region.current.name}.amazonaws.com/${aws_cognito_user_pool.this.id}"
}

resource "random_id" "cognito_domain_suffix" {
  byte_length = 3
}

resource "aws_cognito_user_pool_domain" "this" {
  domain       = "${local.name_prefix}-${random_id.cognito_domain_suffix.hex}"
  user_pool_id = aws_cognito_user_pool.this.id
}

output "cognito_domain" {
  value = aws_cognito_user_pool_domain.this.domain
}

output "cognito_hosted_ui_base_url" {
  value = "https://${aws_cognito_user_pool_domain.this.domain}.auth.${data.aws_region.current.name}.amazoncognito.com"
}
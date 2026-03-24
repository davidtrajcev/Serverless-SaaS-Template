locals {
  api_base     = aws_apigatewayv2_api.http.api_endpoint
  redirect_uri = "https://${aws_cloudfront_distribution.frontend.domain_name}/"
  hosted_ui    = "https://${aws_cognito_user_pool_domain.this.domain}.auth.${data.aws_region.current.name}.amazoncognito.com"
  client_id    = aws_cognito_user_pool_client.this.id
}

resource "aws_s3_object" "index" {
  bucket = aws_s3_bucket.frontend.id
  key    = "index.html"

  content = templatefile("${path.module}/../../../frontend/index.html", {
    API_BASE          = local.api_base
    HOSTED_UI_BASE    = local.hosted_ui
    COGNITO_CLIENT_ID = local.client_id
    REDIRECT_URI      = local.redirect_uri
  })

  etag         = filemd5("${path.module}/../../../frontend/index.html")
  content_type = "text/html"
}
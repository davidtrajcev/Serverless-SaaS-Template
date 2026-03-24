resource "aws_apigatewayv2_route" "tenant_invite" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "POST /tenant/invite"
  target    = "integrations/${aws_apigatewayv2_integration.api.id}"

  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito_jwt.id
}
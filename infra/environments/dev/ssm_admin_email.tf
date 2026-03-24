resource "aws_ssm_parameter" "admin_email" {
  name  = "/${local.name_prefix}/admin_email"
  type  = "SecureString"
  value = var.admin_email
}
data "aws_caller_identity" "current" {}

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

resource "aws_iam_role" "github_actions_plan" {
  name = "${local.name_prefix}-github-terraform-plan"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = [
            "repo:davidtrajcev/Serverless-SaaS-Template:pull_request",
            "repo:davidtrajcev/Serverless-SaaS-Template:ref:refs/heads/*"
          ]
        }
      }
    }]
  })
}

# AWS-managed: read-only across AWS services (covers Terraform refresh/plan reads)
resource "aws_iam_role_policy_attachment" "github_plan_readonly" {
  role       = aws_iam_role.github_actions_plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

# Custom: allow Terraform backend access (S3 state + DynamoDB lock)
resource "aws_iam_policy" "github_plan_backend" {
  name        = "${local.name_prefix}-github-tf-backend"
  description = "Terraform backend access for CI plan (state bucket + lock table)"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "StateBucketList"
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetBucketLocation"]
        Resource = "arn:aws:s3:::serverless-saas-tfstate-f4ac6eda"
      },
      {
        Sid      = "StateObjectsRW"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "arn:aws:s3:::serverless-saas-tfstate-f4ac6eda/serverless-saas/dev/*"
      },
      {
        Sid      = "LockTableRW"
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem", "dynamodb:UpdateItem"]
        Resource = "arn:aws:dynamodb:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:table/terraform-locks"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "github_plan_backend_attach" {
  role       = aws_iam_role.github_actions_plan.name
  policy_arn = aws_iam_policy.github_plan_backend.arn
}

output "github_actions_plan_role_arn" {
  value = aws_iam_role.github_actions_plan.arn
}
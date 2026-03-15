# OIDC provider for GitHub (one per AWS account)
resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]

  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1"
  ]
}

# Change these to your GitHub org/user and repo name
variable "github_owner" {
  type    = string
  default = "davidtrajcev"
}

variable "github_repo" {
  type    = string
  default = "serverless-saas-terraform"
}

resource "aws_iam_role" "github_actions_terraform" {
  name = "${local.name_prefix}-github-terraform"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = {
        Federated = aws_iam_openid_connect_provider.github.arn
      },
      Action = "sts:AssumeRoleWithWebIdentity",
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        },
        StringLike = {
          # Allow only this repo. "ref:*" means any branch/PR; we’ll still gate apply in workflow.
          "token.actions.githubusercontent.com:sub" = "repo:${var.github_owner}/${var.github_repo}:*"
        }
      }
    }]
  })
}

# Minimal permissions for Terraform to manage your stack.
# For a portfolio repo, simplest is AdministratorAccess.
# If you want stricter least-privilege later, we can tighten it.
resource "aws_iam_role_policy_attachment" "github_admin" {
  role       = aws_iam_role.github_actions_terraform.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

output "github_actions_role_arn" {
  value = aws_iam_role.github_actions_terraform.arn
}
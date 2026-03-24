variable "budget_email" {
  type        = string
  description = "Email to notify when budget threshold is reached"
  default     = ""
}

variable "monthly_budget_usd" {
  type        = number
  description = "Monthly budget limit in USD"
  default     = 5
}

resource "aws_budgets_budget" "monthly" {
  count        = local.notifications_enabled ? 1 : 0
  name         = "${local.name_prefix}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }
}
locals {
  name_prefix           = "saas-dev"
  notifications_enabled = length(trimspace(var.budget_email)) > 0
}
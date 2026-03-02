terraform {
  backend "s3" {
    bucket         = "serverless-saas-tfstate-f4ac6eda"
    key            = "serverless-saas/dev/terraform.tfstate"
    region         = "eu-north-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}
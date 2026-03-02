locals {
  name_prefix = "saas-dev"
}

resource "aws_s3_bucket" "hello" {
  bucket = "${local.name_prefix}-hello-${random_id.suffix.hex}"
}

resource "random_id" "suffix" {
  byte_length = 3
}

output "bucket_name" {
  value = aws_s3_bucket.hello.bucket
}
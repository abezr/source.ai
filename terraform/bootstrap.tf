# Bootstrap configuration to create Terraform backend resources
# This file uses local state to avoid the chicken-and-egg problem

terraform {
  # Intentionally using local backend for bootstrap
}

provider "aws" {
  region = "us-east-1"  # Hardcoded for bootstrap
}

# S3 Bucket for Terraform State
resource "aws_s3_bucket" "terraform_state" {
  bucket = "hbi-terraform-state"

  tags = {
    Name        = "hbi-terraform-state"
    Environment = "bootstrap"
    Project     = "HBI"
  }
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# DynamoDB Table for Terraform State Locking
resource "aws_dynamodb_table" "terraform_locks" {
  name         = "hbi-terraform-locks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = {
    Name        = "hbi-terraform-locks"
    Environment = "bootstrap"
    Project     = "HBI"
  }
}

output "s3_bucket_name" {
  value = aws_s3_bucket.terraform_state.bucket
}

output "dynamodb_table_name" {
  value = aws_dynamodb_table.terraform_locks.name
}
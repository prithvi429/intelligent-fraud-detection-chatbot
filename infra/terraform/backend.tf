terraform {
  backend "s3" {
    bucket         = "your-terraform-state-bucket"  # Where Terraform state file lives
    key            = "fraud-chatbot/terraform.tfstate"  # Path (folder/file) inside bucket
    region         = "us-east-1"  # AWS Region for the bucket
    dynamodb_table = "terraform-locks"  # Optional, for state locking (prevents conflicts)
    encrypt        = true  # Encrypts state file with SSE (AWS-managed key)
  }
}

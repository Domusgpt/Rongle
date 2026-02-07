variable "aws_region" {
  default = "us-east-1"
}

variable "app_name" {
  default = "rongle-prod"
}

variable "db_username" {
  default = "rongle_admin"
}

variable "db_password" {
  sensitive = true
}

variable "jwt_secret" {
  sensitive = true
}

variable "gemini_api_key" {
  sensitive = true
}

variable "ecr_repo_url" {
  description = "ECR Repository URL for the Portal Image"
}

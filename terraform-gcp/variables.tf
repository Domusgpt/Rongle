variable "project_id" {
  description = "The GCP Project ID"
}

variable "region" {
  default = "us-central1"
}

variable "app_name" {
  default = "rongle-prod"
}

variable "container_image" {
  description = "GCR/Artifact Registry URL for the Portal Image"
}

variable "db_user" {
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

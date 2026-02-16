terraform {
  required_providers {
    google = {
      source = "hashicorp/google"
      version = "4.51.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ---------------------------------------------------------------------------
# Cloud Run Service (Portal)
# ---------------------------------------------------------------------------
resource "google_cloud_run_service" "portal" {
  name     = "${var.app_name}-portal"
  location = var.region

  template {
    spec {
      containers {
        image = var.container_image

        env {
          name = "DATABASE_URL"
          value = "postgresql://${var.db_user}:${var.db_password}@/${var.project_id}:${var.region}:${google_sql_database_instance.postgres.name}?host=/cloudsql/${var.project_id}:${var.region}:${google_sql_database_instance.postgres.name}"
        }
        env {
          name = "REDIS_URL"
          value = "redis://${google_redis_instance.cache.host}:${google_redis_instance.cache.port}/0"
        }
        env {
          name = "JWT_SECRET"
          value = var.jwt_secret
        }
        env {
          name = "GEMINI_API_KEY"
          value = var.gemini_api_key
        }

        # Cloud SQL Connection
        # Cloud Run needs the Cloud SQL Auth Proxy sidecar, handled via annotation in v1?
        # Actually in modern Cloud Run, we just use the volume mount or the connection annotation.
      }
    }

    metadata {
      annotations = {
        "run.googleapis.com/cloudsql-instances" = google_sql_database_instance.postgres.connection_name
        "run.googleapis.com/client-name"        = "terraform"
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  autogenerate_revision_name = true
}

# Allow unauthenticated access (public API)
data "google_iam_policy" "noauth" {
  binding {
    role = "roles/run.invoker"
    members = [
      "allUsers",
    ]
  }
}

resource "google_cloud_run_service_iam_policy" "noauth" {
  location    = google_cloud_run_service.portal.location
  project     = google_cloud_run_service.portal.project
  service     = google_cloud_run_service.portal.name
  policy_data = data.google_iam_policy.noauth.policy_data
}

# ---------------------------------------------------------------------------
# Cloud SQL (Postgres)
# ---------------------------------------------------------------------------
resource "google_sql_database_instance" "postgres" {
  name             = "${var.app_name}-db"
  database_version = "POSTGRES_15"
  region           = var.region
  deletion_protection = false # For dev/demo only

  settings {
    tier = "db-f1-micro" # Cheapest tier
  }
}

resource "google_sql_database" "database" {
  name     = "rongle_db"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "users" {
  name     = var.db_user
  instance = google_sql_database_instance.postgres.name
  password = var.db_password
}

# ---------------------------------------------------------------------------
# Memorystore (Redis)
# ---------------------------------------------------------------------------
resource "google_redis_instance" "cache" {
  name           = "${var.app_name}-redis"
  memory_size_gb = 1
  region         = var.region
  tier           = "BASIC" # Cheapest tier

  authorized_network = "default" # Assumes default VPC

  redis_version = "REDIS_7_0"
}

# ---------------------------------------------------------------------------
# Serverless VPC Access (Connector)
# Required for Cloud Run to talk to Redis (internal IP)
# ---------------------------------------------------------------------------
resource "google_vpc_access_connector" "connector" {
  name          = "${var.app_name}-vpc-con"
  region        = var.region
  ip_cidr_range = "10.8.0.0/28"
  network       = "default"
}

# Attach connector to Cloud Run
# Note: We need to update the cloud_run_service resource to use this annotation
# "run.googleapis.com/vpc-access-connector" = google_vpc_access_connector.connector.name

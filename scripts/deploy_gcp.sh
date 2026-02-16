#!/bin/bash
# Helper script to deploy Rongle to GCP using Terraform
# Usage: ./scripts/deploy_gcp.sh [plan|apply|destroy]

set -e

COMMAND=${1:-plan}

# 1. Check Dependencies
if ! command -v terraform &> /dev/null; then
    echo "❌ Error: terraform is not installed."
    exit 1
fi

if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI is not installed."
    exit 1
fi

# 2. Check Auth
echo "☁️  Checking GCP Authentication..."
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: No active GCP project found in gcloud config."
    echo "Run: gcloud config set project [PROJECT_ID]"
    exit 1
fi
echo "   Target Project: $PROJECT_ID"

# 3. Check App Secrets
if [ -z "$GEMINI_API_KEY" ] || [ -z "$JWT_SECRET" ]; then
    echo "⚠️ Warning: GEMINI_API_KEY or JWT_SECRET not set in environment."
fi

# 4. Check DB Password
if [ -z "$DB_PASSWORD" ]; then
    echo "⚠️ Warning: DB_PASSWORD not set. Generating a random one..."
    DB_PASSWORD=$(openssl rand -hex 12)
    echo "Generated DB_PASSWORD: $DB_PASSWORD (SAVE THIS!)"
fi

# 5. Check Container Image
if [ -z "$CONTAINER_IMAGE" ]; then
    echo "⚠️ Warning: CONTAINER_IMAGE not set."
    echo "Defaulting to a placeholder. You must build and push the portal image first!"
    CONTAINER_IMAGE="gcr.io/$PROJECT_ID/rongle-portal:latest"
fi

echo "🚀 Initializing Terraform (GCP)..."
cd terraform-gcp
terraform init

if [ "$COMMAND" == "plan" ]; then
    echo "📋 Planning deployment..."
    terraform plan -out=tfplan \
      -var="project_id=$PROJECT_ID" \
      -var="db_password=$DB_PASSWORD" \
      -var="jwt_secret=${JWT_SECRET:-changeme}" \
      -var="gemini_api_key=${GEMINI_API_KEY:-placeholder}" \
      -var="container_image=$CONTAINER_IMAGE"

elif [ "$COMMAND" == "apply" ]; then
    echo "🚀 Applying deployment..."
    terraform apply -auto-approve \
      -var="project_id=$PROJECT_ID" \
      -var="db_password=$DB_PASSWORD" \
      -var="jwt_secret=${JWT_SECRET:-changeme}" \
      -var="gemini_api_key=${GEMINI_API_KEY:-placeholder}" \
      -var="container_image=$CONTAINER_IMAGE"

elif [ "$COMMAND" == "destroy" ]; then
    echo "🧨 Destroying infrastructure..."
    terraform destroy -auto-approve \
      -var="project_id=$PROJECT_ID" \
      -var="db_password=$DB_PASSWORD" \
      -var="jwt_secret=${JWT_SECRET:-changeme}" \
      -var="gemini_api_key=${GEMINI_API_KEY:-placeholder}" \
      -var="container_image=$CONTAINER_IMAGE"
fi

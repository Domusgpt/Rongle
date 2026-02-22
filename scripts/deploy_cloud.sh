#!/bin/bash
# Helper script to deploy Rongle to AWS using Terraform
# Usage: ./scripts/deploy_cloud.sh [plan|apply|destroy]

set -e

COMMAND=${1:-plan}

# 1. Check Dependencies
if ! command -v terraform &> /dev/null; then
    echo "❌ Error: terraform is not installed."
    echo "Please install it: https://developer.hashicorp.com/terraform/install"
    exit 1
fi

# 2. Check Credentials
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "❌ Error: AWS credentials not set."
    echo "Please export AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY."
    exit 1
fi

# 3. Check App Secrets
if [ -z "$GEMINI_API_KEY" ] || [ -z "$JWT_SECRET" ]; then
    echo "⚠️ Warning: GEMINI_API_KEY or JWT_SECRET not set in environment."
    echo "You will be prompted to enter them, or the deployment might fail if using -var defaults."
fi

# 4. Check DB Password
if [ -z "$DB_PASSWORD" ]; then
    echo "⚠️ Warning: DB_PASSWORD not set. Generating a random one..."
    DB_PASSWORD=$(openssl rand -hex 12)
    echo "Generated DB_PASSWORD: $DB_PASSWORD (SAVE THIS!)"
fi

echo "🚀 Initializing Terraform..."
cd terraform
terraform init

if [ "$COMMAND" == "plan" ]; then
    echo "📋 Planning deployment..."
    terraform plan -out=tfplan \
      -var="db_password=$DB_PASSWORD" \
      -var="jwt_secret=${JWT_SECRET:-changeme}" \
      -var="gemini_api_key=${GEMINI_API_KEY:-placeholder}" \
      -var="ecr_repo_url=${ECR_REPO_URL:-placeholder}"

elif [ "$COMMAND" == "apply" ]; then
    echo "🚀 Applying deployment..."
    # Reuse plan if exists, else regenerate (simplified here to just apply vars)
    terraform apply -auto-approve \
      -var="db_password=$DB_PASSWORD" \
      -var="jwt_secret=${JWT_SECRET:-changeme}" \
      -var="gemini_api_key=${GEMINI_API_KEY:-placeholder}" \
      -var="ecr_repo_url=${ECR_REPO_URL:-placeholder}"

elif [ "$COMMAND" == "destroy" ]; then
    echo "🧨 Destroying infrastructure..."
    terraform destroy -auto-approve \
      -var="db_password=$DB_PASSWORD" \
      -var="jwt_secret=${JWT_SECRET:-changeme}" \
      -var="gemini_api_key=${GEMINI_API_KEY:-placeholder}" \
      -var="ecr_repo_url=${ECR_REPO_URL:-placeholder}"
fi

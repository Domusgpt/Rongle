# GCP Deployment (Cloud Run) ☁️

This directory contains the Infrastructure as Code (IaC) configuration to deploy the Rongle Portal to Google Cloud Platform using Serverless technologies.

## Architecture

*   **Cloud Run**: Serverless container hosting for the Portal API (scales to 0).
*   **Cloud SQL (Postgres)**: Managed database for user/session persistence.
*   **Memorystore (Redis)**: Managed Redis for rate limiting.
*   **VPC Connector**: Secure bridge between Serverless and Managed Data services.

## Usage

### Prerequisites
*   Terraform CLI installed (`>= 1.5.0`)
*   Google Cloud CLI (`gcloud`) installed and authenticated.

### Deploy Script

Use the helper script for a one-click deployment:

```bash
# Plan
./scripts/deploy_gcp.sh plan

# Apply
./scripts/deploy_gcp.sh apply
```

### Manual Deploy

1.  **Initialize**:
    ```bash
    cd terraform-gcp
    terraform init
    ```

2.  **Plan**:
    ```bash
    terraform plan -out=tfplan \
      -var="project_id=my-gcp-project" \
      -var="db_password=secure_pass" \
      -var="jwt_secret=secret_key" \
      -var="gemini_api_key=api_key" \
      -var="container_image=gcr.io/my-project/rongle-portal:latest"
    ```

3.  **Apply**:
    ```bash
    terraform apply tfplan
    ```

## Outputs

After deployment, Terraform will output:
*   `service_url`: The public HTTPS URL of the Portal.

---
[Back to Documentation Index](../docs/INDEX.md)

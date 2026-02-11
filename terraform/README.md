# Terraform Deployment ☁️

This directory contains the Infrastructure as Code (IaC) configuration to deploy the Rongle Portal to AWS.

## Architecture

*   **VPC**: Secure network with public/private subnets.
*   **ECS Fargate**: Container orchestration for the Portal API.
*   **RDS Postgres**: Managed database for user/session persistence.
*   **ElastiCache Redis**: Managed Redis for rate limiting and task queues.
*   **ALB**: Application Load Balancer for traffic distribution.

## Usage

### Prerequisites
*   Terraform CLI installed (`>= 1.5.0`)
*   AWS CLI configured (`aws configure`)

### Deploy

1.  **Initialize**:
    ```bash
    terraform init
    ```

2.  **Plan**:
    ```bash
    terraform plan -out=tfplan \
      -var="db_password=secure_pass" \
      -var="jwt_secret=secret_key" \
      -var="gemini_api_key=api_key" \
      -var="ecr_repo_url=123456789012.dkr.ecr.us-east-1.amazonaws.com/rongle-portal"
    ```

3.  **Apply**:
    ```bash
    terraform apply tfplan
    ```

## Outputs

After deployment, Terraform will output:
*   `alb_dns_name`: The public URL of the Portal.
*   `db_endpoint`: The database host.

---
[Back to Documentation Index](../docs/INDEX.md)

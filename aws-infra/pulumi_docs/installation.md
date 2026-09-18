# Infrastructure Setup (Pulumi + AWS)

This document explains how to deploy the Antenna infrastructure using Pulumi on AWS and how to complete required post-deployment steps (Django migrations) that Pulumi does not handle automatically.

---

## Prerequisites

- AWS account with sufficient permissions
- Python 3.10+
- AWS CLI
- Pulumi CLI
- Docker (local only, for image builds if enabled)

---

## 1. Install AWS CLI

### macOS
```bash
brew install awscli
```

### Windows (PowerShell)
```powershell
winget install Amazon.AWSCLI
```

---

## 2. Configure AWS CLI
```bash
aws configure
```

You will be prompted for:

- AWS Access Key ID
- AWS Secret Access Key
- Default region: `us-west-2`
- Default output format: `json`

---

## 3. Install Pulumi

### macOS
```bash
brew install pulumi
```

### Windows (PowerShell)
```powershell
winget install Pulumi.Pulumi
```

---

## 4. Pulumi Login

Pulumi requires an access token.

```bash
export PULUMI_ACCESS_TOKEN=<YOUR_PULUMI_TOKEN>   # macOS
setx PULUMI_ACCESS_TOKEN <YOUR_PULUMI_TOKEN>     # Windows

pulumi login
```

---

## 5. Initialize Pulumi Project
```bash
pulumi new aws-python --name aws_infra --stack dev --yes --force
```

This creates:
- Pulumi.yaml
- Pulumi.dev.yaml
- Python virtual environment (if needed)

---

## 6. Pulumi Configuration (REQUIRED) : RUN ONCE IN YOUR TERMINAL
```bash


# =========================================================
# AWS & Pulumi BASICS
# =========================================================

# AWS region where all infrastructure will be deployed
pulumi config set aws:region us-west-2


# =========================================================
# PROJECT / ENVIRONMENT METADATA
# =========================================================

# Project name
pulumi config set aws_infra:project antenna

# Deployment environment
pulumi config set aws_infra:environment prod

# AWS account ID where resources will be created
pulumi config set aws_infra:aws_account_id <ACCOUNT ID>


# =========================================================
# DJANGO APPLICATION SETTINGS
# =========================================================

# Django settings module to use in this environment
pulumi config set aws_infra:DJANGO_SETTINGS_MODULE "config.settings.production"

# Disable debug mode in production
pulumi config set aws_infra:DJANGO_DEBUG "False"

# Allowed hosts for Django (can be restricted later)
pulumi config set aws_infra:DJANGO_ALLOWED_HOSTS "*"

# Disable forced HTTPS redirect at Django level
# (TLS may be terminated elsewhere, e.g., ALB or CloudFront)
pulumi config set aws_infra:DJANGO_SECURE_SSL_REDIRECT "False"

# Admin URL for basic security hardening
pulumi config set aws_infra:DJANGO_ADMIN_URL <DJANGO ADMIN URL>


# =========================================================
# POSTGRES (RDS) DATABASE CONFIG
# =========================================================

# Database username
pulumi config set aws_infra:POSTGRES_USER "postgres"

# Database name
pulumi config set aws_infra:POSTGRES_DB "postgres"

# Database port (PostgreSQL default)
pulumi config set aws_infra:POSTGRES_PORT "5432"


# =========================================================
# REDIS (ELASTICACHE) CONFIG
# =========================================================

# Redis port (default)
pulumi config set aws_infra:REDIS_PORT "6379"


# =========================================================
# DJANGO STATIC FILES (S3 STORAGE)
# =========================================================

# S3 bucket used for Django static/media files
pulumi config set aws_infra:DJANGO_AWS_STORAGE_BUCKET_NAME "antenna-prod-assets-pulumi"

# AWS region where the S3 bucket lives
pulumi config set aws_infra:DJANGO_AWS_S3_REGION_NAME "us-west-2"


# =========================================================
# SERVICE ENDPOINTS & HEALTH CHECKS
# =========================================================

# Internal endpoint for the ML / processing service
pulumi config set aws_infra:DEFAULT_PROCESSING_SERVICE_ENDPOINT \
"http://ml-backend-example:2000"

# Health check path used by Elastic Beanstalk
pulumi config set aws_infra:EB_HEALTHCHECK "/health/"


# =========================================================
# DEPLOYMENT TOGGLES
# =========================================================

# Whether to deploy Elastic Beanstalk infrastructure
pulumi config set aws_infra:deployEb true

# Whether to build Docker images as part of Pulumi
pulumi config set aws_infra:buildImages true

# Whether to deploy the frontend
pulumi config set deployFrontend true


# =========================================================
# FRONTEND (UI) BUILD & DEPLOY CONFIG
# =========================================================

# Path to frontend source directory
pulumi config set aws_infra:ui_dir ../ui

# Path to built frontend assets
pulumi config set aws_infra:ui_dist_dir ../ui/build

# Build the frontend inside Pulumi execution
pulumi config set aws_infra:build_ui_in_pulumi true

# S3 bucket where the frontend will be deployed
pulumi config set aws_infra:ui_bucket_name antenna-prod-ui-pulumi


# =========================================================
# SECRETS (ENCRYPTED BY PULUMI)
# =========================================================

# Django secret key
pulumi config set --secret aws_infra:DJANGO_SECRET_KEY \
<DJANGO_SECRET_KEY>
# SendGrid API key for email delivery
pulumi config set --secret aws_infra:SENDGRID_API_KEY \
<SENDGRID_API_KEY>

# Sentry DSN for error tracking
pulumi config set --secret aws_infra:SENTRY_DSN \
<SENTRY_DSN>


# =========================================================
# AWS CREDENTIALS FOR DJANGO (S3 ACCESS)
# =========================================================

pulumi config set --secret DJANGO_AWS_ACCESS_KEY_ID \
<DJANGO_AWS_ACCESS_KEY_ID>

pulumi config set --secret DJANGO_AWS_SECRET_ACCESS_KEY \
<DJANGO_AWS_SECRET_ACCESS_KEY>


# =========================================================
# DATABASE CONNECTION (FULL URL)
# =========================================================

# Password
pulumi config set --secret POSTGRES_PASSWORD <POSTGRES_PASSWORD>

# Full database connection string used by Django
pulumi config set --secret aws_infra:DATABASE_URL \
<DATABASE_URL>

```


## 7. Deploy Infrastructure
```bash
pulumi up
```

This provisions:
- VPC networking
- RDS (Postgres)
- ElastiCache (Redis with TLS enabled)
- ECR repositories
- Elastic Beanstalk (ECS-based)
- Secrets Manager secrets
- Cloudfront

---

## 8. IMPORTANT: Django Migrations (REQUIRED)

Pulumi does not run Django migrations.

---

## 9. Access Elastic Beanstalk EC2 via SSM
```bash
aws ssm start-session --target <EC2_INSTANCE_ID> --region us-west-2
```

Find the instance ID in:
- AWS Console -> EC2 -> Instances (linked to the EB environment)

---

## 10. Run Django Migrations Inside the Container
```bash
DJANGO_CONTAINER=$(sudo docker ps --format '{{.Names}}' | grep -E 'django-' | head -n 1)
echo "Django container: $DJANGO_CONTAINER"

sudo docker exec -it "$DJANGO_CONTAINER" sh -lc 'python manage.py migrate --noinput'
```

---



## 11. Verify Application Health
```bash
sudo docker exec -it "$DJANGO_CONTAINER" sh -lc 'python - << "PY"
import urllib.request, socket
socket.setdefaulttimeout(10)

for path in ["/api/v2/events/", "/api/v2/storage/"]:
    url = "http://127.0.0.1:5000" + path
    print("\nGET", url)
    with urllib.request.urlopen(url) as r:
        print("status:", r.status)
        print("sample:", r.read(200))
PY'
```

Expected:
- HTTP 200
- JSON response

---

## Redis + TLS Notes

Redis runs with TLS enabled.

Injected URLs intentionally use:
```text
rediss://<host>:6379/0?ssl_cert_reqs=none
```

This is required for:
- Django cache
- Celery broker
---


### Access Flower (Celery Dashboard) via SSM Port Forwarding

Flower runs inside the Elastic Beanstalk ECS host and listens on port 5555.
Even if you open port 5555 on a security group, the Elastic Beanstalk environment DNS does not reliably expose arbitrary ports like :5555 (EB is primarily designed for web traffic via 80/443).

Because Flower is an admin dashboard, we intentionally do not expose it publicly. For security reasons, do not hardcode personal IP addresses in the repository.
Instead, whitelist your current public IP locally when deploying.
Instead, we use AWS SSM Port Forwarding to securely tunnel port 5555 from the EB EC2 instance to your laptop.

Why this approach

Secure by default: Flower is not public on the internet.

No IP allowlist headaches: your IP can change (Wi-Fi/VPN), but SSM still works.

Works even when EB DNS doesn’t serve :5555

Auditable: access is logged via AWS Systems Manager.

## Step 1: Find the EB EC2 Instance ID

If you know the EB environment name (for example antenna-django-eb-env-pulumi-v2), you can fetch the instance ID like this:
```bash

aws ec2 describe-instances \
  --region us-west-2 \
  --filters "Name=tag:elasticbeanstalk:environment-name,Values=antenna-django-eb-env-pulumi-v2" "Name=instance-state-name,Values=running" \
  --query "Reservations[].Instances[].InstanceId" \
  --output text

```

Copy the output instance ID, for example:

i-050060d3e7473792b

## Step 2: Start an SSM Port Forwarding Session (5555 -> localhost:5555)

Run this on your laptop:

```bash
aws ssm start-session \
  --region us-west-2 \
  --target i-050060d3e7473792b \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["5555"],"localPortNumber":["5555"]}'
```

Keep this terminal session running.

## Step 3: Open Flower in Your Browser

Once the port-forward session is active, open:

http://localhost:5555

You should see the Flower UI.

---

# Production Configuration Checklist

Before deploying to production, update the following settings:


## Elastic Beanstalk

- Change `EnvironmentType` from `SingleInstance` → `LoadBalanced`
- Disable `AssociatePublicIpAddress`
- Terminate TLS at ALB (not instance)
- Disable `force_destroy` on EB bundle bucket


## RDS (Postgres)

- Set `multi_az=True`
- Enable `deletion_protection=True`
- Set `skip_final_snapshot=False`
- Increase backup retention (≥14 days)



## Redis (ElastiCache)

- Enable `multi_az_enabled=True`
- Enable `automatic_failover_enabled=True`
- Enable snapshot retention



## ECR

- Set `force_delete=False`
- Enable `scan_on_push=True`
- Set `image_tag_mutability="IMMUTABLE"`



## S3 (Assets Bucket)

- Set `force_destroy=False`


## CloudFront

- Use ACM certificate (custom domain)
- Enable logging
- Attach AWS WAF
- Use HTTPS to backend origin


## Observability

- Add CloudWatch alarms (CPU, memory, DB storage, 5xx)
- Enable access logs (CloudFront + S3)

---

## References

- Pulumi Docs: https://www.pulumi.com/docs/
- AWS Systems Manager: https://docs.aws.amazon.com/systems-manager/
- Elastic Beanstalk: https://docs.aws.amazon.com/elasticbeanstalk/





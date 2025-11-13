# Antenna Backend – Deployment & Infrastructure Guide

This document provides a full, end-to-end explanation of how the Antenna backend is deployed to AWS using Elastic Beanstalk (EB), Docker, RDS (Postgres), and ElastiCache (Redis). It is intended for future maintainers, reviewers, and collaborators who need to understand, update, or reproduce the deployed environment.

---

## 1. Overview

The Antenna backend is a Django application deployed using:

- AWS Elastic Beanstalk (ECS on Amazon Linux 2, Multi-container Docker)
- AWS Elastic Container Registry (ECR) for Docker images
- AWS RDS Postgres for database storage
- AWS ElastiCache Redis for Celery broker and backend
- Dockerized services (Django app, Celery worker, Celery beat, Flower, AWS CLI helper)
- S3 as the storage backend for static and media files

---

## 2. Repository Structure (Relevant to Deployment)

/.ebextensions/00_setup.config # EB environment variables and settings
/.ebignore # Excludes dev files from deployment bundle
/Dockerrun.aws.json # Multi-container EB deployment configuration
/.envs/.production/.django # Django environment variables (local only)
/.envs/.production/.postgres # Postgres variables (local only)


---

## 3. Deployment Architecture

### Elastic Beanstalk

- Platform: ECS running on Amazon Linux 2 (Multi-container Docker)
- Deployment artifacts:
  - Dockerrun.aws.json (version 2)
  - .ebextensions/00_setup.config
- Instance type: t3.large or t3.medium
- Environment type: Single instance
- Security groups:
  - EB-created SG (for EC2 instance)
  - App Runner egress SG (for outbound VPC access)

### Docker Containers

EB ECS runs the following containers:

1. django  
   Serves the web application on port 5000 → mapped to host port 80.
2. celeryworker  
   Executes asynchronous Celery tasks.
3. celerybeat  
   Runs scheduled Celery tasks.
4. flower  
   Celery monitoring UI on port 5555.
5. awscli  
   Nonessential helper container for debugging within the EB network.

All containers reference the same image:

677276102449.dkr.ecr.us-west-2.amazonaws.com/antenna-backend:<tag>



---

## 4. Environment Variables

Environment configuration is injected via:

- Elastic Beanstalk console → Configuration → Environment Properties  
- .ebextensions/00_setup.config (non-secret defaults only)  
- Local .envs/.production/ files (not committed)

### Django

- DJANGO_SETTINGS_MODULE
- DJANGO_SECRET_KEY
- DJANGO_ALLOWED_HOSTS
- DJANGO_SECURE_SSL_REDIRECT
- DJANGO_ADMIN_URL

### AWS/S3

- DJANGO_AWS_ACCESS_KEY_ID
- DJANGO_AWS_SECRET_ACCESS_KEY
- DJANGO_AWS_STORAGE_BUCKET_NAME
- DJANGO_AWS_S3_REGION_NAME

### Database

- POSTGRES_DB
- POSTGRES_USER
- POSTGRES_PASSWORD
- POSTGRES_HOST
- POSTGRES_PORT
- DATABASE_URL

### Redis/Celery

- REDIS_URL
- CELERY_BROKER_URL

Important note about Redis:

rediss://<primary-endpoint>:6379/0?ssl_cert_reqs=none


Required because ElastiCache uses in-transit encryption.

### Other integrations

- SENDGRID_API_KEY
- SENTRY_DSN
- EB_HEALTHCHECK=1 (to bypass SSL redirect for internal EB health checks)

---

## 5. AWS Infrastructure Components

### RDS (Postgres)

- Engine: PostgreSQL 16
- Instance type: db.t3.micro
- Connected through private subnet
- Security group:
  - Allows inbound on port 5432 only from EB’s security group

### ElastiCache (Redis)

- Engine: Redis 7.1
- Encryption in transit: Enabled
- Multi-AZ: Disabled
- Security group:
  - Allows inbound on port 6379 from EB’s security group
- Requires:
  - rediss:// scheme
  - ssl_cert_reqs=none

### Elastic Beanstalk EC2 Instance

- Instance profile: aws-elasticbeanstalk-ec2-role
- Service role: aws-elasticbeanstalk-service-role
- Permissions:
  - ECR pull access
  - CloudWatch logs/metrics
  - S3 access for EB logs and deployment bundles

### Networking

- VPC: vpc-065bb4037d3347f3f
- Subnets: 3 private + 1 public
- Redis and Postgres run in private subnets
- EB instance assigned a public IP

---

## 6. Multi-Container Configuration (Dockerrun.aws.json)

Elastic Beanstalk uses Dockerrun.aws.json to orchestrate Docker containers


Key details:

- Django container exposes port 5000 → host port 80.
- Flower exposes port 5555.
- All containers include "USE_DOCKER": "yes".
- Shared ECR image ensures consistent app code across all containers.

---

## 7. .ebextensions Configuration

`00_setup.config` ensures EB:

- Loads environment variables
- Sets health check path to `/api/v2/`
- Disables SSL redirect for health checks when EB_HEALTHCHECK=1
- Runs migrations via Docker:


docker exec $(docker ps -q -f name=django) python manage.py migrate --noinput


---

## 8. Deployment Workflow

### Step 1 — Build and push image to ECR



docker build -t antenna-backend .
docker tag antenna-backend:latest <ECR_URI>:v10
docker push <ECR_URI>:v10


### Step 2 — Update Dockerrun.aws.json

Update the tag:


"image": "<ECR_URI>:v10"

### Step 3 — Create the EB bundle

Zip only the required files:


zip -r deploy.zip Dockerrun.aws.json .ebextensions .ebignore

### Step 4 — Deploy to Elastic Beanstalk

- Open EB Console → Environment → Upload and Deploy  
- Upload deploy.zip  
- Wait for ECS tasks to start

### Step 5 — Validate

- /api/v2/ returns 200
- Django container stays healthy
- Celery worker logs show successful connection to Redis
- Celery beat schedules run without connection errors
- Flower UI loads on port 5555 (if SG rules allow)

---

## 9. Common Issues and Requirements

### Redis SSL issues

ElastiCache requires explicit SSL configuration. Without it, Celery fails with:

ssl.SSLCertVerificationError


Solution:
ssl_cert_reqs=none

### Health check redirect loops

EB health checks do not support HTTPS.

Solution:
EB_HEALTHCHECK=1
SECURE_SSL_REDIRECT=False for health checks


### Migrations failing on new deploy

EB occasionally triggers migrations too early. The `.ebextensions` migrations command is configured to ignore failures:

|| true

yaml
Copy code

---

## 10. Security and Secret Management

- Secrets are stored only in the EB console under Environment Properties
- Secrets are not committed to GitHub
- `.ebextensions` contains only non-sensitive or placeholder values
- `.envs/.production` files are for local development only

---

## 11. Future Improvements

- Move secrets to AWS Secrets Manager
- Enable ElastiCache Multi-AZ for production-grade reliability
- Add a CI/CD pipeline (GitHub Actions → ECR → EB)
- Switch to ECS Fargate for a container-only deployment

---

## 12. Maintainer Notes

To update the deployment:

1. Build a new ECR image  
2. Update the tag inside Dockerrun.aws.json  
3. Zip the deployment bundle  
4. Deploy through the EB console or EB CLI  

To debug containers:

eb ssh
docker ps
docker logs <container_id>

yaml
Copy code

---

End of documentation.





# Antenna Backend - Deployment & Infrastructure Guide

This document describes the AWS infrastructure and deployment pipeline for the Antenna backend.  
The system runs on AWS Elastic Beanstalk (ECS-based multicontainer) using Docker, Celery, ElastiCache Redis (TLS), RDS PostgreSQL, S3, ECR, and Sentry.  
It is intended for maintainers and contributors who need to understand, update, or reproduce the deployed environment.

---

## 1. Overview

The Antenna backend is a Django application deployed using:

- **Elastic Beanstalk (ECS-based multicontainer)** running Docker
- **ECR** for storing container images
- **RDS PostgreSQL** as the application database
- **ElastiCache Redis (TLS)** for Celery broker + Django cache
- **Dockerized services** (Django, Celery Worker, Celery Beat, Flower, AWS CLI helper)
- **S3** as static storage backend
- **IAM** roles for instance profiles and service roles
- **CloudWatch** for logs, health monitoring, ECS task metrics
- **Default VPC** with public and private subnets

---

## 2. Repository Structure (Deployment-Relevant)

- /.ebextensions/00_setup.config     # EB environment variables and settings
- /.ebignore                         # Exclusion list for EB deployment bundle
- /Dockerrun.aws.json                # Multi-container EB deployment config

---

## 3. Deployment Architecture

### 3.1. Elastic Beanstalk (EB)

- Platform: ECS on Amazon Linux 2 (Multicontainer Docker)
- Deployment bundle includes:
  - `Dockerrun.aws.json` (v2)
  - `.ebextensions/00_setup.config`
- Instance type: `t3.large`
- Environment type: **single instance** (no load balancing)
- Security groups:
  - EB-created instance security group
  - An outbound egress security group (named App Runner but used by EB)

---

### 3.2. Docker Containers

EB ECS runs the following containers:

1. **django** — web application (the container listens on port 5000, which is exposed as port 80 on the Elastic Beanstalk host)
2. **celeryworker** — asynchronous task worker
3. **celerybeat** — scheduled task runner
4. **flower** — Celery monitoring UI (port 5555)
5. **awscli** — lightweight helper container for internal AWS commands

---

### 3.3. ECR Repositories Used

All application containers pull from:

- **antenna-backend**  
  `<ECR_URI>/antenna-backend`

The AWS CLI helper container pulls from:

- **antenna-awscli**  
  `<ECR_URI>/antenna-awscli`

Both repositories are **mutable** and **AES-256 encrypted**.

---

## 4. Environment Variables

In this setup, **all required environment variables—including secrets—are defined inside**  
`.ebextensions/00_setup.config`.

Elastic Beanstalk automatically reads the values from this file and writes them into its  
**Environment Properties** at deployment time.  
This ensures a fully automated bootstrap with no manual EB console entry.

The deployment uses the following environment variables across these categories:

### Django
- `DJANGO_SETTINGS_MODULE`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_SECURE_SSL_REDIRECT`
- `DJANGO_ADMIN_URL`
- `DJANGO_DEBUG`
- `EB_HEALTHCHECK`

### AWS / S3
- `DJANGO_AWS_ACCESS_KEY_ID`
- `DJANGO_AWS_SECRET_ACCESS_KEY`
- `DJANGO_AWS_STORAGE_BUCKET_NAME`
- `DJANGO_AWS_S3_REGION_NAME`

### Database (RDS)
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `DATABASE_URL`

### Redis / Celery
- `REDIS_URL`
- `CELERY_BROKER_URL`

### Third-Party Integrations
- `SENDGRID_API_KEY`
- `SENTRY_DSN`

---

## 5. AWS Infrastructure Components

### 5.1. RDS (PostgreSQL)

- **Engine:** PostgreSQL  
- **Instance class:** `db.t4g.small`
- **Availability Zone:** Single-AZ

- **Networking:**
  - Runs inside the **default VPC**
  - RDS subnet group uses **public subnets**
  - Instance is configured as **publicly accessible** (need to make it private)

- **Endpoint:** *(redacted for security)*

- **Security group:**
  - Inbound port **5432** allowed from the EB instance SG
  - Outbound allowed to `0.0.0.0/0`

---

### 5.2. ElastiCache (Redis)

- **Engine:** Redis 7.1
- **Node type:** `cache.t4g.micro`
- **Cluster mode:** Disabled (single node)
- **Multi-AZ:** Disabled
- **Auto-failover:** Disabled

- **Security:**
  - Encryption in transit: **Enabled**
  - Encryption at rest: **Enabled**
  - Redis URL requires:
    - `rediss://` (TLS)
    - `ssl_cert_reqs=none` for Celery/Django clients
  - Inbound port **6379** allowed only from the EB instance SG

- **Networking:**
  - Deployed into private subnets (via its subnet group)
  - Runs within the same VPC as EB and RDS

---

### 5.3. Elastic Beanstalk EC2 Instance & IAM Roles

- **Instance type:** `t3.large`
- **Instance profile:** `aws-elasticbeanstalk-ec2-role`
- **Service role:** `aws-elasticbeanstalk-service-role`
- **Public IP:** Assigned
- **Security groups:**
  - EB default instance SG
  - Outbound-only egress SG

### 5.4. IAM Roles and Policies

**1. EC2 Instance Profile – `aws-elasticbeanstalk-ec2-role`**  
Attached AWS-managed policies (default from EB):
- `AWSElasticBeanstalkWebTier`
- `AWSElasticBeanstalkWorkerTier`
- `AmazonEC2ContainerRegistryReadOnly` (ECR pull)
- `CloudWatchAgentServerPolicy` (log streaming)
- S3 read/write access granted through `AWSElasticBeanstalkWebTier`  
  (used for EB deployment bundles, log archives, temp artifacts)

This role is used **by the EC2 instance itself**.  
It allows the instance to:
- Pull container images from ECR  
- Upload logs to CloudWatch  
- Read/write to the EB S3 bucket  
- Communicate with ECS agent inside the EB environment  

---

**2. Service Role – `aws-elasticbeanstalk-service-role`**  
Attached AWS-managed policies (default from EB):
- `AWSElasticBeanstalkEnhancedHealth`  
- `AWSElasticBeanstalkService`  

This role is used **by the Elastic Beanstalk service**, not the EC2 instance.  
It allows EB to:
- Manage environment health monitoring  
- Launch/update/terminate EC2 instances  
- Interact with Auto Scaling  
- Register container tasks and update ECS configuration  

---

### Notes on Security / Least Privilege

The current roles use **Elastic Beanstalk’s default managed policies**, which are intentionally broad to ensure environments deploy successfully.

For a production-grade hardened setup, these should eventually be adjusted toward **least privilege**, including:

- Restricting S3 access to only specific buckets  
- Restricting ECR access to only required repositories  
- Minimizing CloudWatch permissions  
- Adding explicit denies on unneeded services  

This is recommended once the deployment architecture has stabilized so it would be a part of future scope.



---

### 5.5. Networking (EB Environment)

- **VPC:** default VPC
- **Subnets:**
  - EB instance runs in a **public subnet**
  - RDS + Redis run in **private subnets** (via their subnet groups)
- **Public access:**
  - EB EC2 instance receives a public IP
  - No load balancer (single-instance environment)
- **Connectivity:**
  - EB instance can reach RDS & Redis via SG rules
  - Internet connectivity available through AWS default routing

---

## 6. .ebextensions Configuration

`00_setup.config` handles:

- Loading environment variables into EB
- Setting health check path: `/api/v2/`
- Disabling SSL redirects during health checks (`EB_HEALTHCHECK=1`)
- Running Django migrations via Docker:
docker exec $(docker ps -q -f name=django) python manage.py migrate --noinput


---

## 7. Deployment Workflow

### Step 1 — Build and push image to ECR

docker build -t antenna-backend .
docker tag antenna-backend:latest <ECR_URI>:v10
docker push <ECR_URI>:v10

### Step 2 — Update Dockerrun.aws.json

Update the tag:

"image": "<ECR_URI>:v10"

### Step 3 — Create EB bundle

zip -r deploy.zip Dockerrun.aws.json .ebextensions .ebignore


### Step 4 — Deploy to Elastic Beanstalk

- EB Console → Environment → Upload & Deploy  
- Upload `deploy.zip`  
- Wait for ECS tasks to start

### Step 5 — Validate Deployment

- `/api/v2/` returns `200`
- Django container remains healthy
- Celery worker connects to Redis successfully
- Celery Beat schedules run successfully
- Flower UI loads on port 5555 (if security groups permit)

---

## 8. Common Issues & Fixes

### Redis SSL Errors

ElastiCache requires TLS. Missing SSL args causes:

ssl.SSLCertVerificationError

**Fix:**  
Use `rediss://` and `ssl_cert_reqs=none`.

### Health Check Redirect Loops

EB health checks cannot handle HTTPS.

**Fix:**  
Set `EB_HEALTHCHECK=1` and temporarily disable SSL redirect for health checks.

### Early Migrations Failure

EB sometimes runs migrations before services are ready.

**Fix:**  
`.ebextensions` migration command is set to ignore failures and retry.

---

## 9. Future Improvements

To harden the deployment and move toward a production-grade architecture, the following enhancements are recommended:

- **Move secrets to AWS Secrets Manager**  
  Centralize all sensitive variables (DB password, Redis URL, Django secret key, Sentry key, SendGrid, etc.) and replace `.ebextensions` injection with runtime retrieval.

- **Enable ElastiCache Multi-AZ + Auto-Failover**  
  Improves high availability for Celery and Django caching; eliminates single-node Redis failure risks.

- **Restrict RDS and Redis to private-only access**  
  Disable public accessibility on RDS and ensure Redis remains reachable only via EB’s security group.

- **IAM hardening and least-privilege review**  
  Replace broad EB-managed policies with reduced IAM policies scoped only to required S3, ECR, CloudWatch, and ECS resources.

- **Add CI/CD pipeline (GitHub Actions -> ECR -> EB)**  
  Automate build, tag, push of images and deployments to Elastic Beanstalk for consistent, reproducible releases.

- **Add staging environment**  
  Separate EB environment (staging) for testing migrations, image builds, and infrastructure changes before production.

- **Migrate to load-balanced EB environment (optional)**  
  Enables rolling deployments, zero-downtime updates, and better scalability.

- **Enable RDS Multi-AZ + automated backups**  
  Ensures database failover and improves disaster recovery readiness.

- **Add health checks for Celery worker & beat**  
  Custom EB or CloudWatch alarms to alert on worker failures, broker connectivity issues, or long task queues.


---

_End of documentation._

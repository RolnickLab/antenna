import pulumi

# ---------------------------------------------------------
# Optional deploy flags
# ---------------------------------------------------------
config = pulumi.Config()
DEPLOY_EB = config.get_bool("deployEb") or False
BUILD_IMAGES = config.get_bool("buildImages") or False
DEPLOY_FRONTEND = config.get_bool("deployFrontend") or False


# =========================================================
#  CREATE BASE INFRA
# (networking, storage, IAM, ECR, Redis, RDS)
# =========================================================

# --- Networking ---
from networking.vpc import default_vpc
from networking import subnets
from networking import routes
from networking.security_group import *

# --- Storage (S3 + policies) ---
from storage import *

# --- IAM Roles ---
import iam_roles

# --- ECR repos (needed by images build + EB dockerrun) ---
import ecr

# --- Redis + RDS ---
import redis
import rds


# =========================================================
# 1) BUILD DOCKER IMAGES (ONLY IF REQUESTED)
# =========================================================
if BUILD_IMAGES:
    import images


# =========================================================
# 2) DEPLOY EB (ONLY IF REQUESTED)
# =========================================================
if DEPLOY_EB:
    # EB requires Dockerrun/zip generation code,
    # so always import images when deploying EB
    if not BUILD_IMAGES:
        import images

    # Secrets Manager:
    # - creates manual secrets (django key, sendgrid, sentry)
    # - exports AWS-generated RDS master secret arn
    # - constructs EB_ENV map
    import secrets_manager

    # Elastic Beanstalk environment
    import eb

    # =========================================================
    # 3) DEPLOY FRONTEND (ONLY IF REQUESTED)
    # IMPORTANT: must come AFTER EB import, because cloudfront.py
    # imports env_pulumi from eb.py for backend origin.
    # =========================================================
    if DEPLOY_FRONTEND:
        import cloudfront

else:
    # If EB is not deployed in this run, we cannot deploy frontend proxying to EB
    # because cloudfront.py expects env_pulumi from eb.py.
    if DEPLOY_FRONTEND:
        raise Exception("deployFrontend=true requires deployEb=true in the same run (CloudFront backend origin uses EB env URL).")

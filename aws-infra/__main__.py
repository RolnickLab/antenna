"""
Pulumi stack entrypoint.

Conditionally deploys infrastructure components
(RDS, Redis, images, EB, CloudFront) based on config flags.
"""



import pulumi

config = pulumi.Config()
DEPLOY_EB = config.get_bool("deployEb") or False
BUILD_IMAGES = config.get_bool("buildImages") or False
DEPLOY_FRONTEND = config.get_bool("deployFrontend") or False

from networking.antennav2_vpc import default_vpc
from networking import antennav2_subnets
from networking import antennav2_routes
from networking.antennav2_security_group import *

from storage import *

import antennav2_iam_roles

import antennav2_ecr

import antennav2_redis
import antennav2_rds

if BUILD_IMAGES:
    import antennav2_images

if DEPLOY_EB:

    if not BUILD_IMAGES:
        import antennav2_images

    import antennav2_secrets_manager

    import antennav2_eb

    if DEPLOY_FRONTEND:
        import antennav2_cloudfront

else:

    if DEPLOY_FRONTEND:
        raise Exception("deployFrontend=true requires deployEb=true in the same run (CloudFront backend origin uses EB env URL).")

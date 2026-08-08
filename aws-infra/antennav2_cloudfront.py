
"""
Deploys the UI to S3 + CloudFront.

Builds and uploads static assets, configures CloudFront
with the EB backend as an API origin, and triggers invalidation.
"""


import os
import mimetypes
import subprocess
import hashlib
import atexit
import time

import pulumi
import pulumi_aws as aws
from urllib.parse import urlparse


# NOTE:
# We want the backend origin to be the EB environment URL.
# This requires EB to be deployed in the same update *before* importing this file.
from antennav2_eb import env_pulumi


# =========================================================
# CONFIG
# =========================================================

config = pulumi.Config()
project_config = pulumi.Config(pulumi.get_project())

# S3 bucket where the compiled UI will live
ui_bucket_name = (
    config.get("ui_bucket_name")
    or project_config.get("ui_bucket_name")
    or config.require("ui_bucket_name")
)  # e.g. antenna-prod-ui-pulumi

# ---------------------------------------------------------
# UI build paths
# ---------------------------------------------------------
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

ui_dir = (
    config.get("ui_dir")
    or project_config.get("ui_dir")
    or os.path.join(repo_root, "ui")
)


ui_dist_dir = (
    config.get("ui_dist_dir")
    or project_config.get("ui_dist_dir")
    or os.path.join(ui_dir, "build")
)

# If True, Pulumi will run:
#   cd ui
#   nvm use
#   yarn install
#   yarn build
build_ui_in_pulumi = (
    config.get_bool("build_ui_in_pulumi")
    or project_config.get_bool("build_ui_in_pulumi")
    or False
)


# =========================================================
# HELPERS
# =========================================================

def normalize_origin_domain(d: str) -> str:
    parsed = urlparse(d)
    return parsed.netloc or parsed.path


def guess_content_type(path: str) -> str:
    ctype, _ = mimetypes.guess_type(path)
    return ctype or "application/octet-stream"


def cache_control_for_key(key: str) -> str:
    # Vite SPA: index.html should not be aggressively cached
    if key == "index.html":
        return "no-cache"
    # Fingerprinted assets can be cached forever
    if key.startswith("assets/"):
        return "public, max-age=31536000, immutable"
    return "public, max-age=3600"


def run_ui_build_if_enabled() -> None:
    """
    Incorporates:
      cd ui
      nvm use
      yarn install
      yarn build

    Guardrails:
    - Only run during an actual update (not preview)
    - Use bash -lc so nvm works (nvm is a shell function)
    """
    if not build_ui_in_pulumi:
        pulumi.log.info("UI build disabled (build_ui_in_pulumi=false).")
        return

    if pulumi.runtime.is_dry_run():
        pulumi.log.info("Preview detected: skipping UI build (build_ui_in_pulumi=true).")
        return

    if not os.path.isdir(ui_dir):
        raise Exception(f"UI directory not found: {ui_dir}")

    cmd = f"""
set -euo pipefail
cd "{ui_dir}"

# Make nvm available in non-interactive shells.
# We avoid relying on ~/.bash_profile because it may not be sourced cleanly
# (and Pulumi runs this in a subprocess).
export NVM_DIR="${{NVM_DIR:-$HOME/.nvm}}"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  . "$NVM_DIR/nvm.sh"
else
  echo "nvm.sh not found at $NVM_DIR/nvm.sh"
  exit 1
fi

# Use .nvmrc if present, otherwise fall back to default nvm alias
if [ -f ".nvmrc" ]; then
  nvm use
else
  nvm use default || nvm use
fi

yarn install
yarn build
"""

    pulumi.log.info("Building UI inside Pulumi: cd ui && nvm use && yarn install && yarn build")
    subprocess.run(["/bin/bash", "-lc", cmd], check=True)


# =========================================================
# 6.1 BUILD UI
# =========================================================
run_ui_build_if_enabled()


# =========================================================
# 6.2 S3 BUCKET (CREATE A NEW ONE)
# =========================================================
ui_bucket = aws.s3.Bucket(
    "antenna-ui-bucket",
    bucket=ui_bucket_name,
)

# Object ownership controls (recommended with OAC)
ui_ownership = aws.s3.BucketOwnershipControls(
    "antenna-ui-bucket-ownership",
    bucket=ui_bucket.id,
    rule=aws.s3.BucketOwnershipControlsRuleArgs(
        object_ownership="BucketOwnerPreferred"
    ),
)

# Block public access ON (CloudFront OAC will read privately)
ui_public_access_block = aws.s3.BucketPublicAccessBlock(
    "antenna-ui-bucket-public-access",
    bucket=ui_bucket.id,
    block_public_acls=True,
    ignore_public_acls=True,
    block_public_policy=True,
    restrict_public_buckets=True,
)

# Default encryption ON
ui_encryption = aws.s3.BucketServerSideEncryptionConfiguration(
    "antenna-ui-bucket-encryption",
    bucket=ui_bucket.id,
    rules=[
        aws.s3.BucketServerSideEncryptionConfigurationRuleArgs(
            apply_server_side_encryption_by_default=
                aws.s3.BucketServerSideEncryptionConfigurationRuleApplyServerSideEncryptionByDefaultArgs(
                    sse_algorithm="AES256"
                ),
            bucket_key_enabled=True,
        )
    ],
)


# =========================================================
# 6.3 CLOUDFRONT (S3 + EB ORIGIN, /api/* PROXY)
# =========================================================

# ---------------------------------------------------------
# Managed CloudFront policies
# ---------------------------------------------------------
caching_optimized = aws.cloudfront.get_cache_policy_output(name="Managed-CachingOptimized")
caching_disabled = aws.cloudfront.get_cache_policy_output(name="Managed-CachingDisabled")
all_viewer = aws.cloudfront.get_origin_request_policy_output(name="Managed-AllViewer")

# OAC (private S3 origin access)
oac = aws.cloudfront.OriginAccessControl(
    "antenna-ui-oac",
    description="OAC for Antenna UI S3 origin",
    origin_access_control_origin_type="s3",
    signing_behavior="always",
    signing_protocol="sigv4",
)

# Backend origin domain = EB endpoint (no scheme)
backend_origin_domain = env_pulumi.cname.apply(normalize_origin_domain)

# CloudFront distribution
cf_distribution = aws.cloudfront.Distribution(
    "antenna-ui-prod",
    enabled=True,
    comment="CloudFront distribution for Antenna UI (S3) + EB API proxy (/api/v2/*)",
    default_root_object="index.html",

    origins=[
        # UI origin (S3)
        aws.cloudfront.DistributionOriginArgs(
            origin_id="antenna-ui-origin",
            domain_name=ui_bucket.bucket_regional_domain_name,
            origin_access_control_id=oac.id,
            s3_origin_config=aws.cloudfront.DistributionOriginS3OriginConfigArgs(
                origin_access_identity=""
            ),
        ),
        # Backend origin (Elastic Beanstalk)
        aws.cloudfront.DistributionOriginArgs(
            origin_id="antenna-backend-origin",
            domain_name=backend_origin_domain,
            custom_origin_config=aws.cloudfront.DistributionOriginCustomOriginConfigArgs(
                http_port=80,
                https_port=443,
                # CloudFront can connect to the backend over HTTP (80) or HTTPS (443).
                # EB currently serves traffic over HTTP, so CloudFront uses port 80 for origin requests.
                origin_protocol_policy="http-only",
                origin_ssl_protocols=["TLSv1.2"],
                origin_read_timeout=60,
                origin_keepalive_timeout=60,
            ),
        ),
    ],

    # Default: UI from S3 (caching optimized)
    default_cache_behavior=aws.cloudfront.DistributionDefaultCacheBehaviorArgs(
        target_origin_id="antenna-ui-origin",
        viewer_protocol_policy="redirect-to-https",
        allowed_methods=["GET", "HEAD", "OPTIONS"],
        cached_methods=["GET", "HEAD"],
        compress=True,
        cache_policy_id=caching_optimized.id,  # Managed-CachingOptimized
    ),

    # /api/v2/* -> EB (caching disabled)
    ordered_cache_behaviors=[
        aws.cloudfront.DistributionOrderedCacheBehaviorArgs(
            path_pattern="/api/v2/*",
            target_origin_id="antenna-backend-origin",
            viewer_protocol_policy="redirect-to-https",
            allowed_methods=["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
            cached_methods=["GET", "HEAD"],
            compress=True,
            cache_policy_id=caching_disabled.id,         # Managed-CachingDisabled
            origin_request_policy_id=all_viewer.id,      # Managed-AllViewer
        ),

        aws.cloudfront.DistributionOrderedCacheBehaviorArgs(
            path_pattern="/api/*",
            target_origin_id="antenna-backend-origin",
            viewer_protocol_policy="redirect-to-https",
            allowed_methods=["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
            cached_methods=["GET", "HEAD"],
            compress=True,
            cache_policy_id=caching_disabled.id,         # Managed-CachingDisabled
            origin_request_policy_id=all_viewer.id,      # Managed-AllViewer
        ),
    ],

    # SPA fallback to index.html
    custom_error_responses=[
        aws.cloudfront.DistributionCustomErrorResponseArgs(
            error_code=403, response_code=200, response_page_path="/index.html"
        ),
        aws.cloudfront.DistributionCustomErrorResponseArgs(
            error_code=404, response_code=200, response_page_path="/index.html"
        ),
    ],

    price_class="PriceClass_All",
    restrictions=aws.cloudfront.DistributionRestrictionsArgs(
        geo_restriction=aws.cloudfront.DistributionRestrictionsGeoRestrictionArgs(
            restriction_type="none"
        )
    ),
    viewer_certificate=aws.cloudfront.DistributionViewerCertificateArgs(
        cloudfront_default_certificate=True
    ),
    tags={"Environment": "production"},
)

# Bucket policy: allow ONLY this distribution to read (OAC)
caller = aws.get_caller_identity_output()

ui_bucket_policy = aws.s3.BucketPolicy(
    "antenna-ui-bucket-policy",
    bucket=ui_bucket.id,
    policy=pulumi.Output.all(ui_bucket.bucket, caller.account_id, cf_distribution.id).apply(
        lambda args: f"""
{{
  "Version": "2012-10-17",
  "Statement": [
    {{
      "Sid": "AllowCloudFrontReadOnlyViaOAC",
      "Effect": "Allow",
      "Principal": {{ "Service": "cloudfront.amazonaws.com" }},
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::{args[0]}/*",
      "Condition": {{
        "StringEquals": {{
          "AWS:SourceArn": "arn:aws:cloudfront::{args[1]}:distribution/{args[2]}"
        }}
      }}
    }}
  ]
}}
""".strip()
    ),
    opts=pulumi.ResourceOptions(depends_on=[ui_public_access_block, ui_ownership]),
)


# =========================================================
# 6.2 UPLOAD dist/ CONTENTS TO S3
# =========================================================
uploaded_objects = []

if os.path.isdir(ui_dist_dir):
    for root, _, files in os.walk(ui_dist_dir):
        for filename in files:
            full_path = os.path.join(root, filename)
            rel_key = os.path.relpath(full_path, ui_dist_dir).replace(os.sep, "/")

            # Keep Pulumi resource names short + stable
            key_hash = hashlib.md5(rel_key.encode("utf-8")).hexdigest()[:12]
            res_name = f"ui-obj-{key_hash}"

            obj = aws.s3.BucketObject(
                res_name,
                bucket=ui_bucket.id,
                key=rel_key,
                source=pulumi.FileAsset(full_path),
                content_type=guess_content_type(full_path),
                cache_control=cache_control_for_key(rel_key),
                opts=pulumi.ResourceOptions(depends_on=[ui_bucket_policy]),
            )
            uploaded_objects.append(obj)
else:
    pulumi.log.warn(
        f"UI build output not found: {ui_dist_dir}. "
        "If you disabled build_ui_in_pulumi, run the UI build locally first."
    )


# =========================================================
# 6.4 INVALIDATE CLOUDFRONT AFTER DEPLOY
# =========================================================
# Pulumi AWS classic does NOT expose an Invalidation resource.
# Pulumi's recommended workaround is to run a post-deploy task using runtime logic + SDK.
def register_invalidation(distribution_id: str) -> None:
    if pulumi.runtime.is_dry_run():
        pulumi.log.info("Preview detected: skipping CloudFront invalidation.")
        return

    def _do_invalidate() -> None:
        import boto3  # keep import here so previews don’t require boto3

        pulumi.log.info(f"Creating CloudFront invalidation for distribution {distribution_id} (paths: /*)")
        client = boto3.client("cloudfront")
        result = client.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                "CallerReference": f"pulumi-{time.time()}",
                "Paths": {
                    "Quantity": 1,
                    "Items": ["/*"],
                },
            },
        )
        status = result["Invalidation"]["Status"]
        inval_id = result["Invalidation"]["Id"]
        pulumi.log.info(f"CloudFront invalidation created: {inval_id} (status: {status})")

    # run once the program is about to exit (after resources have been applied)
    atexit.register(_do_invalidate)


# Trigger invalidation after any update where this program runs
cf_distribution.id.apply(lambda d: register_invalidation(d))


# =========================================================
# 6.5 OUTPUTS
# =========================================================
pulumi.export("cloudfront_domain", cf_distribution.domain_name)
pulumi.export("ui_bucket_name", ui_bucket.bucket)
pulumi.export("backend_origin_domain", backend_origin_domain)
pulumi.export("ui_dist_dir", ui_dist_dir)
pulumi.export("build_ui_in_pulumi", build_ui_in_pulumi)

pulumi.export("debug_eb_endpoint_url", env_pulumi.endpoint_url)
pulumi.export("debug_eb_cname", env_pulumi.cname)

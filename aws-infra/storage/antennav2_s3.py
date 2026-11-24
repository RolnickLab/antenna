"""
Creates the S3 assets bucket for static files.

Configures ownership controls, public access settings,
and default encryption. Exports bucket name and ARN.
"""



import pulumi
import pulumi_aws as aws

config = pulumi.Config("aws_infra")

PROJECT = config.require("project")
ENVIRONMENT = config.require("environment")

bucket_name = f"{PROJECT}-{ENVIRONMENT}-assets-pulumi"

# ---------------------------------------------------------
# S3 Bucket
# ---------------------------------------------------------
assets_bucket = aws.s3.Bucket(
    bucket_name,
    bucket=bucket_name,
    force_destroy=True,
)

# ---------------------------------------------------------
# Object Ownership (ALLOW ACLs so Django collectstatic works)
# ---------------------------------------------------------

ownership = aws.s3.BucketOwnershipControls(
    f"{bucket_name}-ownership",
    bucket=assets_bucket.id,
    rule=aws.s3.BucketOwnershipControlsRuleArgs(
        object_ownership="BucketOwnerPreferred"
    ),
)

# ---------------------------------------------------------
# Public read is needed for assets served via CloudFront or direct S3 URLs
# ---------------------------------------------------------
public_access = aws.s3.BucketPublicAccessBlock(
    f"{bucket_name}-public-access",
    bucket=assets_bucket.id,
    block_public_acls=False,
    ignore_public_acls=False,
    block_public_policy=False,
    restrict_public_buckets=False,
)

# ---------------------------------------------------------
# Default Encryption
# ---------------------------------------------------------
encryption = aws.s3.BucketServerSideEncryptionConfiguration(
    f"{bucket_name}-encryption",
    bucket=assets_bucket.id,
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

# ---------------------------------------------------------
# Exports
# ---------------------------------------------------------
pulumi.export("assets_bucket_name", assets_bucket.bucket)
pulumi.export("assets_bucket_arn", assets_bucket.arn)

import json
import pulumi
import pulumi_aws as aws

from storage.s3 import assets_bucket

config = pulumi.Config("aws_infra")

AWS_ACCOUNT_ID = config.require("aws_account_id")
CLOUDFRONT_DISTRIBUTION_ID = config.get("CLOUDFRONT_DISTRIBUTION_ID")


# Reference the EB EC2 role created in this stack
from iam_roles import ec2_role_pulumi as eb_ec2_role



# The app is fetching images using *plain S3 HTTPS URLs*, e.g.
#   https://<bucket>.s3.amazonaws.com/<key>
#
# That request is an *anonymous* HTTP GET (no AWS SigV4 signing), so IAM role
# permissions DO NOT apply. A private bucket will return 403 AccessDenied and
# your API surfaces it as a 500.
#
# Since we don't want to change app code to use boto3 (signed GetObject) or CloudFront
# URLs, the only infrastructure-only fix is:
#   1) allow public read (Principal="*") for s3:GetObject, AND
#   2) turn off the bucket’s PublicAccessBlock settings that currently prevent
#      public bucket policies from taking effect.
#
# This makes every object in the bucket publicly readable if someone knows or
# can guess the URL. Only do this if bucket contents are safe to be public.
# Prefer a future fix where the django app uses CloudFront URLs or signed S3 access.


# ---------------------------------------------------------
# Public Access Block (bucket-level)
# ---------------------------------------------------------

public_access_block = aws.s3.BucketPublicAccessBlock(
    "assets-bucket-public-access-block",
    bucket=assets_bucket.id,
    block_public_acls=False,
    ignore_public_acls=False,
    block_public_policy=False,
    restrict_public_buckets=False,
)

# ---------------------------------------------------------
# Bucket Policy
# ---------------------------------------------------------
bucket_policy = aws.s3.BucketPolicy(
    "assets-bucket-policy",
    bucket=assets_bucket.id,
    policy=pulumi.Output.all(
        assets_bucket.bucket,
        eb_ec2_role.arn,
    ).apply(
        lambda args: json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    # 1) CloudFront read-only
                    {
                        "Sid": "AllowCloudFrontServicePrincipalOnly",
                        "Effect": "Allow",
                        "Principal": {"Service": "cloudfront.amazonaws.com"},
                        "Action": ["s3:GetObject"],
                        "Resource": f"arn:aws:s3:::{args[0]}/*",
                        "Condition": {
                            "StringEquals": {
                                "AWS:SourceArn": (
                                    f"arn:aws:cloudfront::{AWS_ACCOUNT_ID}:distribution/"
                                    f"{CLOUDFRONT_DISTRIBUTION_ID}"
                                )
                            }
                        },
                    },

                    # 2) EB EC2 role: bucket-level permissions
                    {
                        "Sid": "AllowEbEc2RoleBucketAccess",
                        "Effect": "Allow",
                        "Principal": {"AWS": args[1]},
                        "Action": [
                            "s3:ListBucket",
                            "s3:GetBucketLocation",
                        ],
                        "Resource": f"arn:aws:s3:::{args[0]}",
                    },

                    # 3) EB EC2 role: object-level permissions (RW)
                    {
                        "Sid": "AllowEbEc2RoleObjectRW",
                        "Effect": "Allow",
                        "Principal": {"AWS": args[1]},
                        "Action": [
                            "s3:GetObject",
                            "s3:PutObject",
                            "s3:DeleteObject",
                        ],
                        "Resource": f"arn:aws:s3:::{args[0]}/*",
                    },

                    # 4) PUBLIC READ (infrastructure-only fix for anonymous S3 URL GETs)
                    {
                        "Sid": "AllowPublicReadObjectsForUnsignedHttpGet",
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": ["s3:GetObject"],
                        "Resource": f"arn:aws:s3:::{args[0]}/*",
                    },
                ],
            }
        )
    ),
    # Ensure the public-access-block config is applied before the policy
    opts=pulumi.ResourceOptions(depends_on=[public_access_block]),
)

pulumi.export("assets_bucket_policy_id", bucket_policy.id)
pulumi.export("assets_bucket_public_access_block_id", public_access_block.id)

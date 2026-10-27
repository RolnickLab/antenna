
"""
Defines the S3 bucket policy for the assets bucket.

Grants the EB EC2 role bucket and object-level access,
and enables public read access for static assets.
"""



import json
import pulumi
import pulumi_aws as aws

from storage.antennav2_s3 import assets_bucket, public_access, ownership
from antennav2_iam_roles import ec2_role_pulumi as eb_ec2_role

config = pulumi.Config("aws_infra")

AWS_ACCOUNT_ID = config.require("aws_account_id")


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
                    # -------------------------------------------------
                    # 1) EB EC2 role - bucket-level access
                    # -------------------------------------------------
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

                    # -------------------------------------------------
                    # 2) EB EC2 role - object-level RW
                    # -------------------------------------------------
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

                    # -------------------------------------------------
                    # 3) PUBLIC READ (required for unsigned HTTP GETs)
                    # -------------------------------------------------
                    {
                        "Sid": "AllowPublicReadObjects",
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": ["s3:GetObject"],
                        "Resource": f"arn:aws:s3:::{args[0]}/*",
                    },
                ],
            }
        )
    ),
    opts=pulumi.ResourceOptions(depends_on=[public_access, ownership]),
)

# ---------------------------------------------------------
# Exports
# ---------------------------------------------------------
pulumi.export("assets_bucket_policy_id", bucket_policy.id)

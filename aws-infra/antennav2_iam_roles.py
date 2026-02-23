
"""
Creates IAM roles for ECS and Elastic Beanstalk.

Grants scoped access to Secrets Manager, S3, ECR,
and required AWS services for application runtime.
Exports role and instance profile details.
"""



import json
import pulumi
import pulumi_aws as aws

from storage.antennav2_s3 import assets_bucket  # used for S3 bucket ARN resolution

# =========================================================
# Global project/stack context
# =========================================================


PROJECT = pulumi.get_project()
STACK = pulumi.get_stack()

secret_arn_pattern = pulumi.Output.concat(
    "arn:aws:secretsmanager:*:*:secret:",
    PROJECT,
    "-",
    STACK,
    "-*",
)


# =========================================================
# 1) ECS TASK EXECUTION ROLE
#
# Used by ECS TASKS (containers) to:
# - Pull images from ECR
# - Read secrets via ECS `valueFrom`
# =========================================================

ecs_execution_role = aws.iam.Role(
    "antenna-ecs-task-execution-role-pulumi",
    name="antenna-ecs-task-execution-role-pulumi",
    assume_role_policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    ),
    tags={"ManagedBy": "Pulumi", "Project": PROJECT},
)

# Standard ECS execution policy (ECR pulls + CloudWatch logs)
aws.iam.RolePolicyAttachment(
    "ecs-execution-policy-attach",
    role=ecs_execution_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
)

# Scoped Secrets Manager access
aws.iam.RolePolicy(
    "ecs-execution-secrets-readonly",
    role=ecs_execution_role.name,
    policy=secret_arn_pattern.apply(
        lambda arn: json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "AllowSecretsReadForEcsTasks",
                        "Effect": "Allow",
                        "Action": [
                            "secretsmanager:GetSecretValue",
                            "secretsmanager:DescribeSecret",
                        ],
                        "Resource": arn,
                    }
                ],
            }
        )
    ),
)

pulumi.export("ecs_execution_role_arn", ecs_execution_role.arn)

# =========================================================
# 2) ELASTIC BEANSTALK EC2 INSTANCE ROLE
#
# Used by:
# - EB platform
# - ECS agent on the EB host
# - EB deploy hooks
# - SSM Session Manager
# =========================================================

ec2_role_pulumi = aws.iam.Role(
    "aws-elasticbeanstalk-ec2-role_pulumi",
    name="aws-elasticbeanstalk-ec2-role_pulumi",
    assume_role_policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "ec2.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    ),
    tags={"ManagedBy": "Pulumi", "Project": PROJECT},
)

# Standard EB + ECS host permissions
ec2_policy_arns = [
    "arn:aws:iam::aws:policy/AWSElasticBeanstalkWebTier",
    "arn:aws:iam::aws:policy/AWSElasticBeanstalkWorkerTier",
    "arn:aws:iam::aws:policy/AWSElasticBeanstalkMulticontainerDocker",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
    "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy",
    "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
]

for i, policy_arn in enumerate(ec2_policy_arns):
    aws.iam.RolePolicyAttachment(
        f"aws-elasticbeanstalk-ec2-policy-{i}_pulumi",
        role=ec2_role_pulumi.name,
        policy_arn=policy_arn,
    )

# Scoped Secrets Manager access (same pattern as ECS)
aws.iam.RolePolicy(
    "eb-ec2-secretsmanager-readonly",
    role=ec2_role_pulumi.name,
    policy=secret_arn_pattern.apply(
        lambda arn: json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "AllowSecretsReadFromEc2",
                        "Effect": "Allow",
                        "Action": [
                            "secretsmanager:GetSecretValue",
                            "secretsmanager:DescribeSecret",
                        ],
                        "Resource": arn,
                    }
                ],
            }
        )
    ),
)

# =========================================================
# S3 access for assets bucket
# =========================================================

assets_bucket_arn = assets_bucket.arn
assets_objects_arn = assets_bucket.arn.apply(lambda a: f"{a}/*")

aws.iam.RolePolicy(
    "eb-ec2-assets-s3-access",
    role=ec2_role_pulumi.name,
    policy=pulumi.Output.all(assets_bucket_arn, assets_objects_arn).apply(
        lambda arns: json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "AllowAssetsBucketListAndLocation",
                        "Effect": "Allow",
                        "Action": [
                            "s3:ListBucket",
                            "s3:GetBucketLocation",
                        ],
                        "Resource": arns[0],
                    },
                    {
                        "Sid": "AllowAssetsObjectRW",
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetObject",
                            "s3:PutObject",
                            "s3:DeleteObject",
                        ],
                        "Resource": arns[1],
                    },
                ],
            }
        )
    ),
)

# Allow EB EC2 host to pass the ECS execution role
eb_ec2_passrole_ecs_execution = aws.iam.RolePolicy(

    "eb-ec2-passrole-ecs-execution-role",
    role=ec2_role_pulumi.name,
    policy=ecs_execution_role.arn.apply(
        lambda arn: json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "AllowPassRoleToEcs",
                        "Effect": "Allow",
                        "Action": "iam:PassRole",
                        "Resource": arn,
                    }
                ],
            }
        )
    ),
)

ec2_instance_profile_pulumi = aws.iam.InstanceProfile(
    "aws-elasticbeanstalk-ec2-instance-profile_pulumi",
    name="aws-elasticbeanstalk-ec2-instance-profile_pulumi",
    role=ec2_role_pulumi.name,
    tags={"ManagedBy": "Pulumi", "Project": PROJECT},
)

# =========================================================
# 3) ELASTIC BEANSTALK SERVICE ROLE
# =========================================================

service_role_pulumi = aws.iam.Role(
    "aws-elasticbeanstalk-service-role_pulumi",
    name="aws-elasticbeanstalk-service-role_pulumi",
    assume_role_policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "elasticbeanstalk.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    ),
    tags={"ManagedBy": "Pulumi", "Project": PROJECT},
)

service_policy_arns = [
    "arn:aws:iam::aws:policy/AWSElasticBeanstalkManagedUpdatesCustomerRolePolicy",
    "arn:aws:iam::aws:policy/service-role/AWSElasticBeanstalkEnhancedHealth",
]

for i, policy_arn in enumerate(service_policy_arns):
    aws.iam.RolePolicyAttachment(
        f"aws-elasticbeanstalk-service-policy-{i}_pulumi",
        role=service_role_pulumi.name,
        policy_arn=policy_arn,
    )

# =========================================================
# Outputs
# =========================================================

pulumi.export("eb_ec2_role_name_pulumi", ec2_role_pulumi.name)
pulumi.export("eb_ec2_instance_profile_name_pulumi", ec2_instance_profile_pulumi.name)
pulumi.export("eb_service_role_name_pulumi", service_role_pulumi.name)

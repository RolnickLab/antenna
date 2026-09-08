"""
Defines security groups for the application stack.

Creates security groups for Elastic Beanstalk, RDS (Postgres),
and Redis, controlling inbound and outbound traffic between
services and restricting admin access.
"""

import pulumi
import pulumi_aws as aws

# ---------------------------------------------------------
# Fetch the default VPC
# ---------------------------------------------------------

default_vpc = aws.ec2.get_vpc_output(default=True)

# ---------------------------------------------------------
# Elastic Beanstalk Security Group
# ---------------------------------------------------------
# Attached to the Elastic Beanstalk environment.
#
# Purpose:
# - Allow public HTTP/HTTPS access to the Django app
# - Allow outbound connections to RDS, Redis, APIs
# - Admin access should be done via SSH tunnel or VPN
# ---------------------------------------------------------

eb_sg = aws.ec2.SecurityGroup(
    "antenna-eb-sg-pulumi",
    description="SG attached to EB instance (inbound web + outbound app traffic)",
    vpc_id=default_vpc.id,

    ingress=[

        # -------------------------------------------------
        # Public HTTP access
        # -------------------------------------------------
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=80,
            to_port=80,
            cidr_blocks=["0.0.0.0/0"],
            description="Public HTTP access to the Django web app",
        ),

        # -------------------------------------------------
        # Public HTTPS access
        # -------------------------------------------------
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=443,
            to_port=443,
            cidr_blocks=["0.0.0.0/0"],
            description="Public HTTPS access to the Django web app",
        ),

        # -------------------------------------------------
        # Admin UI (Flower)
        # -------------------------------------------------
        # In production this should NOT be exposed through a
        # public security group rule.
        #
        # Instead access Flower via an SSH tunnel or VPN.
        #
        # Example:
        # ssh -L 5555:localhost:5555 ec2-user@<instance-ip>
        #
        # aws.ec2.SecurityGroupIngressArgs(
        #     protocol="tcp",
        #     from_port=5555,
        #     to_port=5555,
        #     cidr_blocks=["<your-ip>/32"],
        #     description="Admin access (Flower)",
        # ),

    ],

    # -------------------------------------------------
    # Egress rules
    # -------------------------------------------------
    # Allow application to connect to databases, caches,
    # and external APIs.
    egress=[
        aws.ec2.SecurityGroupEgressArgs(
            protocol="-1",
            from_port=0,
            to_port=0,
            cidr_blocks=["0.0.0.0/0"],
            description="Allow all outbound traffic",
        )
    ],

    tags={
        "Name": "antenna-eb-sg-pulumi"
    }
)

# ---------------------------------------------------------
# RDS (PostgreSQL) Security Group
# ---------------------------------------------------------
# Database is private and only accessible from:
# - Elastic Beanstalk application
# - Your IP (for debugging/admin)
# ---------------------------------------------------------

rds_sg = aws.ec2.SecurityGroup(
    "antenna-rds-sg-pulumi",
    description="Security group for RDS PostgreSQL",
    vpc_id=default_vpc.id,

    ingress=[

        # Allow Postgres access FROM the EB application
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=5432,
            to_port=5432,
            security_groups=[eb_sg.id],
            description="Postgres access from application",
        ),

        # Allow Postgres access FROM your IP
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=5432,
            to_port=5432,
            cidr_blocks=["<your-ip>/32"],   # replace with your IP
            description="Postgres admin access",
        ),
    ],

    # -------------------------------------------------
    # No explicit egress rules
    # -------------------------------------------------
    # Security groups are stateful, meaning responses to
    # allowed inbound connections are automatically allowed.
    # Therefore an open egress rule is unnecessary.
    tags={
        "Name": "antenna-rds-sg-pulumi"
    }
)

# ---------------------------------------------------------
# Redis Security Group
# ---------------------------------------------------------
# Similar model to RDS:
# - App can connect
# - Your IP allowed for debugging
# ---------------------------------------------------------

redis_sg = aws.ec2.SecurityGroup(
    "antenna-redis-sg-pulumi",
    description="Security group for Redis",
    vpc_id=default_vpc.id,

    ingress=[

        # Redis access FROM EB application
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=6379,
            to_port=6379,
            security_groups=[eb_sg.id],
            description="Redis access from application",
        ),

        # Redis access FROM your IP
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=6379,
            to_port=6379,
            cidr_blocks=["<your-ip>/32"],   # replace with your IP
            description="Redis admin access",
        ),
    ],

    # Open egress so Redis can respond to allowed connections
    egress=[
        aws.ec2.SecurityGroupEgressArgs(
            protocol="-1",
            from_port=0,
            to_port=0,
            cidr_blocks=["0.0.0.0/0"],
        )
    ],

    tags={
        "Name": "antenna-redis-sg-pulumi"
    }
)

# ---------------------------------------------------------
# Export Security Group IDs
# ---------------------------------------------------------

pulumi.export("eb_sg_id", eb_sg.id)
pulumi.export("rds_sg_id", rds_sg.id)
pulumi.export("redis_sg_id", redis_sg.id)

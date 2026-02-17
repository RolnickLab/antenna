import pulumi
import pulumi_aws as aws

# ---------------------------------------------------------
# Fetch the default VPC
# ---------------------------------------------------------

default_vpc = aws.ec2.get_vpc_output(default=True)

# ---------------------------------------------------------
# Elastic Beanstalk Security Group
# ---------------------------------------------------------
# This security group is attached to the Elastic Beanstalk
# environment.
#
# Purpose:
# - Allow the application to make outbound connections
#   (to RDS, Redis, external APIs, etc.)
# - Allow restricted inbound admin/debug access

# ---------------------------------------------------------

eb_sg = aws.ec2.SecurityGroup(
    "antenna-eb-sg-pulumi",
    description="SG attached to EB instance (inbound admin/debug + outbound app traffic)",
    vpc_id=default_vpc.id,

    # -----------------
    # INGRESS RULES
    # -----------------
    # Ingress controls who can initiate connections INTO
    # the Elastic Beanstalk environment.

    ingress=[
    # Allow incoming HTTP traffic on port 80 from anywhere.
    # This is needed because the Django app is directly exposed
    # on the EC2 instance (Single-Instance Elastic Beanstalk).
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=80,
            to_port=80,
            cidr_blocks=["0.0.0.0/0"],  # Public access
            description="Public HTTP access to the Django web app",
    ),

    # Allow incoming HTTPS traffic on port 443 from anywhere.
    # Use this ONLY if TLS/SSL is terminated on the EC2 instance itself.
    # If SSL is handled elsewhere (e.g., ALB or CloudFront), this can be removed.
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=443,
            to_port=443,
            cidr_blocks=["0.0.0.0/0"],  # Public access
            description="Public HTTPS access to the Django web app (optional)",
    ),


    # Admin UI (e.g. Flower) - restricted to your IP
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=5555,                   # Port used for admin UI (e.g. Flower)
            to_port=5555,
            cidr_blocks=[""],  # Only allow your personal IP
            description="Admin access (Flower)",
        ),

    ],

    # -----------------
    # EGRESS RULES
    # -----------------
    # Egress controls where the application can connect OUT to.
    # Allowing all outbound traffic is standard for app services
    # so they can reach databases, caches, and external APIs.
    egress=[
        aws.ec2.SecurityGroupEgressArgs(
            protocol="-1",              # -1 means all protocols
            from_port=0,
            to_port=0,
            cidr_blocks=["0.0.0.0/0"],  # Allow outbound traffic to anywhere
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
# This security group protects the PostgreSQL database.
#
# Design:
# - Database does NOT accept public traffic
# - Only the application SG and your IP can connect
# ---------------------------------------------------------

rds_sg = aws.ec2.SecurityGroup(
    "antenna-rds-sg-pulumi",
    description="Security group for RDS PostgreSQL",
    vpc_id=default_vpc.id,

    ingress=[
        # Allow Postgres access FROM the Elastic Beanstalk application
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=5432,             # PostgreSQL default port
            to_port=5432,
            security_groups=[eb_sg.id],
            description="Postgres access from application",
        ),

        # Allow Postgres access FROM your IP for manual admin/debugging
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=5432,
            to_port=5432,
            cidr_blocks=[""],  # Replace with your IP
            description="Postgres admin access",
        ),
    ],

    # Databases need open egress so they can respond to clients.
    # Security groups are stateful, so this does NOT expose the DB publicly.
    egress=[
        aws.ec2.SecurityGroupEgressArgs(
            protocol="-1",
            from_port=0,
            to_port=0,
            cidr_blocks=["0.0.0.0/0"],
        )
    ],

    tags={
        "Name": "antenna-rds-sg-pulumi"
    }
)

# ---------------------------------------------------------
# Redis Security Group
# ---------------------------------------------------------
# This security group protects the Redis cache.
#
# Design mirrors RDS:
# - EB App can connect
# - You can connect from your IP
# - No public access
# ---------------------------------------------------------

redis_sg = aws.ec2.SecurityGroup(
    "antenna-redis-sg-pulumi",
    description="Security group for Redis",
    vpc_id=default_vpc.id,

    ingress=[
        # Allow Redis access FROM the Elastic Beanstalk application
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=6379,             # Redis default port
            to_port=6379,
            security_groups=[eb_sg.id],
            description="Redis access from application",
        ),

        # Allow Redis access FROM your IP for debugging/admin
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=6379,
            to_port=6379,
            cidr_blocks=[""],  # Replace with your IP
            description="Redis admin access",
        ),
    ],

    # Open egress so Redis can respond to allowed inbound connections
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

"""
Creates and manages the private PostgreSQL RDS instance.

Configures subnet group, monitoring role, encryption,
and exports database connection details.
"""



import pulumi
import pulumi_aws as aws

from networking.antennav2_subnets import private_db_subnets
from networking.antennav2_security_group import rds_sg

config = pulumi.Config()

# -----------------------------
# DB config keys
# -----------------------------
POSTGRES_USER = config.get("POSTGRES_USER") or "postgres"
POSTGRES_DB = config.get("POSTGRES_DB") or "postgres"

POSTGRES_PORT = int(config.require("POSTGRES_PORT"))


POSTGRES_PASSWORD = config.require_secret("POSTGRES_PASSWORD")

# -----------------------------
# Get AWS-managed RDS KMS key ARN
# -----------------------------
rds_kms_key = aws.kms.get_key(key_id="alias/aws/rds")

# ---------------------------------------------------------
# IAM Role for Enhanced Monitoring
# ---------------------------------------------------------
monitoring_role = aws.iam.Role(
    "antenna-rds-monitoring-role-pulumi",
    name="antenna-rds-monitoring-role-pulumi",
    assume_role_policy="""{
      "Version": "2012-10-17",
      "Statement": [{
        "Effect": "Allow",
        "Principal": { "Service": "monitoring.rds.amazonaws.com" },
        "Action": "sts:AssumeRole"
      }]
    }""",
    tags={
        "Name": "antenna-rds-monitoring-role-pulumi",
        "ManagedBy": "Pulumi",
        "Project": "Antenna",
    },
)

aws.iam.RolePolicyAttachment(
    "antenna-rds-monitoring-policy-attach-pulumi",
    role=monitoring_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole",
)

# ---------------------------------------------------------
# RDS Subnet Group
# ---------------------------------------------------------
rds_subnet_group = aws.rds.SubnetGroup(
    "antenna-private-db-subnet-group-pulumi-v2",
    name="antenna-private-db-subnet-group-pulumi-v2",
    description="Private DB subnet group for Antenna Postgres (Pulumi)",
    subnet_ids=[s.id for s in private_db_subnets],
    tags={
        "Name": "antenna-private-db-subnet-group-pulumi",
        "ManagedBy": "Pulumi",
        "Project": "Antenna",
    },
)

# ---------------------------------------------------------
# RDS Instance
# ---------------------------------------------------------
rds_instance = aws.rds.Instance(
    "antenna-postgres1-pulumi",
    identifier="antenna-postgres1-pulumi",

    # Engine
    engine="postgres",
    engine_version="17.6",
    instance_class="db.t4g.medium",

    # DB init
    username=POSTGRES_USER,
    password=POSTGRES_PASSWORD,
    manage_master_user_password=False,
    db_name=POSTGRES_DB,
    port=POSTGRES_PORT,


    # Networking
    db_subnet_group_name=rds_subnet_group.name,
    vpc_security_group_ids=[rds_sg.id],
    publicly_accessible=False,

    # Storage
    storage_type="gp3",
    allocated_storage=30,
    max_allocated_storage=100,

    # Encryption
    storage_encrypted=True,
    kms_key_id=rds_kms_key.arn,

    # Availability
    multi_az=False,

    # Backups
    backup_retention_period=7,
    backup_window="10:40-11:10",

    # Maintenance
    maintenance_window="wed:06:24-wed:06:54",
    auto_minor_version_upgrade=True,

    # Enhanced Monitoring
    monitoring_interval=60,
    monitoring_role_arn=monitoring_role.arn,

    # Performance Insights
    performance_insights_enabled=True,
    performance_insights_retention_period=7,

    # Destroy behavior
    # Intentionally allow full teardown for this stack.
    # This environment is designed to be ephemeral and fully reproducible.
    # No final snapshot is required on destroy.

    deletion_protection=False,
    skip_final_snapshot=True,

    tags={
        "Name": "antenna-postgres1-pulumi",
        "ManagedBy": "Pulumi",
        "Project": "Antenna",
    },
)

# ---------------------------------------------------------
# Outputs
# ---------------------------------------------------------
pulumi.export("rds_instance_id", rds_instance.id)
pulumi.export("rds_endpoint", rds_instance.endpoint)
pulumi.export("rds_address", rds_instance.address)
pulumi.export("rds_port", POSTGRES_PORT)
pulumi.export("rds_subnet_group", rds_subnet_group.name)
pulumi.export("rds_security_group_id", rds_sg.id)
pulumi.export("private_db_subnet_ids", [s.id for s in private_db_subnets])
pulumi.export("rds_monitoring_role_arn", monitoring_role.arn)


import pulumi
import pulumi_aws as aws

from networking.subnets import redis_default_subnets
from networking.security_group import redis_sg

config = pulumi.Config()


# -------------------------------------------------------------------
REDIS_REPLICATION_GROUP_ID = "antenna-redis-pulumi"
REDIS_SUBNET_GROUP_NAME = "antenna-redis-subnet-group"

# Redis port from Pulumi config
REDIS_PORT = int(config.get("REDIS_PORT") or "6379")


# -------------------------------------------------------------------
# Uses AWS DEFAULT subnets in default VPC (redis_default_subnets)
# -------------------------------------------------------------------
def get_or_create_subnet_group():
    try:
        existing = aws.elasticache.get_subnet_group(name=REDIS_SUBNET_GROUP_NAME)
        pulumi.log.info(
            f"[Redis] Using existing ElastiCache subnet group: {existing.name}"
        )
        return existing.name
    except Exception:
        pulumi.log.warn(
            f"[Redis] Subnet group '{REDIS_SUBNET_GROUP_NAME}' not found. Creating new one..."
        )

        sg = aws.elasticache.SubnetGroup(
            "antenna-redis-subnet-group-pulumi",
            name=REDIS_SUBNET_GROUP_NAME,
            description="Subnet group for Antenna Redis (default VPC default subnets)",
            subnet_ids=[s.id for s in redis_default_subnets],
            tags={
                "Name": REDIS_SUBNET_GROUP_NAME,
                "ManagedBy": "Pulumi",
                "Project": "Antenna",
            },
        )
        return sg.name


redis_subnet_group_name = get_or_create_subnet_group()


# -------------------------------------------------------------------
# Redis Replication Group
# - Cluster mode disabled
# - Multi-AZ disabled
# - Auto-failover disabled
# - Engine Redis 7.1
# - cache.t4g.micro
# - TLS required
# - no access control
# -------------------------------------------------------------------
redis = aws.elasticache.ReplicationGroup(
    "antenna-redis-pulumi",
    replication_group_id=REDIS_REPLICATION_GROUP_ID,
    description="Private Redis cache for Antenna (Celery broker + backend)",

    engine="redis",
    engine_version="7.1",

    port=REDIS_PORT,

    node_type="cache.t4g.micro",
    parameter_group_name="default.redis7",

    num_cache_clusters=1,   # single node, no replicas
    multi_az_enabled=False,
    automatic_failover_enabled=False,

    # Networking
    subnet_group_name=redis_subnet_group_name,
    security_group_ids=[redis_sg.id],

    # Security
    at_rest_encryption_enabled=True,
    transit_encryption_enabled=True,
    transit_encryption_mode="required",

    # Backups disabled
    snapshot_retention_limit=0,

    # Maintenance window (Fri 09:30 UTC for 1 hour)
    maintenance_window="fri:09:30-fri:10:30",
    auto_minor_version_upgrade=True,

    tags={
        "Name": REDIS_REPLICATION_GROUP_ID,
        "ManagedBy": "Pulumi",
        "Project": "Antenna",
    },
)


# -------------------------------------------------------------------
# Outputs
# -------------------------------------------------------------------
pulumi.export("redis_replication_group_id", redis.id)
pulumi.export("redis_primary_endpoint", redis.primary_endpoint_address)
pulumi.export("redis_reader_endpoint", redis.reader_endpoint_address)

pulumi.export("redis_port", REDIS_PORT)

pulumi.export("redis_subnet_group_name", redis_subnet_group_name)
pulumi.export("redis_security_group_id", redis_sg.id)
pulumi.export("redis_subnet_ids", [s.id for s in redis_default_subnets])

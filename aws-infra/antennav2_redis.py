"""
Creates and manages the private Redis (ElastiCache) cluster.

Handles subnet group setup, security configuration,
and exports Redis endpoints for the application.
"""



import pulumi
import pulumi_aws as aws

from networking.antennav2_subnets import private_redis_subnets
from networking.antennav2_security_group import redis_sg

config = pulumi.Config()

REDIS_REPLICATION_GROUP_ID = "antenna-redis-pulumi"
REDIS_SUBNET_GROUP_NAME = "antenna-redis-subnet-group"
REDIS_PORT = int(config.get("REDIS_PORT") or "6379")


redis_subnet_group = aws.elasticache.SubnetGroup(
    "antenna-redis-subnet-group-pulumi",
    name=REDIS_SUBNET_GROUP_NAME,
    description="Subnet group for Antenna Redis (private subnets managed by Pulumi)",
    subnet_ids=[s.id for s in private_redis_subnets],
    tags={
        "Name": REDIS_SUBNET_GROUP_NAME,
        "ManagedBy": "Pulumi",
        "Project": "Antenna",
    },
)


redis = aws.elasticache.ReplicationGroup(
    "antenna-redis-pulumi",
    replication_group_id=REDIS_REPLICATION_GROUP_ID,
    description="Private Redis cache for Antenna (Celery broker + backend)",

    engine="redis",
    engine_version="7.1",
    port=REDIS_PORT,

    node_type="cache.t4g.micro",
    parameter_group_name="default.redis7",

    num_cache_clusters=1,
    multi_az_enabled=False,
    automatic_failover_enabled=False,

    subnet_group_name=redis_subnet_group.name,
    security_group_ids=[redis_sg.id],

    at_rest_encryption_enabled=True,
    transit_encryption_enabled=True,
    transit_encryption_mode="required",

    snapshot_retention_limit=0,
    maintenance_window="fri:09:30-fri:10:30",
    auto_minor_version_upgrade=True,

    tags={
        "Name": REDIS_REPLICATION_GROUP_ID,
        "ManagedBy": "Pulumi",
        "Project": "Antenna",
    },


    opts=pulumi.ResourceOptions(depends_on=[redis_subnet_group]),
)

pulumi.export("redis_replication_group_id", redis.id)
pulumi.export("redis_primary_endpoint", redis.primary_endpoint_address)
pulumi.export("redis_reader_endpoint", redis.reader_endpoint_address)
pulumi.export("redis_port", REDIS_PORT)
pulumi.export("redis_subnet_group_name", redis_subnet_group.name)
pulumi.export("redis_security_group_id", redis_sg.id)
pulumi.export("redis_subnet_ids", [s.id for s in private_redis_subnets])


# Assumes default AWS VPC (/16). Splitting into /20 yields 16 subnets,
# Custom smaller VPC CIDRs may require additional validation.

# This stack targets us-west-2 (our primary user region).
# us-west-2 consistently provides at least 3 availability zones,
# so selecting azs[:3] is valid for our deployment scope.
# Additional validation would be needed only if expanding to other regions.


"""
Subnets strategy:

We explicitly manage our own private subnets instead of relying on AWS “default subnets”

1) Redis (ElastiCache)
- We place Redis inside explicitly-created PRIVATE subnets in the default VPC.
- ElastiCache nodes do not get public IPs, and Redis is not internet-facing.
- Access is controlled via security groups (only the app SG + optional single admin IP for debugging).

2) RDS (Postgres)
- RDS must be launched in a DB Subnet Group.
- We create dedicated PRIVATE DB subnets across 3 AZs for high availability.
- These subnets have no public IP mapping and should use route tables without an Internet Gateway route.

CIDR strategy:
- We carve out /20 subnets from the default VPC CIDR, selecting blocks away from the “typical” default ranges
  to keep clear separation. (Even if defaults were deleted, the separation remains clean.)
"""

import ipaddress
import pulumi
import pulumi_aws as aws

# ---------------------------------------------------------
# Fetch the default VPC
# ---------------------------------------------------------
default_vpc = aws.ec2.get_vpc(default=True)

# Pick 3 AZs (High Availability)
azs = aws.get_availability_zones(state="available").names[:3]

# ---------------------------------------------------------
# Allocate CIDRs for our PRIVATE subnets
# ---------------------------------------------------------
vpc_cidr = ipaddress.ip_network(default_vpc.cidr_block)

# Split the VPC CIDR into /20 blocks (works if VPC is /16; adjust new_prefix if not)
cidr_blocks = list(vpc_cidr.subnets(new_prefix=20))

# Choose 6 /20 blocks: 3 for Redis, 3 for DB, away from the start of the range
# (Keep these stable so subnet CIDRs don't shift run-to-run.)
redis_cidrs = [cidr_blocks[6], cidr_blocks[9], cidr_blocks[10]]
db_cidrs    = [cidr_blocks[12], cidr_blocks[13], cidr_blocks[14]]

# ---------------------------------------------------------
# Create PRIVATE subnets for Redis (ElastiCache)
# ---------------------------------------------------------
private_redis_subnets = []
for i, az in enumerate(azs):
    subnet = aws.ec2.Subnet(
        f"antenna-pulumi-redis-private-{az[-1]}",  # ex: antenna-pulumi-redis-private-a
        vpc_id=default_vpc.id,
        cidr_block=str(redis_cidrs[i]),
        availability_zone=az,
        map_public_ip_on_launch=False,
        tags={"Name": f"antenna-pulumi-redis-private-{az[-1]}"},
    )
    private_redis_subnets.append(subnet)

pulumi.export("redis_private_subnet_ids", [s.id for s in private_redis_subnets])

# ---------------------------------------------------------
# Create PRIVATE subnets for RDS (DB Subnet Group)
# ---------------------------------------------------------
private_db_subnets = []
for i, az in enumerate(azs):
    subnet = aws.ec2.Subnet(
        f"antenna-pulumi-db-private-{az[-1]}",  # ex: antenna-pulumi-db-private-a
        vpc_id=default_vpc.id,
        cidr_block=str(db_cidrs[i]),
        availability_zone=az,
        map_public_ip_on_launch=False,
        tags={"Name": f"antenna-pulumi-db-private-{az[-1]}"},
    )
    private_db_subnets.append(subnet)

pulumi.export("db_private_subnet_ids", [s.id for s in private_db_subnets])

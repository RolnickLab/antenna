"""
Subnets strategy:

Redis (ElastiCache) uses the AWS default subnets in the default VPC because ElastiCache nodes do not receive public IPs
by default and are never directly exposed to the internet. Access to Redis is strictly controlled through a dedicated
security group that only allows inbound traffic from the application security group and a single admin IP for debugging,
which is sufficient to keep it private.


In contrast, RDS requires explicitly creating private database subnets because AWS mandates that RDS be launched
inside a DB subnet group. By creating new private subnets across multiple AZs, we ensure the database has no internet
gateway routes and cannot be accidentally exposed.


Since default subnets typically occupy the first /20 CIDR blocks, we carve out new /20 ranges away from the defaults
to maintain clear separation and stronger network isolation for the database.
"""

import ipaddress
import pulumi
import pulumi_aws as aws


# ---------------------------------------------------------
# Fetch the default VPC
# ---------------------------------------------------------
default_vpc = aws.ec2.get_vpc(default=True)


# ---------------------------------------------------------
# Redis: Use AWS DEFAULT subnets (in the default VPC)
# ---------------------------------------------------------

# Only keep AWS "default subnets"
aws_default_subnet_ids = aws.ec2.get_subnets(
    filters=[
        {"name": "vpc-id", "values": [default_vpc.id]},
        {"name": "default-for-az", "values": ["true"]},
    ]
).ids

redis_default_subnets = [
    aws.ec2.Subnet.get(f"aws-default-subnet-{i}", subnet_id)
    for i, subnet_id in enumerate(aws_default_subnet_ids)
]

pulumi.export("redis_default_subnet_ids", aws_default_subnet_ids)


# ---------------------------------------------------------
# RDS: Create 3 NEW PRIVATE DB subnets
# ---------------------------------------------------------
vpc_cidr = ipaddress.ip_network(default_vpc.cidr_block)

# Split /16 into /20s
cidr_blocks = list(vpc_cidr.subnets(new_prefix=20))

# SAFETY: skip first 4 blocks (these are typically AWS default subnets)
db_cidrs = [cidr_blocks[4], cidr_blocks[7], cidr_blocks[8]]  # exactly 3 subnets


# Pick 3 AZs (High Availability)
azs = aws.get_availability_zones(state="available").names[:3]

private_db_subnets = []
for i, az in enumerate(azs):
    subnet = aws.ec2.Subnet(
        f"antenna-pulumi-private-{az[-1]}",     # ex: antenna-pulumi-private-a, antenna-pulumi-private-b
        vpc_id=default_vpc.id,
        cidr_block=str(db_cidrs[i]),
        availability_zone=az,
        map_public_ip_on_launch=False,
        tags={"Name": f"antenna-pulumi-private-{az[-1]}"},
    )
    private_db_subnets.append(subnet)

pulumi.export("private_db_subnet_ids", [s.id for s in private_db_subnets])

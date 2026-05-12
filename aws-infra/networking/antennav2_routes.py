"""
This creates a dedicated private route table that is associated only with the custom RDS private subnets.
The default AWS route table and default subnets are left untouched.
Since this route table contains only the default local VPC route and no internet or NAT gateway routes,
any resources launched in these subnets can communicate only within the VPC.
This ensures the RDS database remains fully private and inaccessible from the public internet.
"""

import pulumi
import pulumi_aws as aws
from .antennav2_subnets import default_vpc, private_db_subnets


# ---------------------------------------------------------
# Private route table
# ---------------------------------------------------------
private_rt = aws.ec2.RouteTable(
    "antenna-pulumi-private-rt",
    vpc_id=default_vpc.id,
    tags={"Name": "antenna-pulumi-private-rt"},
)

# ---------------------------------------------------------
# Associate ONLY DB private subnets
# ---------------------------------------------------------
for i, subnet in enumerate(private_db_subnets[:2]):
    aws.ec2.RouteTableAssociation(
        f"antenna-pulumi-private-rt-assoc-{i}",
        subnet_id=subnet.id,
        route_table_id=private_rt.id,
    )

pulumi.export("private_route_table_id", private_rt.id)
pulumi.export("attached_subnet_ids", [s.id for s in private_db_subnets[:2]])

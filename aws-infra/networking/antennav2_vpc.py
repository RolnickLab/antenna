"""
Fetches and exports the AWS default VPC.

This stack reuses the default VPC instead of creating a new one.
"""



import pulumi
import pulumi_aws as aws

# We do not create a VPC. We just use the AWS default VPC.

default_vpc = aws.ec2.get_vpc(default=True)

pulumi.export("vpc_id", default_vpc.id)

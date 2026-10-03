"""
Creates and configures ECR repositories.
Exports repository URLs for Docker builds and deployment.
"""
import pulumi
import pulumi_aws as aws

# Repositories to create
REPOS = [
    "antenna-pulumi",
]

ecr_repos = {}

for repo in REPOS:
    ecr_repos[repo] = aws.ecr.Repository(
        repo,
        name=repo,

        force_delete=True,

        # Scan on push = OFF (enable for production)
        image_scanning_configuration=aws.ecr.RepositoryImageScanningConfigurationArgs(
            scan_on_push=False
        ),

        # Mutable tags
        image_tag_mutability="MUTABLE",

        # Encryption: AES-256 (SSE-S3)
        encryption_configurations=[
            aws.ecr.RepositoryEncryptionConfigurationArgs(
                encryption_type="AES256"
            )
        ],

        tags={
            "Name": repo,
            "ManagedBy": "Pulumi",
            "Project": "Antenna",
        },
    )




# outputs for EB Dockerrun generation
pulumi.export("ecr_repo_url", ecr_repos["antenna-pulumi"].repository_url)


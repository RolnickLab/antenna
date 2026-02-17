import pulumi
import pulumi_aws as aws

# Repositories to create
REPOS = [
    "antenna-awscli-pulumi",
    "antenna-backend-pulumi",
    "antenna-ml-example-pulumi",
    "antenna-ml-minimal-pulumi",
]

ecr_repos = {}

for repo in REPOS:
    ecr_repos[repo] = aws.ecr.Repository(
        repo,
        name=repo,

        force_delete=True,

        # Scan on push = ON
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
pulumi.export("ecr_backend_repo_url", ecr_repos["antenna-backend-pulumi"].repository_url)
pulumi.export("ecr_awscli_repo_url", ecr_repos["antenna-awscli-pulumi"].repository_url)
pulumi.export("ecr_ml_min_repo_url", ecr_repos["antenna-ml-minimal-pulumi"].repository_url)
pulumi.export("ecr_ml_ex_repo_url", ecr_repos["antenna-ml-example-pulumi"].repository_url)

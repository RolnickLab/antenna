"""
Builds and pushes Docker images to ECR using Pulumi Docker v4.
"""

import os
import base64
import hashlib
import pulumi
import pulumi_aws as aws
import pulumi_docker as docker
import antennav2_ecr

pulumi.log.info("=== antennav2_images module loaded ===")

# -------------------------------------------------------------------
# AWS info
# -------------------------------------------------------------------
caller = aws.get_caller_identity()
region = aws.get_region()

# -------------------------------------------------------------------
# Repo root
# -------------------------------------------------------------------
REPO_ROOT = os.path.realpath(
    os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

if not os.path.exists(os.path.join(REPO_ROOT, "pyproject.toml")):
    raise RuntimeError(f"Invalid REPO_ROOT detected: {REPO_ROOT}")

# -------------------------------------------------------------------
# Hash entire build context
# -------------------------------------------------------------------
def hash_directory(path: str) -> str:
    sha = hashlib.sha256()

    EXCLUDE_DIRS = {
        ".git",
        "__pycache__",
        ".venv",
        "node_modules",
        "build",
        "dist",
    }

    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        for file in sorted(files):
            file_path = os.path.join(root, file)

            try:
                with open(file_path, "rb") as f:
                    file_hash = hashlib.file_digest(f, "sha256")
                    sha.update(file_hash.digest())
            except Exception:
                continue

    return sha.hexdigest()

# -------------------------------------------------------------------
# ECR repo
# -------------------------------------------------------------------
repo = antennav2_ecr.ecr_repos["antenna-pulumi"]
repo_url = repo.repository_url

# -------------------------------------------------------------------
# ECR authentication
# -------------------------------------------------------------------
ecr_token = aws.ecr.get_authorization_token_output()

def build_registry():
    return pulumi.Output.all(
        ecr_token.authorization_token,
        ecr_token.proxy_endpoint,
    ).apply(_decode_ecr)

def _decode_ecr(args):
    token, endpoint = args
    decoded = base64.b64decode(token).decode()
    username, password = decoded.split(":")

    return docker.RegistryArgs(
        server=endpoint.replace("https://", ""),
        username=username,
        password=password,
    )

registry = build_registry()

# -------------------------------------------------------------------
# Tags (logical names only)
# -------------------------------------------------------------------
BACKEND_TAG = "backend"
AWSCLI_TAG = "awscli"
ML_MIN_TAG = "ml-minimal"
ML_EX_TAG = "ml-example"

# -------------------------------------------------------------------
# Helper
# -------------------------------------------------------------------
def _abs(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.abspath(os.path.join(REPO_ROOT, path))

# -------------------------------------------------------------------
# Build + Push
# -------------------------------------------------------------------
def build_push_image(name: str, tag: str, dockerfile_path: str, context_path: str):

    dockerfile_abs = _abs(dockerfile_path)
    context_abs = _abs(context_path)

    pulumi.log.info(f"Building image: {name}")
    pulumi.log.info(f"Dockerfile: {dockerfile_abs}")
    pulumi.log.info(f"Context: {context_abs}")

    # FULL content hash of context
    context_hash = hash_directory(context_abs)

    image_name = pulumi.Output.concat(
        repo_url,
        ":",
        tag,

    )

    return docker.Image(
        name,
        build=docker.DockerBuildArgs(
            context=context_abs,
            dockerfile=dockerfile_abs,
            platform="linux/amd64",
        ),
        image_name=image_name,
        registry=registry,
    )

# -------------------------------------------------------------------
# Images
# -------------------------------------------------------------------
backend_image = build_push_image(
    "backend-image",
    BACKEND_TAG,
    "compose/production/django/Dockerfile",
    ".",
)

awscli_image = build_push_image(
    "awscli-image",
    AWSCLI_TAG,
    "compose/production/aws/Dockerfile",
    ".",
)

ml_min_image = build_push_image(
    "ml-minimal-image",
    ML_MIN_TAG,
    "processing_services/minimal/Dockerfile",
    "processing_services/minimal",
)

ml_ex_image = build_push_image(
    "ml-example-image",
    ML_EX_TAG,
    "processing_services/example/Dockerfile",
    "processing_services/example",
)

# -------------------------------------------------------------------
# Outputs
# -------------------------------------------------------------------
pulumi.export("backend_image_uri", backend_image.image_name)
pulumi.export("awscli_image_uri", awscli_image.image_name)
pulumi.export("ml_min_image_uri", ml_min_image.image_name)
pulumi.export("ml_ex_image_uri", ml_ex_image.image_name)

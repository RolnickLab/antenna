import os
import hashlib
import pulumi
import pulumi_aws as aws
from pulumi_command import local
import ecr

# -------------------------------------------------------------------
# AWS account + region info
# -------------------------------------------------------------------
caller = aws.get_caller_identity()   # gets AWS account ID
region = aws.get_region()            # gets current AWS region

# -------------------------------------------------------------------
# Repo root (used to resolve relative Docker paths reliably)
# -------------------------------------------------------------------
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# -------------------------------------------------------------------
# Isolated Docker config (avoids conflicts with ~/.docker)
# -------------------------------------------------------------------
DOCKER_CONFIG_DIR = "/tmp/pulumi-docker-config"
DOCKER_CONFIG_JSON = os.path.join(DOCKER_CONFIG_DIR, "config.json")

# -------------------------------------------------------------------
# Docker image tags
# -------------------------------------------------------------------
BACKEND_TAG = "latest"
AWSCLI_TAG = "latest"
ML_MIN_TAG = "latest"
ML_EX_TAG = "latest"

# -------------------------------------------------------------------
# ECR repository URLs (created in ecr.py)
# -------------------------------------------------------------------
backend_repo_url = ecr.ecr_repos["antenna-backend-pulumi"].repository_url
awscli_repo_url = ecr.ecr_repos["antenna-awscli-pulumi"].repository_url
mlmin_repo_url = ecr.ecr_repos["antenna-ml-minimal-pulumi"].repository_url
mlex_repo_url = ecr.ecr_repos["antenna-ml-example-pulumi"].repository_url

# -------------------------------------------------------------------
# Helper: convert relative paths to absolute paths
# (Docker + Pulumi are safer with absolute paths)
# -------------------------------------------------------------------
def _abs(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.abspath(os.path.join(REPO_ROOT, path))

# -------------------------------------------------------------------
# Helper: create a hash from Docker build inputs
# Used to trigger rebuilds only when inputs change

# Build context path is the directory Docker is allowed to see during the build.


# -------------------------------------------------------------------
def _hash_build_inputs(dockerfile_path: str, context_path: str) -> str:
    h = hashlib.sha256()
    h.update(dockerfile_path.encode("utf-8"))  # include Dockerfile path
    h.update(context_path.encode("utf-8"))     # include build context path
    return h.hexdigest()

# -------------------------------------------------------------------
# Docker setup script
# - resets Docker config
# - restores buildx plugin (needed when DOCKER_CONFIG is custom)

# buildx:
# Docker build extension that supports modern features like BuildKit,
# cross-platform builds (e.g. linux/amd64 for AWS),
# Required here so images built on Mac (ARM) run correctly on AWS (x86).

# -------------------------------------------------------------------
DOCKER_SETUP_BLOCK = f"""
export DOCKER_CONFIG="{DOCKER_CONFIG_DIR}"
mkdir -p "$DOCKER_CONFIG"
rm -f "{DOCKER_CONFIG_JSON}"

# Create a clean Docker config (no cached auth)
cat > "{DOCKER_CONFIG_JSON}" << "EOF"
{{
  "auths": {{}},
  "credsStore": "",
  "credHelpers": {{}}
}}
EOF

# Docker looks for plugins in $DOCKER_CONFIG/cli-plugins
mkdir -p "$DOCKER_CONFIG/cli-plugins"

# Restore docker-buildx plugin from common install locations
if [ -f "$HOME/.docker/cli-plugins/docker-buildx" ]; then
  ln -sf "$HOME/.docker/cli-plugins/docker-buildx" "$DOCKER_CONFIG/cli-plugins/docker-buildx"
elif [ -f "/usr/local/lib/docker/cli-plugins/docker-buildx" ]; then
  ln -sf "/usr/local/lib/docker/cli-plugins/docker-buildx" "$DOCKER_CONFIG/cli-plugins/docker-buildx"
elif [ -f "/opt/homebrew/lib/docker/cli-plugins/docker-buildx" ]; then
  ln -sf "/opt/homebrew/lib/docker/cli-plugins/docker-buildx" "$DOCKER_CONFIG/cli-plugins/docker-buildx"
fi

# Debug info to confirm setup
echo "Using DOCKER_CONFIG=$DOCKER_CONFIG"
ls -la "$DOCKER_CONFIG/cli-plugins" || true
"""

# =========================================================
# Helper: authenticate Docker to ECR WITHOUT using macOS Keychain
# - avoids `docker login` credential helper storing duplicates in Keychain
# - writes auth directly into the isolated DOCKER_CONFIG/config.json
# =========================================================
ECR_AUTH_BLOCK = r"""
PASS="$(aws ecr get-login-password --region "$REGION")"
AUTH="$(printf 'AWS:%s' "$PASS" | base64)"
cat > "$DOCKER_CONFIG/config.json" <<EOF
{
  "auths": {
    "$REGISTRY": { "auth": "$AUTH" }
  },
  "credsStore": "",
  "credHelpers": {}
}
EOF
"""

# =========================================================
# 1) ECR Login (local command)
# =========================================================
ecr_login = local.Command(
    "ecr-login",
    create=pulumi.Output.all(caller.account_id, region.name).apply(
        lambda args: f"""
set -euo pipefail

ACCOUNT_ID="{args[0]}"
REGION="{args[1]}"
REGISTRY="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

{DOCKER_SETUP_BLOCK}

# Ensure clean auth WITHOUT writing to Keychain
{ECR_AUTH_BLOCK}

echo "ECR auth ok -> $REGISTRY"
docker buildx version
"""
    ),
    # Re-run login if account or region changes
    triggers=[pulumi.Output.all(caller.account_id, region.name)],
)

# =========================================================
# Helper: build + push Docker image to ECR
# =========================================================
def build_push_image(name: str, tag: str, repo_url, dockerfile_path: str, context_path: str):
    dockerfile_abs = _abs(dockerfile_path)     # absolute Dockerfile path
    context_abs = _abs(context_path)            # absolute build context
    input_hash = _hash_build_inputs(dockerfile_abs, context_abs)

    # Triggers decide when Pulumi reruns this command
    triggers = [tag, dockerfile_abs, context_abs, input_hash, repo_url]

    return local.Command(
        name,
        create=pulumi.Output.all(repo_url, caller.account_id, region.name).apply(
            lambda args: f"""
set -euo pipefail

REPO_URL="{args[0]}"
ACCOUNT_ID="{args[1]}"
REGION="{args[2]}"
REGISTRY="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

export DOCKER_BUILDKIT=1

{DOCKER_SETUP_BLOCK}

# Auth again to ensure Docker can push (no Keychain writes)
{ECR_AUTH_BLOCK}

echo "Building + pushing -> $REPO_URL:{tag}"
echo "Dockerfile -> {dockerfile_abs}"
echo "Context -> {context_abs}"

docker buildx version

# Build for AWS-compatible architecture and push to ECR
docker buildx build --platform linux/amd64 \
  -f "{dockerfile_abs}" \
  -t "${{REPO_URL}}:{tag}" \
  "{context_abs}" \
  --push

echo "Pushed -> $REPO_URL:{tag}"
"""
        ),
        # Ensure ECR login happens first
        opts=pulumi.ResourceOptions(depends_on=[ecr_login]),
        triggers=triggers,
    )

# =========================================================
# Image builds
# =========================================================
backend_cmd = build_push_image(
    "build-push-backend",
    BACKEND_TAG,
    backend_repo_url,
    "compose/production/django/Dockerfile",
    ".",
)

awscli_cmd = build_push_image(
    "build-push-awscli",
    AWSCLI_TAG,
    awscli_repo_url,
    "compose/production/aws/Dockerfile",
    ".",
)

ml_min_cmd = build_push_image(
    "build-push-ml-minimal",
    ML_MIN_TAG,
    mlmin_repo_url,
    "processing_services/minimal/Dockerfile",
    "processing_services/minimal",
)

ml_ex_cmd = build_push_image(
    "build-push-ml-example",
    ML_EX_TAG,
    mlex_repo_url,
    "processing_services/example/Dockerfile",
    "processing_services/example",
)

# =========================================================
# Outputs (final image URIs)
# =========================================================
pulumi.export("backend_image_uri", pulumi.Output.concat(backend_repo_url, ":", BACKEND_TAG))
pulumi.export("awscli_image_uri", pulumi.Output.concat(awscli_repo_url, ":", AWSCLI_TAG))
pulumi.export("ml_min_image_uri", pulumi.Output.concat(mlmin_repo_url, ":", ML_MIN_TAG))
pulumi.export("ml_ex_image_uri", pulumi.Output.concat(mlex_repo_url, ":", ML_EX_TAG))

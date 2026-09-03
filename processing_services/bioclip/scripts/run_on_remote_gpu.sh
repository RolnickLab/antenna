#!/usr/bin/env bash
#
# Tunnel the bioclip processing service running on a remote GPU host into a local
# Antenna stack.
#
# Usage: ./run_on_remote_gpu.sh <ssh-host> [local-port] [remote-port]
#
# Opens two forwards over one SSH connection:
#   -L  local:2004        -> remote:2000    Antenna calls the service   (sync/push mode)
#   -R  remote:9000       -> local:9000     the service downloads captures from minio
#   -R  remote:8000       -> local:8000     the ADC worker calls Antenna (async/pull mode)
#
# The reverse forward is required because Antenna signs capture URLs as
# http://minio:9000/... and the host name is covered by the S3 signature, so it
# cannot be rewritten. The remote host needs "127.0.0.1 minio" in /etc/hosts.
#
# Register the service in Antenna as http://host.docker.internal:2004
#
# The connection is reopened automatically if it drops, which it will over a long
# job or an idle period. Ctrl-C to stop for good.
set -uo pipefail

SSH_HOST="${1:?usage: $0 <ssh-host> [local-port] [remote-port]}"
LOCAL_PORT="${2:-2004}"
REMOTE_PORT="${3:-2000}"
MINIO_PORT=9000
API_PORT=8000
RETRY_DELAY=5

echo "Antenna  -> http://host.docker.internal:${LOCAL_PORT} -> ${SSH_HOST}:${REMOTE_PORT}"
echo "service  -> http://minio:${MINIO_PORT} -> local minio-proxy"
echo "worker   -> http://127.0.0.1:${API_PORT}/api/v2 -> local Antenna API"
echo "Ctrl-C to close the tunnel."

trap 'echo; echo "tunnel closed."; exit 0' INT TERM

while true; do
    ssh -N -T \
        -o ExitOnForwardFailure=yes \
        -o ServerAliveInterval=15 \
        -o ServerAliveCountMax=3 \
        -o TCPKeepAlive=yes \
        -L "127.0.0.1:${LOCAL_PORT}:127.0.0.1:${REMOTE_PORT}" \
        -R "127.0.0.1:${MINIO_PORT}:127.0.0.1:${MINIO_PORT}" \
        -R "127.0.0.1:${API_PORT}:127.0.0.1:${API_PORT}" \
        "$SSH_HOST"
    echo "$(date '+%H:%M:%S') tunnel dropped, reconnecting in ${RETRY_DELAY}s..." >&2
    sleep "$RETRY_DELAY"
done

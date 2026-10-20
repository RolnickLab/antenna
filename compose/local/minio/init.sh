#!/bin/sh
# Stop on the first error so a failed bucket setup fails this container instead of passing silently.
set -e

# Create the default buckets. Current mc releases dropped `mc config host add`, so use `mc alias set`.
/usr/bin/mc alias set local "${MINIO_ENDPOINT}" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}"
/usr/bin/mc mb local/"${MINIO_DEFAULT_BUCKET}" --ignore-existing
/usr/bin/mc mb local/"${MINIO_TEST_BUCKET}" --ignore-existing

# Give it public read access
/usr/bin/mc anonymous set public local/"${MINIO_DEFAULT_BUCKET}"
/usr/bin/mc anonymous set public local/"${MINIO_TEST_BUCKET}"

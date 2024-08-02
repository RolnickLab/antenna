#!/bin/sh

# Create a default bucket
/usr/bin/mc config host add local "${MINIO_ENDPOINT}" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}"
/usr/bin/mc mb local/"${MINIO_DEFAULT_BUCKET}" --ignore-existing

# Give it public access
# /usr/bin/mc policy set public local/"${MINIO_DEFAULT_BUCKET}"
# /usr/bin/mc anonymous set upload local/"${MINIO_DEFAULT_BUCKET}"
# /usr/bin/mc anonymous set download local/"${MINIO_DEFAULT_BUCKET}"
# /usr/bin/mc anonymous set public local/"${MINIO_DEFAULT_BUCKET}"
exit 0

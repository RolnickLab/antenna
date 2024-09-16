#!/bin/sh

# Create a default bucket
# /usr/bin/mc set alias minio "${MINIO_ENDPOINT}" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}"
/usr/bin/mc config host add local "${MINIO_ENDPOINT}" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}"
/usr/bin/mc mb local/"${MINIO_DEFAULT_BUCKET}" --ignore-existing
/usr/bin/mc mb local/"${MINIO_TEST_BUCKET}" --ignore-existing

# Give it public read access
/usr/bin/mc anonymous set public local/"${MINIO_DEFAULT_BUCKET}"
/usr/bin/mc anonymous set public local/"${MINIO_TEST_BUCKET}"

exit 0

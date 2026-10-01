FROM postgres:16
# FROM esgn/pgtuned:latest

# pgvector, required by ami.ml.models.DetectionEmbedding.
#
# Installed into the stock image rather than switching the base to
# pgvector/pgvector:pg16. That image is built on Debian 12 (glibc 2.36) while
# postgres:16 is on Debian 13 (glibc 2.41), so swapping it under an existing PGDATA
# volume makes Postgres report a collation version mismatch and would need a full
# REINDEX. Same extension version (0.8.6) either way.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*

COPY ./compose/local/postgres/maintenance /usr/local/bin/maintenance
RUN chmod +x /usr/local/bin/maintenance/*
RUN mv /usr/local/bin/maintenance/* /usr/local/bin \
    && rmdir /usr/local/bin/maintenance

FROM postgres:16
# FROM esgn/pgtuned:latest

# pgvector for Classification.features_2048 (migration 0096). Pinned to the 0.8 series so
# every environment starts on the same current release.
ARG PGVECTOR_VERSION=0.8.*
RUN apt-get update \
    && apt-get install -y --no-install-recommends "postgresql-16-pgvector=${PGVECTOR_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

COPY ./compose/local/postgres/maintenance /usr/local/bin/maintenance
RUN chmod +x /usr/local/bin/maintenance/*
RUN mv /usr/local/bin/maintenance/* /usr/local/bin \
    && rmdir /usr/local/bin/maintenance

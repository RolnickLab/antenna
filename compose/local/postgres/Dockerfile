FROM postgres:16
# FROM esgn/pgtuned:latest

# pgvector stores feature vectors (DetectionEmbedding). The 0.8 series is the floor the
# migration checks for, so local and CI databases get the same release as production.
ARG PGVECTOR_VERSION=0.8.*
RUN apt-get update \
    && apt-get install -y --no-install-recommends "postgresql-16-pgvector=${PGVECTOR_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

COPY ./compose/local/postgres/maintenance /usr/local/bin/maintenance
RUN chmod +x /usr/local/bin/maintenance/*
RUN mv /usr/local/bin/maintenance/* /usr/local/bin \
    && rmdir /usr/local/bin/maintenance

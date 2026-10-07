FROM postgres:16
# FROM esgn/pgtuned:latest

# pgvector stores feature vectors (DetectionEmbedding). Migration ml/0029 enforces the 0.8 floor,
# so the package is not pinned and a newer PGDG release does not break the build.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*

COPY ./compose/local/postgres/maintenance /usr/local/bin/maintenance
RUN chmod +x /usr/local/bin/maintenance/*
RUN mv /usr/local/bin/maintenance/* /usr/local/bin \
    && rmdir /usr/local/bin/maintenance

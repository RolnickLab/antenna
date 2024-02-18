FROM postgres:16
# FROM esgn/pgtuned:latest

COPY ./compose/local/postgres/postgresql.conf /var/lib/postgresql/data/
COPY ./compose/local/postgres/maintenance /usr/local/bin/maintenance
RUN chmod +x /usr/local/bin/maintenance/*
RUN mv /usr/local/bin/maintenance/* /usr/local/bin \
    && rmdir /usr/local/bin/maintenance

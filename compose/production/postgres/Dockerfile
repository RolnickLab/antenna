FROM postgres:14
# FROM esgn/pgtuned:latest

COPY ./compose/production/postgres/postgresql.conf /var/lib/postgresql/data/
COPY ./compose/production/postgres/maintenance /usr/local/bin/maintenance
RUN chmod +x /usr/local/bin/maintenance/*
RUN mv /usr/local/bin/maintenance/* /usr/local/bin \
    && rmdir /usr/local/bin/maintenance

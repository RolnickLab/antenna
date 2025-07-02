FROM postgres:16


# Install build dependencies and pgvector
RUN apt-get update && apt-get install -y \
   postgresql-server-dev-16 \
   make \
   g++ \
   git \
&& git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git \
&& cd pgvector \
&& make && make install \
&& cd .. \
&& rm -rf pgvector \
&& apt-get remove -y git g++ make \
&& apt-get autoremove -y && apt-get clean


# Copy maintenance scripts
COPY ./compose/local/postgres/maintenance /usr/local/bin/maintenance
RUN chmod +x /usr/local/bin/maintenance/* \
&& mv /usr/local/bin/maintenance/* /usr/local/bin \
&& rmdir /usr/local/bin/maintenance

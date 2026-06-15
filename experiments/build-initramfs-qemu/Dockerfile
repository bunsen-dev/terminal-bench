FROM ubuntu:24.04

WORKDIR /app

COPY prepare-seed.sh /app/prepare-seed.sh
RUN chmod +x /app/prepare-seed.sh
RUN /app/prepare-seed.sh

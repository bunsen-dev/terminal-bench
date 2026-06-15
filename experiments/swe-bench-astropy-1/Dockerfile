FROM python:3.9-slim-bookworm

RUN apt-get update && apt-get install -y gcc git patch && rm -rf /var/lib/apt/lists/*

COPY vendor/astropy-d16bfe05a744909de4b27f5875fe0d4ed41ce607.tar.gz /tmp/vendor/
COPY vendor/astropy-d16bfe05a744909de4b27f5875fe0d4ed41ce607.tar.gz.sha256 /tmp/vendor/

RUN cd /tmp/vendor && \
    sha256sum -c astropy-d16bfe05a744909de4b27f5875fe0d4ed41ce607.tar.gz.sha256 && \
    mkdir -p /opt/task/astropy && \
    tar -xzf astropy-d16bfe05a744909de4b27f5875fe0d4ed41ce607.tar.gz -C /opt/task/astropy --strip-components=1 && \
    rm -rf /tmp/vendor

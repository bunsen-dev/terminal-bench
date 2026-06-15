FROM python:3.9-slim-bookworm

RUN apt-get update && apt-get install -y gcc git patch && rm -rf /var/lib/apt/lists/*

COPY vendor/astropy-7269fa3e33e8d02485a647da91a5a2a60a06af61.tar.gz /tmp/vendor/
COPY vendor/astropy-7269fa3e33e8d02485a647da91a5a2a60a06af61.tar.gz.sha256 /tmp/vendor/

RUN cd /tmp/vendor && \
    sha256sum -c astropy-7269fa3e33e8d02485a647da91a5a2a60a06af61.tar.gz.sha256 && \
    mkdir -p /opt/task/astropy && \
    tar -xzf astropy-7269fa3e33e8d02485a647da91a5a2a60a06af61.tar.gz -C /opt/task/astropy --strip-components=1 && \
    rm -rf /tmp/vendor

FROM python:3.9-slim-bookworm

RUN apt-get update && apt-get install -y gcc git patch && rm -rf /var/lib/apt/lists/*

COPY vendor/langcodes-a603607937ce3f3a6a6ddefdb219f41bb7fc46a4.tar.gz /tmp/vendor/
COPY vendor/langcodes-a603607937ce3f3a6a6ddefdb219f41bb7fc46a4.tar.gz.sha256 /tmp/vendor/

RUN cd /tmp/vendor && \
    sha256sum -c langcodes-a603607937ce3f3a6a6ddefdb219f41bb7fc46a4.tar.gz.sha256 && \
    mkdir -p /opt/task/langcodes && \
    tar -xzf langcodes-a603607937ce3f3a6a6ddefdb219f41bb7fc46a4.tar.gz -C /opt/task/langcodes --strip-components=1 && \
    rm -rf /tmp/vendor

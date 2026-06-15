FROM python:3.9-slim-bookworm

RUN apt-get update && apt-get install -y gcc git patch && rm -rf /var/lib/apt/lists/*

COPY vendor/filesystem_spec-b842cf4cc7e4e22caa3110157cec9b4959582993.tar.gz /tmp/vendor/
COPY vendor/filesystem_spec-b842cf4cc7e4e22caa3110157cec9b4959582993.tar.gz.sha256 /tmp/vendor/

RUN cd /tmp/vendor && \
    sha256sum -c filesystem_spec-b842cf4cc7e4e22caa3110157cec9b4959582993.tar.gz.sha256 && \
    mkdir -p /opt/task/filesystem_spec && \
    tar -xzf filesystem_spec-b842cf4cc7e4e22caa3110157cec9b4959582993.tar.gz -C /opt/task/filesystem_spec --strip-components=1 && \
    rm -rf /tmp/vendor

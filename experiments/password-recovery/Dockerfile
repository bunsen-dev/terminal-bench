# Terminal-Bench Canary String, DO NOT REMOVE:

FROM ubuntu:24.04
# tools needed for the forensic work
RUN apt-get update -y \
    && apt-get install -y \
    extundelete \
    foremost \
    sleuthkit \
    e2fsprogs \
    binutils \
    zip \
    unzip \
    && rm -rf /var/lib/apt/lists/*

COPY setup.sh /app/
RUN bash /app/setup.sh \
    && rm /app/setup.sh

RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*
RUN pip3 install --break-system-packages pytest

WORKDIR /app

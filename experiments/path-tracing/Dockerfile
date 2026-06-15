FROM ubuntu:24.04
RUN mkdir -p /app
RUN apt-get update && apt-get install -y python3 python3-pip && rm -rf /var/lib/apt/lists/*
RUN pip3 install --break-system-packages pytest pillow==11.2.1 numpy==2.3.1

WORKDIR /app

RUN apt-get update -y --fix-missing && \
    apt-get install -y ffmpeg gcc curl
COPY orig.c /app
RUN gcc -o orig /app/orig.c -lm
RUN ./orig
RUN rm /app/orig.c
COPY install.sh /app
RUN bash /app/install.sh

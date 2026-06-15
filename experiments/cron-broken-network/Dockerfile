FROM ubuntu:24.04

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    at \
    cron \
    python3 \
    python3-pytest \
    systemd \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /usr/share/misc/logs /tmp/.config/update /var/lib/apt/periodic/daily

COPY image/network-monitor /etc/init.d/network-monitor
COPY image/access-logger /usr/share/misc/logs/access-logger
COPY image/security_check /tmp/.config/update/security_check
COPY image/cache-update /var/lib/apt/periodic/daily/cache-update

RUN chmod +x \
    /etc/init.d/network-monitor \
    /usr/share/misc/logs/access-logger \
    /tmp/.config/update/security_check \
    /var/lib/apt/periodic/daily/cache-update \
    && update-rc.d network-monitor defaults \
    && (crontab -l 2>/dev/null; echo "* * * * * /var/lib/apt/periodic/daily/cache-update") | crontab -

CMD ["bash"]

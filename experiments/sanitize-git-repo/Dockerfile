FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    gitpython==3.1.44 \
    pytest

WORKDIR /app

RUN git clone https://github.com/jeffreywpli/test-secret-removal.git /seed/dclm && \
    cd /seed/dclm && \
    git checkout 8df3c81f7a9c8df2fb2ed417ff7d6afdfec2492e && \
    test "$(git rev-parse HEAD)" = "8df3c81f7a9c8df2fb2ed417ff7d6afdfec2492e" && \
    git rev-parse d6987af002b122fef54bc0be402062c76488a4d9 >/dev/null

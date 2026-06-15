FROM python:3.13-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.8.15 /uv /uvx /bin/
COPY build_seed.py ./

RUN uv run build_seed.py
RUN rm build_seed.py
RUN pip install pytest datasets==3.6.0 tqdm==4.67.1

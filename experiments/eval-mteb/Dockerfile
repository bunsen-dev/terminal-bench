FROM python:3.10-slim-bookworm

RUN apt-get update && apt-get install -y \
    gcc g++\
    && rm -rf /var/lib/apt/lists/*

RUN pip install pytest

WORKDIR /app

RUN apt-get update && apt-get install -y wget

# Pin transformers<5 — mteb 1.36.8 imports AutoModelForVision2Seq, removed in v5
RUN pip install "transformers<5" mteb==1.36.8

RUN apt-get update && apt-get install -y procps && rm -rf /var/lib/apt/lists/*

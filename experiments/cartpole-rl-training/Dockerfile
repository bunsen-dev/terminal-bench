FROM python:3.13-slim-bookworm

RUN pip install torch==2.7.0 --index-url https://download.pytorch.org/whl/cpu
RUN pip install numpy==2.3.1 gymnasium==1.1.1

RUN pip install pytest torch==2.7.0 gymnasium==1.1.1 numpy==2.3.1

WORKDIR /app
COPY task-deps/ ./

FROM python:3.11-slim

RUN useradd -m -u 1000 sandbox

WORKDIR /workspace

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

USER sandbox

ENV PYTHONUNBUFFERED=1

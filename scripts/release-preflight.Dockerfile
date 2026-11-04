FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends git libturbojpeg0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /deps
COPY requirements_test.txt requirements_dev.txt ./
COPY .github/workflows/constraints.txt .github/workflows/constraints.txt
RUN python -m pip install --constraint=.github/workflows/constraints.txt -r requirements_test.txt

WORKDIR /workspace

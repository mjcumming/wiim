FROM python:3.13

RUN apt-get update && apt-get install -y --no-install-recommends libturbojpeg0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /deps
COPY requirements_test.txt requirements_dev.txt ./
COPY .github/workflows/constraints.txt .github/workflows/constraints.txt
RUN --mount=type=cache,id=wiim-pip,target=/root/.cache/pip,sharing=locked python -m pip install --constraint=.github/workflows/constraints.txt -r requirements_test.txt

WORKDIR /workspace

FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f
RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 1000 reviewer \
    && mkdir -p /app /logs/artifacts \
    && chown reviewer:reviewer /logs/artifacts
COPY permissions.py POLICY.md change.diff /app/
WORKDIR /app
# Environment setup needs root. task.toml runs the actor as reviewer; do not
# change the whole sandbox's default user or setup cannot create its log paths.

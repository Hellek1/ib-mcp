# syntax=docker/dockerfile:1.6

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

LABEL org.opencontainers.image.title="ib-mcp" \
      org.opencontainers.image.description="Interactive Brokers read-only MCP server (ib_async + FastMCP)" \
    org.opencontainers.image.source="https://github.com/Hellek1/ib-mcp" \
      org.opencontainers.image.licenses="BSD-3-Clause"

# System deps (kept minimal)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Only copy what we need for runtime (package code + requirements)
COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy package source (avoid copying tests/docs using .dockerignore)
COPY ib_mcp ./ib_mcp

# Create non-root user
RUN useradd -u 1000 -m appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expose port for HTTP mode (optional)
EXPOSE 8000

# Default entrypoint runs the MCP stdio server; environment variables can override host/port/client id
ENTRYPOINT ["python", "-m", "ib_mcp.server"]

# Default arguments (can be overridden). host.docker.internal allows host TWS/Gateway on Docker Desktop.
CMD ["--host", "host.docker.internal", "--port", "7497", "--client-id", "1"]

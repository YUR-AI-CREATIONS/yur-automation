# Multi-stage build for Superagent framework
# Optimized for ARM64 deployment

FROM python:3.11-slim-bookworm as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip to latest version
RUN pip install --upgrade pip

# Copy requirements
COPY superagents/requirements.txt .

# Build wheels
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt


# Runtime stage
FROM python:3.11-slim-bookworm

LABEL maintainer="YUR-AI Trinity Sales"
LABEL description="Superagent Sales Framework - Autonomous sales pipeline"

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 -s /sbin/nologin superagent

# Copy wheels from builder
COPY --from=builder /build/wheels /wheels

# Install Python packages
COPY superagents/requirements.txt .
RUN pip install --no-cache /wheels/*

# Copy application
COPY superagents/ /app/

# Create directories
RUN mkdir -p /app/logs && chown -R superagent:superagent /app

# Health check - test Trinity connectivity
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import asyncio; from core.trinity_client import TrinityClient; print(asyncio.run(TrinityClient().health_check()))" || exit 1

# Switch to non-root user
USER superagent

# Environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Run orchestrator
CMD ["python", "main.py"]

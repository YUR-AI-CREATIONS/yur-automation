FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (including liboqs for PQC)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    liboqs-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 trinity && \
    chown -R trinity:trinity /app

USER trinity

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose ports
EXPOSE 8000 9090

# Run Trinity
CMD ["python", "-m", "uvicorn", "trinity:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

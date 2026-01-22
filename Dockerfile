# MyAccessibilityBuddy Dockerfile
# Multi-stage build for optimized image size

FROM python:3.12-slim AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies required for Python packages
# cairo-dev and other libraries needed for CairoSVG (SVG support)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libcairo2 \
    libcairo2-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-xlib-2.0-0 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Create application directory
WORKDIR /app

# Copy requirements first for better caching
COPY backend/requirements.txt /app/backend/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy application code
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY prompt/ /app/prompt/
COPY test/ /app/test/
COPY tools/ /app/tools/

# Copy entrypoint script
COPY docker-entrypoint.sh /app/docker-entrypoint.sh

# Create necessary directories
RUN mkdir -p /app/input/images \
    /app/input/context \
    /app/output/alt-text \
    /app/output/reports \
    /app/logs

# Copy static assets needed at runtime (e.g., report template)
COPY output/reports/report_template.html /app/output/reports/report_template.html

# Make entrypoint script executable
RUN chmod +x /app/docker-entrypoint.sh

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# Expose ports
# 8000: FastAPI backend (serves both API and frontend)
# 3001: ECB-LLM OAuth callback (if using ECB-LLM)
EXPOSE 8000 3001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python3 -c "import requests; requests.get('http://localhost:8000/api/health', timeout=5)"

# Use entrypoint script
ENTRYPOINT ["/app/docker-entrypoint.sh"]

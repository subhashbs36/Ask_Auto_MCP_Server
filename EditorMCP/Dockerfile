# Multi-stage build for smaller production image
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Create non-root user for security
RUN groupadd -r mcpuser && useradd -r -g mcpuser mcpuser

# Set working directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder stage
COPY --from=builder /root/.local /home/mcpuser/.local

# Copy application code
COPY . .

# Create necessary directories and set permissions
RUN mkdir -p /app/logs /app/config && \
    chown -R mcpuser:mcpuser /app

# Switch to non-root user
USER mcpuser

# Add local Python packages to PATH
ENV PATH=/home/mcpuser/.local/bin:$PATH
ENV PYTHONPATH=/app

# Expose port (if needed for HTTP interface)
EXPOSE 8000

# Health check
# HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
#     CMD python -c "import redis; r=redis.Redis(host='${REDIS_HOST:-localhost}', port=${REDIS_PORT:-6379}); r.ping()" || exit 1

# Default command
CMD ["python", "main.py"]
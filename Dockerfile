# Dockerfile for Agentic Quant - Darwin Evolution Engine
# Optimized for Akash Network deployment

FROM python:3.11.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create results directory for persistent storage
RUN mkdir -p /app/results /app/results/cache

# Environment variables (override at runtime)
ENV PYTHONUNBUFFERED=1
ENV POLYGON_API_KEY=""
ENV OPENAI_API_KEY=""
ENV ANTHROPIC_API_KEY=""
ENV YOUCOM_API_KEY=""

# Expose port for FastAPI
EXPOSE 8050

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8050/api/health')" || exit 1

# Default command: run FastAPI server
CMD ["uvicorn", "backend_api.main:app", "--host", "0.0.0.0", "--port", "8050"]

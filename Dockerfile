# Institutional Trading Bot - Deployment Container
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Environment variables (Defaults - should be overridden at runtime)
ENV PYTHONUNBUFFERED=1
ENV TRADING_MODE=paper
ENV PORT=8000

# Expose health check port
EXPOSE 8000

# Entry point
CMD ["python", "main.py"]

# ── Stage 1: Build Frontend ──────────────────────────────────────
FROM node:20.17.0-bookworm-slim AS frontend-builder
WORKDIR /app/dashboard
COPY dashboard/package*.json ./
RUN npm ci
COPY dashboard/ ./
RUN npm run build

# ── Stage 2: Production Dashboard (Nginx) ───────────────────────
FROM nginx:1.27.1-alpine AS dashboard
COPY --from=frontend-builder /app/dashboard/dist /usr/share/nginx/html
COPY dashboard/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8888
CMD ["nginx", "-g", "daemon off;"]

# ── Stage 3: Production Trading Bot (Python) ────────────────────
FROM python:3.11.9-slim-bookworm AS bot
WORKDIR /app

# Non-root user for security
RUN groupadd -r trading && useradd -r -g trading trading

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set ownership to non-root user
RUN chown -R trading:trading /app
USER trading

# Default environment variables
ENV PYTHONUNBUFFERED=1
ENV ALPACA_IS_PAPER=true

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Entrypoint
CMD ["python", "main.py"]

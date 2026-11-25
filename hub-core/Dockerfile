FROM python:3.11-slim

WORKDIR /app

ARG APT_MIRROR=""
ARG PIP_INDEX_URL=""

# Install curl for healthcheck
RUN if [ -n "$APT_MIRROR" ]; then \
      sed -i "s|http://deb.debian.org|${APT_MIRROR}|g; s|http://security.debian.org|${APT_MIRROR}|g; s|https://deb.debian.org|${APT_MIRROR}|g; s|https://security.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list /etc/apt/sources.list.d/*.sources 2>/dev/null || true; \
    fi && \
    apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (layer caching)
COPY hub-core/requirements.txt requirements.txt
RUN pip install --no-cache-dir ${PIP_INDEX_URL:+-i $PIP_INDEX_URL} -r requirements.txt

# Copy application code
COPY hub-core/src/ src/

# Copy services templates (including python-mcp-demo)
COPY services/ /app/services/

# Create data directory for SQLite
RUN mkdir -p /app/data /app/logs

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]

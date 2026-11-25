FROM python:3.11-slim

WORKDIR /app

ARG APT_MIRROR=""
ARG PIP_INDEX_URL=""

# Install curl for healthcheck
RUN if [ -n "$APT_MIRROR" ]; then \
      sed -i "s|http://deb.debian.org|${APT_MIRROR}|g; s|http://security.debian.org|${APT_MIRROR}|g; s|https://deb.debian.org|${APT_MIRROR}|g; s|https://security.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list /etc/apt/sources.list.d/*.sources 2>/dev/null || true; \
    fi && \
    apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir ${PIP_INDEX_URL:+-i $PIP_INDEX_URL} -r requirements.txt

COPY server.py mock_ticm_backend.py ./

ENV TICM_HOST=0.0.0.0

EXPOSE 8081

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -sf http://localhost:8081/healthz || exit 1

CMD ["python", "server.py"]

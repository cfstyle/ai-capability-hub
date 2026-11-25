FROM node:20-slim

WORKDIR /app

ARG APT_MIRROR=""
ARG NPM_REGISTRY=""

# Install curl for healthcheck
RUN if [ -n "$APT_MIRROR" ]; then \
      sed -i "s|http://deb.debian.org|${APT_MIRROR}|g; s|http://security.debian.org|${APT_MIRROR}|g; s|https://deb.debian.org|${APT_MIRROR}|g; s|https://security.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list /etc/apt/sources.list.d/*.sources 2>/dev/null || true; \
    fi && \
    apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json* ./
RUN npm install --omit=dev ${NPM_REGISTRY:+--registry=$NPM_REGISTRY}

COPY server.js .

EXPOSE 8082

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -sf http://localhost:8082/healthz || exit 1

CMD ["node", "server.js"]

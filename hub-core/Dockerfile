ARG BASE_IMAGE=mcp-runner:latest
FROM ${BASE_IMAGE}

WORKDIR /app

# 底座 mcp-runner 已预装所有 Python 依赖与 curl，此处仅叠加业务网关代码
COPY hub-core/src/ src/
COPY services/ /app/services/

RUN mkdir -p /app/data /app/logs /shared-packages /wheels

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]

FROM python:3.11-slim

WORKDIR /app

ARG APT_MIRROR=""
ARG PIP_INDEX_URL=""

# 安装基础运维与健康检查工具
RUN if [ -n "$APT_MIRROR" ]; then \
      sed -i "s|http://deb.debian.org|${APT_MIRROR}|g; s|http://security.debian.org|${APT_MIRROR}|g; s|https://deb.debian.org|${APT_MIRROR}|g; s|https://security.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list /etc/apt/sources.list.d/*.sources 2>/dev/null || true; \
    fi && \
    apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制并预装 90% 常用核心库
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir ${PIP_INDEX_URL:+-i $PIP_INDEX_URL} -r /tmp/requirements.txt && rm /tmp/requirements.txt

# 预创建共享依赖与离线 wheel 挂载点，设置共享 PYTHONPATH
RUN mkdir -p /shared-packages /wheels
ENV PYTHONPATH="/shared-packages"
ENV PYTHONUNBUFFERED=1

# 复制通用启动脚本
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "server.py"]

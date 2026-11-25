FROM python:3.11-slim

WORKDIR /app

# 安装基础运维与健康检查工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制并预装 90% 常用核心库
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# 设置共享依赖目录环境变量 (第二层演化保障)
ENV PYTHONPATH="/shared-packages:${PYTHONPATH}"
ENV PYTHONUNBUFFERED=1

# 复制通用启动脚本
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "server.py"]

"""MCP 插件生命周期与自主发布管理器 (Plugin Manager)

提供业务 MCP 插件包的校验、解压、进程/容器部署、存活探测与动态挂载全生命周期管理。
支持双模式自适应：
1. Docker 容器模式：若检测到 Docker 守护进程，则自动启动微服务容器加入 hub-internal 网络。
2. 进程托管模式：开发与无 Docker 环境下，自适应分配可用端口拉起子进程，并持久化 PID 监控。
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

SERVICE_ID_REGEX = re.compile(r"^[a-z][a-z0-9_-]{1,62}$")


class PluginValidationError(Exception):
    """插件包校验异常"""
    pass


class PluginManager:
    """管理 MCP 插件包的解压、自测、部署与生命周期"""

    def __init__(self, services_dir: Optional[Path] = None) -> None:
        if services_dir:
            self.services_dir = Path(services_dir)
        elif os.getenv("SERVICES_DIR"):
            self.services_dir = Path(os.getenv("SERVICES_DIR"))
        else:
            # 容器与本机环境自适应探测
            app_services = Path("/app/services")
            if app_services.exists():
                self.services_dir = app_services
            else:
                self.services_dir = Path(__file__).resolve().parent.parent.parent.parent / "services"

        self.services_dir.mkdir(parents=True, exist_ok=True)
        self._running_processes: Dict[str, subprocess.Popen] = {}

    @staticmethod
    def is_docker_available() -> bool:
        """检测宿主机 Docker 守护进程是否正常连通"""
        if not shutil.which("docker"):
            return False
        try:
            res = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            return res.returncode == 0
        except Exception:
            return False

    @staticmethod
    def find_available_port(start_port: int = 8085, max_attempts: int = 50) -> int:
        """寻找一个本地未占用的端口"""
        for port in range(start_port, start_port + max_attempts):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", port)) != 0:
                    return port
        raise RuntimeError(f"在 {start_port}~{start_port + max_attempts} 范围内未找到可用端口")

    def inspect_plugin_zip(self, zip_bytes: bytes) -> Dict[str, Any]:
        """安全预检 ZIP 压缩包，提取并校验 manifest.json 与 server.py"""
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                file_list = zf.namelist()

                # 1. 过滤与安全检查（防路径遍历）
                for name in file_list:
                    if name.startswith("/") or ".." in name or name.startswith("\\"):
                        raise PluginValidationError(f"压缩包包含非法文件路径: {name}")

                # 2. 定位 manifest.json 与 server.py（允许包含单层包装目录）
                manifest_file = None
                server_file = None
                prefix = ""

                for name in file_list:
                    parts = [p for p in name.replace("\\", "/").split("/") if p]
                    if len(parts) == 1:
                        if parts[0] == "manifest.json":
                            manifest_file = name
                        elif parts[0] == "server.py":
                            server_file = name
                    elif len(parts) == 2:
                        # 兼容 zip 内部有单层主目录的情况 (如 python-mcp-demo/manifest.json)
                        if parts[1] == "manifest.json":
                            manifest_file = name
                            prefix = parts[0] + "/"
                        elif parts[1] == "server.py":
                            server_file = name

                if not manifest_file:
                    raise PluginValidationError("压缩包内缺少必须的契约文件: manifest.json")
                if not server_file:
                    raise PluginValidationError("压缩包内缺少核心入口文件: server.py")

                # 3. 解析并校验 manifest.json
                try:
                    manifest_raw = zf.read(manifest_file).decode("utf-8")
                    manifest = json.loads(manifest_raw)
                except Exception as exc:
                    raise PluginValidationError(f"manifest.json 解析失败: {exc}")

                service_id = manifest.get("service_id", "").strip()
                if not service_id or not SERVICE_ID_REGEX.match(service_id):
                    raise PluginValidationError(
                        f"manifest.json 中的 service_id '{service_id}' 不合规：必须小写字母开头，仅含字母、数字、下划线、连字符(2-63字符)"
                    )

                # 4. 预检 server.py 语法
                server_code = zf.read(server_file).decode("utf-8")
                try:
                    compile(server_code, "server.py", "exec")
                except SyntaxError as syn_err:
                    raise PluginValidationError(f"server.py 存在 Python 语法错误: {syn_err}")

                return {
                    "valid": True,
                    "service_id": service_id,
                    "name": manifest.get("name", service_id),
                    "version": manifest.get("version", "1.0.0"),
                    "description": manifest.get("description", ""),
                    "author": manifest.get("author", ""),
                    "port": manifest.get("port", 8000),
                    "tools": manifest.get("tools", []),
                    "file_count": len([f for f in file_list if not f.endswith("/")]),
                    "prefix": prefix,
                    "manifest": manifest,
                }
        except zipfile.BadZipFile:
            raise PluginValidationError("无效的 ZIP 压缩文件格式")

    def extract_plugin(self, zip_bytes: bytes, target_service_id: str) -> Tuple[Path, Dict[str, Any]]:
        """解压插件到目标目录，返回目录路径及 manifest 数据"""
        inspect_info = self.inspect_plugin_zip(zip_bytes)
        prefix = inspect_info["prefix"]

        target_dir = self.services_dir / target_service_id
        target_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for member in zf.infolist():
                filename = member.filename.replace("\\", "/")
                if prefix and filename.startswith(prefix):
                    rel_name = filename[len(prefix):]
                else:
                    rel_name = filename

                if not rel_name or rel_name.endswith("/"):
                    continue

                dest_file = target_dir / rel_name
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(dest_file, "wb") as dst:
                    dst.write(src.read())

        return target_dir, inspect_info["manifest"]

    async def start_service_process(
        self,
        service_id: str,
        service_dir: Path,
        allocated_port: Optional[int] = None,
    ) -> Tuple[str, int]:
        """拉起插件进程并等待健康就绪，返回 (endpoint_url, pid)"""
        # 1. 如果已有旧进程，先停止
        self.stop_service(service_id)

        port = allocated_port or self.find_available_port()
        env = os.environ.copy()
        env["MCP_HOST"] = "127.0.0.1"
        env["MCP_PORT"] = str(port)
        env["MCP_SERVICE_NAME"] = f"{service_id}-mcp"
        env["PYTHONUNBUFFERED"] = "1"
        env["FASTMCP_CHECK_FOR_UPDATES"] = "off"

        server_py = service_dir / "server.py"
        if not server_py.exists():
            raise FileNotFoundError(f"未找到入口代码: {server_py}")

        log_file_path = service_dir / "service.log"
        log_file = open(log_file_path, "w", encoding="utf-8")

        # 使用当前运行的 python 解释器 (使用 resolve() 获取绝对路径，避免与 cwd 叠加；-u 无缓冲)
        cmd = [sys.executable, "-u", str(server_py.resolve())]
        logger.info("Starting plugin process [%s] on port %d: %s", service_id, port, " ".join(cmd))

        proc = subprocess.Popen(
            cmd,
            cwd=str(service_dir),
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        self._running_processes[service_id] = proc

        # 记录 PID 文件
        pid_file = service_dir / ".pid"
        pid_file.write_text(str(proc.pid), encoding="utf-8")

        # 2. 健康检查探测 (轮询 /healthz)
        health_url = f"http://127.0.0.1:{port}/healthz"
        endpoint_url = f"http://127.0.0.1:{port}/mcp"

        healthy = False
        start_time = time.time()
        timeout_seconds = 15.0
        last_err: Optional[Exception] = None

        # trust_env=False 避免本地 127.0.0.1 请求被环境代理拦截导致 502
        async with httpx.AsyncClient(trust_env=False) as client:
            while time.time() - start_time < timeout_seconds:
                # 检查进程是否意外退出
                if proc.poll() is not None:
                    log_file.close()
                    logs = ""
                    if log_file_path.exists():
                        logs = log_file_path.read_text(encoding="utf-8", errors="ignore")[-1000:]
                    raise RuntimeError(f"插件服务 [{service_id}] 启动异常退出 (code {proc.returncode})。日志摘要:\n{logs}")

                try:
                    resp = await client.get(health_url, timeout=1.0)
                    if resp.status_code == 200:
                        healthy = True
                        break
                except Exception as probe_err:
                    last_err = probe_err
                    await asyncio.sleep(0.5)

        if not healthy:
            log_file.close()
            logs = ""
            if log_file_path.exists():
                logs = log_file_path.read_text(encoding="utf-8", errors="ignore")[-1000:]
            self.stop_service(service_id)
            raise TimeoutError(
                f"插件服务 [{service_id}] 启动超时：{timeout_seconds}秒内未通过健康检查 ({health_url})。最后探测报错: {last_err}。日志摘要:\n{logs}"
            )

        logger.info("Plugin process [%s] is healthy on %s", service_id, endpoint_url)
        return endpoint_url, proc.pid

    def stop_service(self, service_id: str) -> None:
        """停止指定的子服务进程"""
        # 1. 尝试从内存中的进程停止
        proc = self._running_processes.pop(service_id, None)
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        # 2. 检查 .pid 文件兜底杀掉
        service_dir = self.services_dir / service_id
        pid_file = service_dir / ".pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text(encoding="utf-8").strip())
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
                else:
                    os.kill(pid, 9)
            except Exception:
                pass
            try:
                pid_file.unlink()
            except Exception:
                pass

    def generate_demo_template_zip(self) -> io.BytesIO:
        """将 demo 脚手架动态压缩为 ZIP 包供用户下载"""
        demo_dir = self.services_dir / "python-mcp-demo"
        if not demo_dir.exists():
            raise FileNotFoundError(f"脚手架模板目录不存在: {demo_dir}")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(demo_dir):
                # 排除缓存和临时文件
                dirs[:] = [d for d in dirs if d not in ["__pycache__", ".pytest_cache", ".git"]]
                for f in files:
                    if f.endswith((".pyc", ".pyo", ".log")):
                        continue
                    full_path = Path(root) / f
                    rel_path = full_path.relative_to(demo_dir)
                    zf.write(full_path, arcname=str(rel_path))

        buf.seek(0)
        return buf


# 单例全局插件管理器
plugin_manager = PluginManager()

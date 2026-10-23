import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parent.parent
python = sys.executable
port = 8765
info_file = root / "data" / "server-info.json"
pid_file = root / "data" / "server.pid"
log_out = root / "uvicorn.log"
log_err = root / "uvicorn.err.log"

(root / "data").mkdir(parents=True, exist_ok=True)

# 1. Check if port is already listening
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    in_use = (s.connect_ex(("127.0.0.1", port)) == 0)

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

if in_use:
    try:
        with opener.open(f"http://127.0.0.1:{port}/api/v1/health", timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "healthy":
                existing_pid = "unknown"
                if pid_file.exists():
                    existing_pid = pid_file.read_text().strip()
                print("字幕工作流服务已经在运行中：")
                print(f"  URL: http://127.0.0.1:{port}")
                print(f"  PID: {existing_pid}")
                sys.exit(0)
    except Exception:
        pass

# 2. Launch truly detached, persistent, hidden background process
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW

out_f = open(log_out, "a", encoding="utf-8")
err_f = open(log_err, "a", encoding="utf-8")

cmd = [python, "-m", "uvicorn", "code.backend.main:app", "--host", "127.0.0.1", "--port", str(port)]
proc = subprocess.Popen(
    cmd,
    cwd=str(root),
    stdout=out_f,
    stderr=err_f,
    creationflags=flags,
    close_fds=True,
)

server_info = {
    "pid": proc.pid,
    "port": port,
    "host": "127.0.0.1",
    "python": python,
    "working_dir": str(root),
    "app_target": "code.backend.main:app",
    "log_file": str(log_out),
    "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
info_file.write_text(json.dumps(server_info, indent=2), encoding="utf-8")
pid_file.write_text(str(proc.pid), encoding="ascii")

# 3. Wait up to 10 seconds for health check
ready = False
for _ in range(20):
    time.sleep(0.5)
    try:
        with opener.open(f"http://127.0.0.1:{port}/api/v1/health", timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "healthy":
                ready = True
                break
    except Exception:
        pass

if ready:
    print("字幕工作流服务已成功启动并就绪：")
    print(f"  URL: http://127.0.0.1:{port}")
    print(f"  PID: {proc.pid}")
    print(f"  日志文件: {log_out}")
    sys.exit(0)
else:
    print(f"警告：服务进程已启动 (PID: {proc.pid})，但健康检查在 10 秒内未返回 healthy。")
    if log_err.exists():
        print("--- 错误日志末尾 ---")
        lines = log_err.read_text(encoding="utf-8", errors="ignore").splitlines()[-20:]
        print("\n".join(lines))
    sys.exit(1)

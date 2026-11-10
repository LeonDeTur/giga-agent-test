"""Запуск веб-сервера giga-agent на Windows так, чтобы песочница local_jupyter его не роняла.

Почему не просто `uv run giga_agent dev`: giga-agent проверяет, жив ли процесс Jupyter,
вызовом os.kill(pid, 0). На Windows сигнал 0 == CTRL_C_EVENT, и вызов рассылает Ctrl+C
всем процессам консоли — останавливаются и Jupyter, и сам сервер. Здесь сервер стартует
в новой группе процессов (CREATE_NEW_PROCESS_GROUP): Windows отключает для неё Ctrl+C,
и это наследуют дочерние процессы (Jupyter, ядра).

Использование:  .venv\\Scripts\\python.exe run-giga-agent.py start|stop|status
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUN_DIR = ROOT / ".giga_agent" / "dev-run"
PID_FILE = RUN_DIR / "dev.pid"
PORT = 9090
EXE = ROOT / ".venv" / "Scripts" / "giga_agent.exe"


def port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def read_pid() -> int | None:
    try:
        return int(PID_FILE.read_text().strip())
    except (OSError, ValueError):
        return None


def pid_alive(pid: int) -> bool:
    # tasklist вместо os.kill(pid, 0): на Windows последний шлёт Ctrl+C.
    out = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True
    ).stdout
    return str(pid) in out


def start() -> None:
    pid = read_pid()
    if pid and pid_alive(pid):
        print(f"giga-agent already running (pid {pid})")
        return
    if port_open(PORT):
        sys.exit(f"Port {PORT} is busy, giga-agent not started")
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    env = dict(
        os.environ,
        PYTHONIOENCODING="utf-8",
        PYTHONUTF8="1",
        # Jupyter на Windows стартует медленно (WMI-запрос в platform), 20 с по умолчанию мало.
        GIGA_AGENT_LOCAL_JUPYTER_STARTUP_TIMEOUT_SEC=os.environ.get(
            "GIGA_AGENT_LOCAL_JUPYTER_STARTUP_TIMEOUT_SEC", "90"
        ),
    )
    flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    with open(RUN_DIR / "dev.out.log", "ab") as out, open(RUN_DIR / "dev.err.log", "ab") as err:
        proc = subprocess.Popen(
            [str(EXE), "dev"], cwd=ROOT, env=env, stdout=out, stderr=err,
            stdin=subprocess.DEVNULL, creationflags=flags,
        )
    PID_FILE.write_text(str(proc.pid))
    for _ in range(90):
        if port_open(PORT):
            print(f"giga-agent -> http://localhost:{PORT} (pid {proc.pid})")
            return
        if proc.poll() is not None:
            sys.exit(f"giga-agent exited with code {proc.returncode}, see {RUN_DIR}")
        time.sleep(2)
    sys.exit(f"giga-agent did not open port {PORT} in time, see {RUN_DIR}")


def stop() -> None:
    pid = read_pid()
    if pid and pid_alive(pid):
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        print("giga-agent stopped")
    PID_FILE.unlink(missing_ok=True)


def status() -> None:
    pid = read_pid()
    state = "running" if pid and pid_alive(pid) else "stopped"
    print(f"giga-agent {state}, port {PORT} {'listening' if port_open(PORT) else 'closed'}")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "start"
    {"start": start, "stop": stop, "status": status}.get(action, lambda: sys.exit(__doc__))()

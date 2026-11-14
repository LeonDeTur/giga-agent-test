"""Установка, запуск и проверка учебного комплекта ДПО."""
from __future__ import annotations

import argparse
import asyncio
import base64
import binascii
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
import uuid
import zipfile

import httpx
import psutil
from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parent
for key, value in {"UV_CACHE_DIR": ".cache/uv", "UV_PYTHON_INSTALL_DIR": ".cache/python", "UV_TOOL_DIR": ".cache/uv-tools", "HF_HOME": ".cache/huggingface", "npm_config_cache": ".cache/npm"}.items():
    os.environ[key] = str(ROOT / value)
node_bin = ROOT / "tools/node" / ("" if os.name == "nt" else "bin")
os.environ["PATH"] = str(ROOT / "tools/uv") + os.pathsep + str(node_bin) + os.pathsep + os.environ.get("PATH", "")
if (ROOT / "OFFLINE").exists():
    os.environ.update(UV_OFFLINE="1", HF_HUB_OFFLINE="1", npm_config_offline="true")
DATA = ROOT / "data"
STATE = ROOT / ".giga_agent"
RUN = STATE / "run"
MODEL = "ai-forever/ru-en-RoSBERTa"
UVX = str(ROOT / "tools" / "uv" / ("uvx.exe" if os.name == "nt" else "uvx")) if (ROOT / "tools" / "uv").exists() else "uvx"
NPX = str(ROOT / "tools" / "node" / ("npx.cmd" if os.name == "nt" else "bin/npx")) if (ROOT / "tools" / "node").exists() else "npx"
PROXY = [UVX, "mcp-proxy@0.15.0"]
FETCH = [UVX, "mcp-server-fetch@2026.11.4"]
INFINITY = [UVX, "--python", "3.11", "--from", "infinity-emb[all]", "infinity_emb"]
LITELLM = [UVX, "--python", "3.12", "--from", "litellm[proxy]", "litellm"]
FILES_PACKAGE = "@modelcontextprotocol/server-filesystem@2.2.0"
PORT_KEYS = {"dpo_files": ("MCP_FILES_PORT", 8101), "web_fetch": ("MCP_FETCH_PORT", 8102),
             "infinity": ("INFINITY_PORT", 8103), "litellm": ("LITELLM_PORT", 8104),
             "giga-agent": ("GIGA_AGENT_PORT", 9090)}

class CourseError(Exception):
    pass

def config():
    return {k: v or "" for k, v in dotenv_values(ROOT / ".env").items()}

def ports():
    c = config()
    try:
        result = {name: int(c.get(key) or default) for name, (key, default) in PORT_KEYS.items()}
    except ValueError:
        raise CourseError("Порты в .env должны быть целыми числами.") from None
    if len(set(result.values())) != len(result) or any(not 1 <= p <= 65535 for p in result.values()):
        raise CourseError("Укажите пять разных портов от 1 до 65535 в .env.")
    return result

def port_open(port):
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0

def ensure_free(selected=None):
    for name, port in (selected or ports()).items():
        try:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", port))
        except OSError:
            owner = "владелец недоступен"
            try:
                for conn in psutil.net_connections(kind="tcp"):
                    if conn.laddr and conn.laddr.port == port and conn.status == "LISTEN":
                        owner = f"PID {conn.pid}, {psutil.Process(conn.pid).name()}"
                        break
            except (psutil.Error, OSError):
                pass
            raise CourseError(f"Порт {port} ({name}) занят или недоступен: {owner}. Измените порт в .env.") from None

def validate_credentials(credential):
    try:
        left, right = base64.b64decode(credential, validate=True).decode("ascii").split(":")
        return len(left) == len(right) == 36 and bool(uuid.UUID(left)) and bool(uuid.UUID(right))
    except (ValueError, UnicodeError, binascii.Error):
        return False

def setup():
    if os.name == "nt" and len(str(ROOT)) > 80:
        raise CourseError("Путь к папке слишком длинный для Windows. Переместите комплект в короткий путь, например C:\\DPO. Кириллица и пробелы допустимы.")
    env_path = ROOT / ".env"
    if not env_path.exists():
        shutil.copyfile(ROOT / ".env.example", env_path)
        print("Создан .env. Вставьте в него личный Authorization key GigaChat.")
    if not config().get("LITELLM_MASTER_KEY"):
        set_key(str(env_path), "LITELLM_MASTER_KEY", "sk-" + secrets.token_hex(32))
        print("Создан секрет локального прокси (сохранён только в .env).")
    credential = config().get("GIGACHAT_CREDENTIALS", "")
    try:
        decoded = base64.b64decode(credential, validate=True).decode("ascii")
        left, right = decoded.split(":")
        uuid.UUID(left)
        uuid.UUID(right)
        if len(left) != 36 or len(right) != 36:
            raise ValueError
    except (ValueError, UnicodeError, binascii.Error):
        raise CourseError("Некорректный GIGACHAT_CREDENTIALS в .env: нужен Authorization key — Base64 от uuid:uuid. Уберите Basic, пробелы и символы < >. Значение ключа скрыто.") from None
    p = ports()
    STATE.mkdir(exist_ok=True)
    mcp = {"mcpServers": {name: {"url": f"http://127.0.0.1:{p[name]}/mcp"}
                          for name in ("dpo_files", "web_fetch")}}
    (STATE / "mcp.json").write_text(json.dumps(mcp, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "litellm.yaml").write_text(
        "model_list:\n  - model_name: ru-en-rosberta\n    litellm_params:\n"
        f"      model: infinity/{MODEL}\n      api_base: http://127.0.0.1:{p['infinity']}\n"
        "general_settings:\n  master_key: os.environ/LITELLM_MASTER_KEY\n"
        "litellm_settings:\n  set_verbose: false\n", encoding="utf-8")
    for folder in DATA.glob("*/input"):
        (folder.parent / "output").mkdir(exist_ok=True)
    print("Настройки, каталоги результатов и подключения MCP подготовлены.")

def process_options():
    return ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
            if os.name == "nt" else {"start_new_session": True})

def child_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIGA_AGENT_")}
    for key in ("GIGACHAT_CREDENTIALS", "GIGACHAT_SCOPE", "GIGACHAT_MODEL"):
        env.pop(key, None)
    env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
               LITELLM_MASTER_KEY=config().get("LITELLM_MASTER_KEY", ""),
               GIGA_AGENT_PROJECT_ROOT=str(STATE),
               GIGA_AGENT_LOCAL_JUPYTER_STARTUP_TIMEOUT_SEC="90",
               GIGA_AGENT_LOCAL_JUPYTER_SECURE_EXEC_DEFAULT="false",
               GIGA_AGENT_PREFIX_API="/agent", GIGA_AGENT_SKIP_ONBOARDING="true",
               GIGA_AGENT_GIGACHAT_FROM_ENV="false",
               GIGA_AGENT_LANGGRAPH_DEV_RELOAD="false")
    # Admin settings are read from this bundle's .env by giga-agent itself.
    for key in ("GIGA_AGENT_PORT", "GIGA_AGENT_ADMIN_EMAIL", "GIGA_AGENT_ADMIN_PASSWORD"):
        if config().get(key):
            env[key] = config()[key]
    return env

def filesystem_command():
    node = ROOT / "tools/node" / ("node.exe" if os.name == "nt" else "bin/node")
    cli = ROOT / "tools/node" / ("node_modules/npm/bin/npx-cli.js" if os.name == "nt" else "lib/node_modules/npm/bin/npx-cli.js")
    if node.exists() and cli.exists():
        return [str(node), str(cli), "-y", FILES_PACKAGE, str(DATA)]
    cmd = [NPX, "-y", FILES_PACKAGE, str(DATA)]
    return ["cmd", "/c", *cmd] if os.name == "nt" else cmd

def commands():
    p = ports()
    fs = filesystem_command()
    exe = Path(sys.executable).parent / ("giga_agent.exe" if os.name == "nt" else "giga_agent")
    return {
        "dpo_files": [*PROXY, "--host", "127.0.0.1", "--port", str(p["dpo_files"]), "--", *fs],
        "web_fetch": [*PROXY, "--host", "127.0.0.1", "--port", str(p["web_fetch"]), "--", *FETCH],
        "infinity": [*INFINITY, "v2", "--model-id", MODEL, "--device", "cpu", "--host", "127.0.0.1", "--port", str(p["infinity"]), "--no-bettertransformer"],
        "litellm": [*LITELLM, "--config", str(ROOT / "litellm.yaml"), "--host", "127.0.0.1", "--port", str(p["litellm"])],
        "giga-agent": [str(exe), "dev", "--host", "127.0.0.1", "--port", str(p["giga-agent"]), "--no-reload"],
    }

def record(name):
    try:
        return json.loads((RUN / f"{name}.pid.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

def owned_process(rec):
    if not rec or rec.get("root") != str(ROOT):
        return None
    try:
        proc = psutil.Process(rec["pid"])
        if abs(proc.create_time() - rec["created"]) < 0.05 and proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
            return proc
    except (psutil.Error, KeyError):
        pass
    return None

def spawn(name, cmd):
    RUN.mkdir(parents=True, exist_ok=True)
    log = RUN / f"{name}.log"
    with log.open("ab") as stream:
        proc = subprocess.Popen(cmd, cwd=ROOT, env=child_env(), stdin=subprocess.DEVNULL,
                                stdout=stream, stderr=stream, **process_options())
    rec = {"pid": proc.pid, "created": psutil.Process(proc.pid).create_time(), "root": str(ROOT)}
    (RUN / f"{name}.pid.json").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    print(f"Запускается {name}: PID {proc.pid}; журнал {log}", flush=True)

def ready(name):
    p = ports()[name]
    if not port_open(p):
        return False
    try:
        with httpx.Client(timeout=5, trust_env=False) as client:
            if name == "infinity":
                response = client.get(f"http://127.0.0.1:{p}/models")
                return response.is_success and MODEL in json.dumps(response.json())
            if name == "litellm":
                response = client.get(f"http://127.0.0.1:{p}/health/liveliness",
                                      headers={"Authorization": "Bearer " + config()["LITELLM_MASTER_KEY"]})
                return response.is_success
            if name == "giga-agent":
                return client.get(f"http://127.0.0.1:{p}/api/agent/auth/users/me").status_code == 401
        return True
    except (httpx.HTTPError, ValueError):
        return False

def start():
    ensure_free()
    if not (STATE / "mcp.json").exists() or not (ROOT / "litellm.yaml").exists():
        raise CourseError("Сначала выполните uv run dpo.py setup.")
    if any(owned_process(record(name)) for name in PORT_KEYS):
        raise CourseError("Остались процессы предыдущего запуска. Выполните stop, затем start.")
    try:
        for name, cmd in commands().items():
            spawn(name, cmd)
            deadline = time.monotonic() + (1800 if name == "infinity" else 600)
            while not ready(name):
                if not owned_process(record(name)) or time.monotonic() > deadline:
                    raise CourseError(f"Сервис {name} не готов. См. {RUN / (name + '.log')}")
                time.sleep(2)
            print(f"Готов: {name}, порт {ports()[name]}", flush=True)
    except BaseException:
        stop()
        raise
    print(f"Откройте http://localhost:{ports()['giga-agent']}")

def stop():
    failures = []
    for name in reversed(list(PORT_KEYS)):
        proc = owned_process(record(name))
        if proc:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
            else:
                children = proc.children(recursive=True)
                for child in reversed(children):
                    try:
                        child.terminate()
                    except psutil.Error:
                        pass
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                _, alive = psutil.wait_procs([*children, proc], timeout=5)
                for item in alive:
                    try:
                        item.kill()
                    except psutil.Error:
                        pass
            try:
                proc.wait(timeout=10)
            except psutil.TimeoutExpired:
                failures.append(name)
        if not owned_process(record(name)):
            (RUN / f"{name}.pid.json").unlink(missing_ok=True)
        print(f"{name}: {'ошибка остановки' if name in failures else 'остановлен'}")
    if failures:
        raise CourseError("Не удалось остановить: " + ", ".join(failures))

def status():
    print(f"{'Сервис':<14} {'PID':<9} {'Состояние':<14} {'Порт':<7} TCP")
    for name, port in ports().items():
        proc = owned_process(record(name))
        print(f"{name:<14} {str(proc.pid) if proc else '—':<9} "
              f"{'работает' if proc else 'остановлен':<14} {port:<7} "
              f"{'открыт' if port_open(port) else 'закрыт'}")

class API:
    def __init__(self):
        self.client = httpx.Client(base_url=f"http://127.0.0.1:{ports()['giga-agent']}/api/agent",
                                   timeout=300, trust_env=False, follow_redirects=True)
        c = config()
        try:
            auth = self.call("POST", "/auth/token", data={
                "username": c.get("GIGA_AGENT_ADMIN_EMAIL") or "admin@example.com",
                "password": c.get("GIGA_AGENT_ADMIN_PASSWORD") or "giga_agent_admin"})
            self.client.headers["Authorization"] = "Bearer " + auth["access_token"]
        except BaseException:
            self.client.close()
            raise

    def call(self, method, path, **kwargs):
        response = self.client.request(method, path, **kwargs)
        if not response.is_success:
            # Validation responses may contain secret inputs; never echo their bodies.
            raise CourseError(f"API: {method} {path}, HTTP {response.status_code}. Проверьте настройки и журнал giga-agent.")
        return response.json() if response.content else None

    def upsert(self, path, payload, *, update=True, immutable=()):
        matches = [item for item in self.call("GET", path) if item.get("name") == payload["name"]]
        if len(matches) > 1:
            raise CourseError(f"В API уже есть дубликаты: {payload['name']}. Удалите лишние записи в интерфейсе.")
        if not matches:
            return self.call("POST", path, json=payload)
        item = matches[0]
        if update:
            patch = {k: v for k, v in payload.items() if k not in immutable}
            return self.call("PATCH", path.rstrip("/") + "/" + item["id"], json=patch)
        return item

def agents():
    result = []
    for path in sorted((ROOT / "agents").glob("0*.md")):
        text = path.read_text(encoding="utf-8-sig")
        name, rest = text.split("\n\n", 1)
        description, rest = rest.split("\n\n## Инструкции\n\n", 1)
        instructions, message = rest.split("\n\n## Первое сообщение\n\n", 1)
        if os.sep != "\\":
            instructions = instructions.replace("\\", os.sep)
        result.append({"name": name.removeprefix("# "), "description": description,
                       "instructions": instructions.replace("{DATA_DIR}", str(DATA)),
                       "first_message": message.strip()})
    if len(result) != 3:
        raise CourseError("В agents/ должны быть три файла 01–03 с инструкциями.")
    return result

def seed():
    c = config()
    api = API()
    try:
        gc = api.upsert("/connectors", {"name": "ДПО: GigaChat", "type": "gigachat", "is_active": True,
            "check_connection": False, "settings": {"credentials": c["GIGACHAT_CREDENTIALS"],
            "scope": c.get("GIGACHAT_SCOPE") or "GIGACHAT_API_PERS"}}, immutable=("type",))
        local = api.upsert("/connectors", {"name": "ДПО: локальные эмбеддинги", "type": "openai",
            "is_active": True, "check_connection": False, "settings": {"base_url": f"http://127.0.0.1:{ports()['litellm']}/v1",
            "api_key": c["LITELLM_MASTER_KEY"]}}, immutable=("type",))
        llm = api.upsert("/llms", {"name": "ДПО: основная модель", "type": "gigachat",
            "connector_id": gc["id"], "model_id": c.get("GIGACHAT_MODEL") or "GigaChat-3-Ultra",
            "is_active": True, "check_connection": False, "settings": {}})
        # Embedding PATCH accepts name only; the server probes vector size at creation.
        emb = api.upsert("/embeddings", {"name": "ДПО: ru-en-rosberta", "type": "openai",
            "connector_id": local["id"], "model_id": "ru-en-rosberta", "is_active": True,
            "check_connection": True, "settings": {}}, update=False)
        sb = api.upsert("/sandboxes/providers", {"name": "ДПО: локальный Python", "type": "local_jupyter",
            "is_active": True, "settings": {"safe_execution": False, "write_dirs": [str(DATA)]}}, immutable=("type",))
        api.call("PATCH", "/auth/users/me", json={"llm_id": llm["id"], "embedding_id": emb["id"], "sandbox_provider_id": sb["id"]})
        for agent in agents():
            api.upsert("/projects/", {k: v for k, v in agent.items() if k != "first_message"})
            print("Настроен проект: " + agent["name"])
        col = api.upsert("/rag/collections", {"name": "ДПО: закупки"}, update=False)
        collection_id = col["uuid"]
        documents, offset = [], 0
        while True:
            page = api.call("GET", f"/rag/collections/{collection_id}/documents", params={"limit": 100, "offset": offset})
            documents.extend(page)
            if len(page) < 100:
                break
            offset += 100
        names = {item.get("metadata", {}).get("name") for item in documents}
        for path in sorted((DATA / "01_procurement" / "input").iterdir()):
            if path.is_file() and path.name not in names:
                text = path.read_text(encoding="utf-8-sig")
                api.call("POST", f"/rag/collections/{collection_id}/documents",
                    files={"files": (path.name + ".txt", text.encode("utf-8"), "text/plain")},
                    data={"metadatas_json": json.dumps([{"name": path.name}], ensure_ascii=False)})
                print("Добавлен текст в базу знаний: " + path.name)
        print(f"Настройка завершена. Проектов: {len(api.call('GET', '/projects/'))}; коннекторов API: {len(api.call('GET', '/connectors'))}.")
    finally:
        api.client.close()

async def mcp_tools(name):
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    async with streamablehttp_client(f"http://127.0.0.1:{ports()[name]}/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return len((await session.list_tools()).tools)

def embedding_check():
    from langchain_openai import OpenAIEmbeddings
    text = "Учебная проверка: гарантийный срок на светильники составляет тридцать шесть месяцев."
    c, p = config(), ports()
    emb = OpenAIEmbeddings(model="ru-en-rosberta", openai_api_key=c["LITELLM_MASTER_KEY"],
                           openai_api_base=f"http://127.0.0.1:{p['litellm']}/v1")
    assert emb.check_embedding_ctx_length is True, "Отключена стандартная токенизация"
    a = emb.embed_query(text)
    with httpx.Client(timeout=120, trust_env=False) as client:
        response = client.post(f"http://127.0.0.1:{p['infinity']}/embeddings", json={"model": MODEL, "input": [text]})
        response.raise_for_status()
        b = response.json()["data"][0]["embedding"]
    cosine = sum(x*y for x, y in zip(a, b)) / math.sqrt(sum(x*x for x in a) * sum(y*y for y in b))
    if len(a) != 1024 or len(b) != 1024 or cosine <= 0.999:
        raise CourseError("Векторы не прошли проверку размерности или сходства.")
    return f"1024 измерения; косинус {cosine:.9f}"

def check():
    results = []
    def run(label, fn):
        try:
            detail = fn()
            results.append(True)
            print(f"PASS | {label} | {detail}", flush=True)
        except Exception as exc:
            results.append(False)
            detail = str(exc) if isinstance(exc, CourseError) else "Сбой проверки; см. журналы сервисов."
            print(f"FAIL | {label} | {detail}", flush=True)
    print("Итог | Проверка | Результат")
    def login():
        api = API()
        api.client.close()
        return "вход выполнен"
    run("Вход в API", login)
    for name, expected in (("dpo_files", 16), ("web_fetch", 1)):
        def tools(n=name, e=expected):
            count = asyncio.run(asyncio.wait_for(mcp_tools(n), timeout=90))
            if count != e:
                raise CourseError(f"Инструментов: {count}; ожидалось {e}.")
            return f"инструментов: {count}"
        run("MCP " + name, tools)
    run("Локальные эмбеддинги", embedding_check)
    def defaults():
        api = API()
        try:
            user = api.call("GET", "/auth/users/me")
            for endpoint, field, name in (("/llms", "llm_id", "ДПО: основная модель"),
                ("/embeddings", "embedding_id", "ДПО: ru-en-rosberta"),
                ("/sandboxes/providers", "sandbox_provider_id", "ДПО: локальный Python")):
                item = next((x for x in api.call("GET", endpoint) if x.get("name") == name), None)
                if not item or not item["is_active"] or user.get(field) != item["id"]:
                    raise CourseError("Не выбран активный ресурс: " + name)
                if field == "sandbox_provider_id" and (item["settings"].get("safe_execution", False) is not False or str(DATA) not in item["settings"].get("write_dirs", [])):
                    raise CourseError("Проверьте режим исполнения и разрешение записи песочницы.")
            return "модель, эмбеддинг и песочница активны и выбраны"
        finally:
            api.client.close()
    run("Ресурсы пользователя", defaults)
    def projects():
        api = API()
        try:
            rows = api.call("GET", "/projects/")
            if any(sum(x["name"] == a["name"] and x["instructions"] == a["instructions"] for x in rows) != 1 for a in agents()):
                raise CourseError("Нужны три уникальных проекта с актуальными инструкциями.")
            return "3 проекта; инструкции актуальны"
        finally:
            api.client.close()
    run("Учебные проекты", projects)
    def rag():
        api = API()
        try:
            col = next(x for x in api.call("GET", "/rag/collections") if x["name"] == "ДПО: закупки")
            docs = api.call("GET", f"/rag/collections/{col['uuid']}/documents", params={"limit": 100})
            expected = {x.name for x in (DATA / "01_procurement" / "input").iterdir() if x.is_file()}
            if {x.get("metadata", {}).get("name") for x in docs} != expected or len(docs) != len(expected):
                raise CourseError("Состав текстов базы знаний не совпадает с комплектом закупок.")
            hits = api.call("POST", f"/rag/collections/{col['uuid']}/documents/search", json={"query": "Гарантия на светильники", "limit": 3})
            if not hits:
                raise CourseError("Поиск в базе знаний не вернул фрагментов.")
            return f"текстов: {len(docs)}; поиск работает"
        finally:
            api.client.close()
    run("База знаний", rag)
    if not all(results):
        raise CourseError(f"Проверки пройдены: {sum(results)} из {len(results)}.")
    print(f"Все проверки пройдены: {len(results)} из {len(results)}. Можно начинать занятие.")

def prefetch():
    RUN.mkdir(parents=True, exist_ok=True)
    jobs = [("MCP-прокси", [*PROXY, "--help"]), ("MCP для веб-страниц", [*FETCH, "--help"]),
            ("Infinity и зависимости CPU", [*INFINITY, "--help"]),
            ("LiteLLM и зависимости", [*LITELLM, "--help"])]
    jobs.append(("MCP для файлов (Node.js)", filesystem_command()))
    jobs.append(("Модель русских эмбеддингов (1–2 ГБ)", [UVX, "--python", "3.11", "--from", "infinity-emb[all]", "python", "-c",
        "from huggingface_hub import snapshot_download; snapshot_download('ai-forever/ru-en-RoSBERTa')"]))
    for idx, (label, cmd) in enumerate(jobs, 1):
        log = RUN / f"prefetch-{idx}.log"
        print("Загрузка: " + label, flush=True)
        with log.open("wb") as stream:
            completed = subprocess.run(cmd, cwd=ROOT, env=child_env(), stdin=subprocess.DEVNULL,
                stdout=stream, stderr=stream, **process_options())
        if completed.returncode:
            raise CourseError(f"Не удалось загрузить {label}. См. {log}")
        print("Загружено и сохранено в кэше: " + label, flush=True)
    print("Предзагрузка завершена. Проверьте up до занятия; GigaChat требует интернет при каждом запуске агента.")

def reset(yes=False):
    if not yes and input("Удалить БД, чаты и результаты этого комплекта? Введите ДА: ").strip() != "ДА":
        print("Сброс отменён.")
        return
    stop()
    targets = [STATE, *(folder for folder in DATA.glob("*/output") if folder.is_dir())]
    for target in targets:
        if not target.resolve().is_relative_to(ROOT) or target.is_symlink() or (hasattr(target, "is_junction") and target.is_junction()):
            raise CourseError("Отказ сброса: каталог выходит за пределы комплекта.")
    for target in targets:
        if target == STATE:
            if target.exists():
                shutil.rmtree(target)
        else:
            for child in target.iterdir():
                if child.name == ".gitkeep":
                    continue
                if child.is_symlink() or not child.is_dir():
                    child.unlink()
                else:
                    shutil.rmtree(child)
            (target / ".gitkeep").touch()
    print("База данных, чаты и результаты удалены. .env сохранён. Выполните uv run dpo.py up.")

def installer_key():
    credential = os.environ.get("DPO_GIGACHAT_CREDENTIALS") or config().get("GIGACHAT_CREDENTIALS", "")
    if not validate_credentials(credential):
        raise CourseError("Неверный формат ключа: нужен Authorization key Base64 от uuid:uuid.")
    if not (ROOT / ".env").exists():
        shutil.copyfile(ROOT / ".env.example", ROOT / ".env")
    set_key(str(ROOT / ".env"), "GIGACHAT_CREDENTIALS", credential)

def pack_offline():
    target = ROOT.parent / "dpo-giga-agent-offline.zip"
    paths = []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise CourseError("Архивирование ссылок запрещено.")
        if not path.is_file() or any(x in rel.parts for x in (".env", ".venv", ".giga_agent", "__pycache__", "output", ".downloads")) or path.suffix in (".log", ".pyc") or path.name == "litellm.yaml":
            continue
        paths.append(path)
    if sum(p.stat().st_size for p in paths) > 6 * 1024**3:
        raise CourseError("Размер больше 6 ГБ. Перенесите tools и .cache отдельно; см. README.")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for path in paths:
            z.write(path, str(Path(ROOT.name) / path.relative_to(ROOT)))
        z.writestr(ROOT.name + "/OFFLINE", "UV_OFFLINE=1; HF_HUB_OFFLINE=1; npm offline\n")
    print(f"Архив: {target.name}; байт: {target.stat().st_size}. Проверяйте на той же ОС и архитектуре.")

class RussianParser(argparse.ArgumentParser):
    def format_help(self):
        return super().format_help().replace("usage:", "Использование:")

    def error(self, message):
        self.exit(2, "Ошибка: неверная команда или параметры. Справка: uv run dpo.py --help\n")

def main():
    parser = RussianParser(description="Учебный комплект giga-agent для ДПО", add_help=False)
    parser.add_argument("-h", "--help", action="help", help="показать справку и завершить работу")
    parser._positionals.title = "Команда"
    parser._optionals.title = "Параметры"
    parser.add_argument("command", choices=["setup", "prefetch", "start", "stop", "status", "seed", "check", "up", "reset", "pack-offline", "installer-key", "open-ui"], help="команда управления")
    parser.add_argument("--yes", action="store_true", help="подтвердить удаление данных при reset")
    args = parser.parse_args()
    if args.command == "up":
        setup()
        start()
        seed()
        check()
    elif args.command == "pack-offline":
        pack_offline()
    elif args.command == "installer-key":
        installer_key()
    elif args.command == "open-ui":
        import webbrowser
        webbrowser.open(f"http://localhost:{ports()['giga-agent']}")
        c = config()
        print("Вход: " + (c.get("GIGA_AGENT_ADMIN_EMAIL") or "admin@example.com"))
        print("Пароль указан в .env (по умолчанию giga_agent_admin). Результаты: data/*/output/")
    elif args.command == "reset":
        reset(args.yes)
    else:
        globals()[args.command]()

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    try:
        main()
    except KeyboardInterrupt:
        print("Операция прервана. Для остановки сервисов: uv run dpo.py stop.")
        sys.exit(130)
    except (CourseError, httpx.HTTPError, OSError, KeyError) as exc:
        message = str(exc) if isinstance(exc, CourseError) else "Ошибка доступа к настройкам, процессам или сети. Проверьте .env, установку uv/Node.js и журналы .giga_agent/run/."
        print("Ошибка: " + message, file=sys.stderr)
        sys.exit(1)


# Самостоятельная настройка без установщика

## 1. Исходные условия и инструменты

1. Возьмите каталог `bundle/dpo-giga-agent` целиком, включая wheel, agents и data. Работайте в папке с `dpo.py` и `pyproject.toml`. Требования к Windows, месту, сети и ключу описаны в [инструкции установки](01_install_and_build.md). Не запускайте install.cmd или EXE для этого способа.
2. Установите вручную версии из `bootstrap.ps1`: uv 0.9.5 и Node.js 22.14.0 x64. Для точного соответствия используйте [архив uv](https://github.com/astral-sh/uv/releases/download/0.9.5/uv-x86_64-pc-windows-msvc.zip) и [архив Node.js](https://nodejs.org/dist/v22.14.0/node-v22.14.0-win-x64.zip). Сверьте SHA256 с официальными файлами `.sha256` для uv и `SHASUMS256.txt` того же выпуска Node.js. Эти URL и версии строятся bootstrap.ps1; доступность ссылок сейчас не проверялась.
3. Разместите uv.exe и uvx.exe в `tools/uv`, а содержимое корневой папки архива Node.js — в `tools/node`, чтобы там находились node.exe, npx.cmd и node_modules. Это расположение использует dpo.py; системный PATH менять не требуется. Далее команды Windows приведены для cmd, открытой в папке комплекта.
4. Создайте `.env` без чтения чужих настроек. PowerShell:

```powershell
Copy-Item .env.example .env
```

5. В редакторе вставьте собственный ключ, затем подготовьте окружение и конфигурацию. Команда cmd:

```cmd
tools\uv\uv.exe run dpo.py setup
```

`uv run` создаёт `.venv` и устанавливает зависимости из pyproject.toml: Python >=3.12, giga-agent[jupyter]==0.1.9 из `wheels/giga_agent-0.1.9-py3-none-any.whl`, httpx==0.28.1, python-dotenv==1.2.2, psutil>=7.0,<8. Отдельный requirements-файл в каталоге комплекта не предусмотрен. Python для Infinity задаётся отдельно как 3.11, для LiteLLM — 3.12. Ручная установка системного Python не обязательна при доступности управляемого Python через uv. Прямой вызов uv до входа в dpo.py может использовать стандартный кэш uv; локальные переменные кэша самого dpo.py применяются после его загрузки.

## 2. Все настройки, которые читает dpo.py

Значения из `.env` читаются через python-dotenv. Таблица отражает defaults в коде dpo.py, а не содержимое конкретного файла `.env`. Настоящие ключи в примерах не приводятся.

| Переменная в .env | Назначение и значение по умолчанию в коде |
|---|---|
| GIGACHAT_CREDENTIALS | Обязательный Authorization key. Значение: `<ВАШ_AUTHORIZATION_KEY>`; замените целиком, включая скобки. Рабочего значения по умолчанию нет. |
| GIGACHAT_SCOPE | Scope коннектора; GIGACHAT_API_PERS. |
| GIGACHAT_MODEL | Модель генерации; GigaChat-3-Ultra. |
| LITELLM_MASTER_KEY | Секрет локального прокси; при пустом значении setup создаёт sk- плюс 32 случайных байта в hex и сохраняет в .env. |
| GIGA_AGENT_ADMIN_EMAIL | Учебный вход; admin@example.com для API-клиента dpo.py. Укажите до первого запуска сервера. |
| GIGA_AGENT_ADMIN_PASSWORD | Учебный пароль; giga_agent_admin для API-клиента dpo.py. Укажите до первого запуска сервера. |
| GIGA_AGENT_PORT | Порт UI/API; 9090. |
| MCP_FILES_PORT | MCP файлов; 8101. |
| MCP_FETCH_PORT | MCP веб-загрузки; 8102. |
| INFINITY_PORT | Локальные эмбеддинги; 8103. |
| LITELLM_PORT | Прокси эмбеддингов; 8104. |

Порты должны быть целыми, разными, в диапазоне 1–65535. После изменения портов остановите службы, повторите setup, start и seed. Смена пароля уже существующего пользователя через изменение .env в dpo.py не реализована.

Дополнительно dpo.py читает из окружения процесса `PATH` (добавляет tools), `DPO_GIGACHAT_CREDENTIALS` (только installer-key: приоритет над ключом из .env), и весь набор окружения при формировании дочерних процессов. Произвольные переменные могут наследоваться, но самостоятельных настроек комплекта для них нет. `DPO_GIGACHAT_CREDENTIALS` для ручного setup не требуется.

Сам dpo.py принудительно задаёт `UV_CACHE_DIR=.cache/uv`, `UV_PYTHON_INSTALL_DIR=.cache/python`, `UV_TOOL_DIR=.cache/uv-tools`, `HF_HOME=.cache/huggingface`, `npm_config_cache=.cache/npm` как абсолютные пути относительно комплекта. При наличии файла `OFFLINE` задаёт `UV_OFFLINE=1`, `HF_HUB_OFFLINE=1`, `npm_config_offline=true`.

Дочерним процессам задаются `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`, `LITELLM_MASTER_KEY` из .env, `GIGA_AGENT_PROJECT_ROOT` как абсолютный путь `.giga_agent`, `GIGA_AGENT_LOCAL_JUPYTER_STARTUP_TIMEOUT_SEC=90`, `GIGA_AGENT_LOCAL_JUPYTER_SECURE_EXEC_DEFAULT=false`, `GIGA_AGENT_PREFIX_API=/agent`, `GIGA_AGENT_SKIP_ONBOARDING=true`, `GIGA_AGENT_GIGACHAT_FROM_ENV=false`, `GIGA_AGENT_LANGGRAPH_DEV_RELOAD=false`. Остальные входящие `GIGA_AGENT_*` сначала удаляются, затем из .env переносятся непустые GIGA_AGENT_PORT, GIGA_AGENT_ADMIN_EMAIL и GIGA_AGENT_ADMIN_PASSWORD. Входящие GIGACHAT_CREDENTIALS, GIGACHAT_SCOPE, GIGACHAT_MODEL удаляются из окружения детей: коннектор настраивает seed через API.

## 3. Конфигурация и запуск пяти служб

1. Setup проверяет формат ключа и длину пути, создаёт `.giga_agent/mcp.json`, `litellm.yaml` и каталоги output. MCP-конфигурация содержит `mcpServers` с именами dpo_files и web_fetch, URL `http://127.0.0.1:8101/mcp` и `http://127.0.0.1:8102/mcp` при стандартных портах.
2. Setup генерирует следующий `litellm.yaml`; при изменении INFINITY_PORT адрес будет другим:

```yaml
model_list:
  - model_name: ru-en-rosberta
    litellm_params:
      model: infinity/ai-forever/ru-en-RoSBERTa
      api_base: http://127.0.0.1:8103
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
litellm_settings:
  set_verbose: false
```

3. При необходимости заранее загрузите вспомогательные окружения, npm-пакет и модель, cmd:

```cmd
tools\uv\uv.exe run dpo.py prefetch
```

4. Запустите службы, cmd:

```cmd
tools\uv\uv.exe run dpo.py start
```

Отдельных подкоманд запуска одной службы в dpo.py нет. Используйте start: он задаёт окружение, сохраняет PID с временем создания и на Windows изолирует группы процессов, что важно для Jupyter. Ниже описаны реальные команды, формируемые функцией commands(), а не дополнительные команды для ручного копирования:

| Порядок | Служба | Что запускается |
|---|---|---|
| 1 | dpo_files, 8101 | uvx mcp-proxy@0.15.0 с --host 127.0.0.1, --port 8101; после -- запускается Node.js npx-cli.js с -y @modelcontextprotocol/server-filesystem@2.2.0 и абсолютным путём data. При отсутствии локальной Node.js используется npx.cmd через cmd /c. |
| 2 | web_fetch, 8102 | Такой же mcp-proxy с --port 8102; после -- запускается uvx mcp-server-fetch@2026.11.4. |
| 3 | infinity, 8103 | uvx --python 3.11 --from infinity-emb[all] infinity_emb v2 с --model-id ai-forever/ru-en-RoSBERTa, --device cpu, --host 127.0.0.1, --port 8103, --no-bettertransformer. |
| 4 | litellm, 8104 | uvx --python 3.12 --from litellm[proxy] litellm с --config и абсолютным путём litellm.yaml, --host 127.0.0.1, --port 8104. |
| 5 | giga-agent, 9090 | giga_agent.exe из Python-окружения: dev --host 127.0.0.1 --port 9090 --no-reload. |

Start ждёт готовности каждой службы: MCP — открытый TCP-порт; Infinity — наличие модели в `/models`; LiteLLM — успешный `/health/liveliness` с ключом; giga-agent — HTTP 401 для неавторизованного `/api/agent/auth/users/me`. При сбое start пытается остановить свои процессы. Seed ещё не выполнен.

## 4. Первоначальная настройка и ручной эквивалент seed

1. Примените учебную настройку, cmd:

```cmd
tools\uv\uv.exe run dpo.py seed
```

2. Откройте http://localhost:9090 и войдите с учебными значениями `admin@example.com` / `giga_agent_admin` либо своими настройками. Сам seed не создаёт пользователя: он авторизуется в уже запущенном giga-agent. Создание начального администратора выполняет приложение; отдельного пользовательского мастера создания в dpo.py нет.
3. Если настраиваете ресурсы вручную через UI, используйте следующие значения из seed. Точные названия экранов и доступность всех полей UI из dpo.py не устанавливаются; ниже приведено соответствие данных, а не проверенный маршрут кликов. Если UI не позволяет задать поле, используйте seed.

| Ресурс | Значения |
|---|---|
| Коннектор «ДПО: GigaChat» | type gigachat, активен, credentials — собственный ключ, scope GIGACHAT_API_PERS либо значение GIGACHAT_SCOPE; check_connection=false. |
| Коннектор «ДПО: локальные эмбеддинги» | type openai, активен, base_url http://127.0.0.1:8104/v1, api_key — локальный LITELLM_MASTER_KEY; check_connection=false. |
| «ДПО: основная модель» | type gigachat, первый коннектор, model_id GigaChat-3-Ultra либо GIGACHAT_MODEL, активна, settings пустые, check_connection=false. |
| «ДПО: ru-en-rosberta» | type openai, локальный коннектор, model_id ru-en-rosberta, активен, settings пустые, check_connection=true. Размерность при создании проверяет сервер. |
| «ДПО: локальный Python» | type local_jupyter, активен, safe_execution=false, write_dirs — список из абсолютного пути data. Это учебный режим исполнения, а не изоляция Python на уровне ОС. |

4. Выберите для текущего пользователя эти модель, эмбеддинг и песочницу как ресурсы по умолчанию. Seed записывает llm_id, embedding_id, sandbox_provider_id через `/auth/users/me`.
5. MCP-подключения берутся из `.giga_agent/mcp.json`, созданного setup. Они не являются двумя REST-коннекторами из таблицы. Для ручного заполнения UI, если оно доступно, используйте имена и HTTP URL из раздела 3; точный экран регистрации из dpo.py не выводится.
6. В «Проектах» создайте три проекта без дублей. Название берите из первого заголовка соответствующего файла, описание — из абзаца после него, инструкции — из раздела «Инструкции». Замените `{DATA_DIR}` абсолютным путём data:

| Проект | Источник | Результаты в соответствующем output |
|---|---|---|
| Агент: проверка закупок | agents/01_procurement.md | report.md |
| Агент: контроль поручений | agents/02_assignments.md | status_report.md, questions.md |
| Агент: разбор обращений | agents/03_appeals.md | incidents.md, manual_review.md |

Seed не сохраняет раздел «Первое сообщение» в проект; отправьте его сами в новом чате проекта. Инструкции фиксируют ограничения и пути к input/output; копируйте их полностью.
7. Создайте коллекцию базы знаний «ДПО: закупки». Seed передаёт только имя коллекции. Загрузите все пять файлов из `data/01_procurement/input`: acceptance.md, contract.md, estimate.csv, schedule.md, technical_spec.md. Для точного соответствия seed каждый файл читается как текст UTF-8, загружается как text/plain с добавленным `.txt` к имени, а metadata.name сохраняет исходное имя. Доступность задания metadata в UI не проверена; без него автоматический check может не принять ручную загрузку. Для точного результата используйте seed.
8. Seed ищет ресурсы по имени; при дублях выдаёт ошибку. Модель эмбеддингов и существующая коллекция не обновляются; документы добавляются только при отсутствии исходного имени в metadata. Повторный seed не заменяет текст уже загруженного документа. Для изменённых документов нужна отдельная ручная обработка либо учебный reset с потерей данных.

## 5. Семь проверок

1. Выполните, cmd:

```cmd
tools\uv\uv.exe run dpo.py check
```

| Проверка | Критерий PASS |
|---|---|
| Вход в API | Успешная авторизация с настройками администратора. |
| MCP dpo_files | Инициализация MCP и ровно 16 инструментов. |
| MCP web_fetch | Инициализация MCP и ровно один инструмент. |
| Локальные эмбеддинги | LangChain OpenAIEmbeddings со стандартной токенизацией через LiteLLM и прямой Infinity возвращают векторы по 1024 измерения с косинусом >0.999. |
| Ресурсы пользователя | Именованные модель, эмбеддинг, песочница активны и выбраны пользователем; у песочницы safe_execution=false и абсолютный data в write_dirs. |
| Учебные проекты | Для каждого из трёх сценариев ровно один проект с актуальными именем и инструкциями из agents. |
| База знаний | Имена metadata и число документов точно соответствуют input закупок; поиск «Гарантия на светильники» возвращает фрагменты. |

2. Дождитесь итога 7 из 7. Check не выполняет генерацию ответа GigaChat и не доказывает доступность тарифа/модели для генерации. Для проверки занятия отправьте первые сообщения из agents в новые чаты и сопоставьте результаты с `data/instructor/expected_results.md`. Вопрос для RAG находится в `agents/rag_demo.md`.
3. На Windows 11 (сборка 10.0.26300) 15.11.2026 получено 7 из 7 при первой установке (около 10 минут) и повторном запуске install.cmd (около 3 минут). Записи о 6/7 в README.md и CHECKLIST.md относятся к более раннему испытанию и устарели; собственный check обязателен.

## 6. Состояние, остановка и сброс

1. Состояние процессов и TCP-портов, cmd:

```cmd
tools\uv\uv.exe run dpo.py status
```

2. Остановка своих пяти служб и их дочерних процессов, cmd:

```cmd
tools\uv\uv.exe run dpo.py stop
```

Повторите status: процессы должны быть остановлены, порты закрыты. PID сверяется со временем создания и корнем комплекта. Журналы находятся в `.giga_agent/run/`.
3. Учебный сброс, cmd:

```cmd
tools\uv\uv.exe run dpo.py reset
```

Введите `ДА`. Сброс останавливает службы, удаляет `.giga_agent` вместе с БД, чатами и журналами и очищает output, сохраняя `.gitkeep`. `.env`, input, инструменты и кэши остаются. Для автоматического подтверждения существует `reset --yes`; используйте только при осознанном удалении учебных данных.
4. Восстановите конфигурацию, службы и начальные данные одной командой, cmd:

```cmd
tools\uv\uv.exe run dpo.py up
```

Up последовательно выполняет setup, start, seed, check. Для ежедневного запуска без повторной настройки достаточно start. Если seed/check завершились ошибкой, службы могут остаться работать: проверьте status, исправьте причину и повторите соответствующий шаг либо stop.

## 7. Linux и macOS

В dpo.py есть ветви для Unix: исполняемые файлы без .exe, Node.js в tools/node/bin, группы процессов с start_new_session и остановка через SIGTERM. Bootstrap.sh поддерживает Linux/Darwin и x86_64/arm64 (aarch64); предусмотрены install.sh, start.sh и stop.sh. Полный цикл подтверждён только на Windows: CHECKLIST сообщает для Linux/macOS лишь bash -n.

При самостоятельной подготовке используйте uv 0.9.5 и Node.js 22.14.0 для своей ОС/архитектуры. Вместо `tools\uv\uv.exe` путь — `tools/uv/uv`, разделитель каталогов — `/`; подкоманды dpo.py те же. Окружение приложения и модели всё равно создаётся uv. Windows-архив tools/.cache нельзя считать переносимым на Unix. Полная установка и автономный перенос на Linux/macOS не проверены.

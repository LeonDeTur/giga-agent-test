#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/bootstrap.sh"
cd "$ROOT"
trap 'echo "Ошибка установки. Проверьте интернет и .giga_agent/run/install.log" >&2' ERR
available=$(df -Pk "$ROOT" | awk 'END {print $4}')
(( available >= 5*1024*1024 )) || { echo 'Требуется около 5 ГБ'; exit 1; }
mkdir -p .giga_agent/run
exec > >(tee -a .giga_agent/run/install.log) 2>&1
echo 'Первый запуск скачивает около 2 ГБ, 10–20 минут.'
bootstrap
until course installer-key; do
    echo 'developers.sber.ru → GigaChat API → Ключ авторизации; GIGACHAT_API_PERS'
    read -r -s -p 'Вставьте ключ: ' DPO_GIGACHAT_CREDENTIALS
    echo
    export DPO_GIGACHAT_CREDENTIALS
done
unset DPO_GIGACHAT_CREDENTIALS
course up
course open-ui

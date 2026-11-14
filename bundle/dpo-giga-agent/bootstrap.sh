#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
UV_VERSION=0.9.5
NODE_VERSION=22.14.0
export UV_CACHE_DIR="$ROOT/.cache/uv" UV_PYTHON_INSTALL_DIR="$ROOT/.cache/python" UV_TOOL_DIR="$ROOT/.cache/uv-tools" HF_HOME="$ROOT/.cache/huggingface" npm_config_cache="$ROOT/.cache/npm" PYTHONUTF8=1 PYTHONIOENCODING=utf-8
export PATH="$ROOT/tools/uv:$ROOT/tools/node/bin:$PATH"
if [[ -f "$ROOT/OFFLINE" ]]; then export UV_OFFLINE=1 HF_HUB_OFFLINE=1 npm_config_offline=true; fi
verify() {
    local actual
    if command -v sha256sum >/dev/null; then actual=$(sha256sum "$1"); else actual=$(shasum -a 256 "$1"); fi
    [[ "${actual%% *}" == "$2" ]] || { echo 'Ошибка: SHA256 не совпадает.' >&2; exit 1; }
    echo "SHA256 проверен: ${actual%% *}"
}
bootstrap() {
    local os arch target stage asset base expected
    case "$(uname -s)" in Linux) os=linux;; Darwin) os=darwin;; *) echo 'Неподдерживаемая ОС'; exit 1;; esac
    case "$(uname -m)" in x86_64) arch=x64; target=x86_64;; arm64|aarch64) arch=arm64; target=aarch64;; *) echo 'Неподдерживаемая архитектура'; exit 1;; esac
    for kind in uv node; do
        [[ -x "$ROOT/tools/$kind/$( [[ $kind == node ]] && echo bin/node || echo uv )" ]] && continue
        [[ ${UV_OFFLINE:-0} != 1 ]] || { echo 'Автономные инструменты отсутствуют'; exit 1; }
        mkdir -p "$ROOT/.downloads"
        stage=$(mktemp -d "$ROOT/.downloads/download.XXXXXXXX")
        if [[ $kind == uv ]]; then
            [[ $os == linux ]] && target="$target-unknown-linux-gnu" || target="$target-apple-darwin"
            asset="uv-$target.tar.gz"; base="https://github.com/astral-sh/uv/releases/download/$UV_VERSION"
            curl -fLsS "$base/$asset.sha256" -o "$stage/checks"
            expected=$(awk 'NR==1 {print $1}' "$stage/checks")
        else
            asset="node-v$NODE_VERSION-$os-$arch.tar.xz"; base="https://nodejs.org/dist/v$NODE_VERSION"
            curl -fLsS "$base/SHASUMS256.txt" -o "$stage/checks"
            expected=$(awk -v name="$asset" '$2==name {print $1}' "$stage/checks")
        fi
        [[ $expected =~ ^[a-fA-F0-9]{64}$ ]] || { echo 'Некорректный официальный SHA256'; exit 1; }
        echo "Загрузка $asset"
        curl -fLsS "$base/$asset" -o "$stage/$asset" || { echo 'Ошибка загрузки. Проверьте интернет.'; exit 1; }
        verify "$stage/$asset" "$expected"
        mkdir "$stage/extract"
        tar -xf "$stage/$asset" -C "$stage/extract" --strip-components=1
        mkdir -p "$ROOT/tools/$kind"
        cp -R "$stage/extract/." "$ROOT/tools/$kind/"
    done
}
course() { "$ROOT/tools/uv/uv" run --project "$ROOT" "$ROOT/dpo.py" "$@"; }

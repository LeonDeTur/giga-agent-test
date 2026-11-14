#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/bootstrap.sh"
cd "$ROOT"
bootstrap
course stop


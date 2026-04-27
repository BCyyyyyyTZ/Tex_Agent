#!/usr/bin/env sh
# 仓库根执行: ./scripts/start-texagent-web.sh
cd "$(dirname "$0")/.." || exit 1
exec python scripts/start_texagent_web.py "$@"

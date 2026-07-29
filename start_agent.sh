#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if command -v pyenv >/dev/null 2>&1; then
  PYTHON_CMD=(pyenv exec python)
else
  PYTHON_CMD=(python3)
fi

if [[ ! -f ".env" ]]; then
  echo "未找到 .env。请先执行: cp .env.example .env，并填入 MiniMax / ComfyUI 配置。"
  exit 1
fi

"${PYTHON_CMD[@]}" - <<'PY'
try:
    import prompt_toolkit  # noqa: F401
except ImportError:
    raise SystemExit("缺少依赖。请先运行: python -m pip install -r requirements.txt")
PY

"${PYTHON_CMD[@]}" main.py --agent

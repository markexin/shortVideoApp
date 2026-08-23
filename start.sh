#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

SESSION="instantvideo"
BACKEND_PORT=8000
FRONTEND_DIR="web/frontend"
FRONTEND_PORT=5173
LOG_DIR=".logs"

say() { echo "[instantvideo] $*"; }

check_env() {
  if [[ ! -f ".env" ]]; then
    say "未找到 .env。请先执行: cp .env.example .env，并填入 MiniMax / ComfyUI 配置。"
    exit 1
  fi
}

check_deps() {
  if ! command -v tmux >/dev/null 2>&1; then
    say "未检测到 tmux，请先安装: brew install tmux"
    exit 1
  fi
  if [[ ! -d "${FRONTEND_DIR}/node_modules" ]]; then
    say "前端依赖未安装，正在执行 npm install（首次启动需要一些时间）..."
    ( cd "${FRONTEND_DIR}" && npm install )
  fi
}

is_up() {
  curl -s -o /dev/null -m 2 "http://localhost:$1/api/health"
}

start_backend() {
  tmux send-keys -t "$SESSION" "uvicorn web.app:app --host 0.0.0.0 --port $BACKEND_PORT --reload" C-m
}

start_frontend() {
  tmux send-keys -t "$SESSION" "cd ${FRONTEND_DIR} && npm run dev" C-m
}

start() {
  check_env
  check_deps
  mkdir -p "$LOG_DIR"

  if tmux has-session -t "$SESSION" 2>/dev/null; then
    tmux kill-session -t "$SESSION"
  fi

  say "正在启动后端（port ${BACKEND_PORT}）和前端（port ${FRONTEND_PORT}）..."
  tmux new-session -d -s "$SESSION" -n app "uvicorn web.app:app --host 0.0.0.0 --port $BACKEND_PORT --reload"
  tmux new-window -t "$SESSION" -n web "cd ${FRONTEND_DIR} && npm run dev"

  for i in $(seq 1 30); do
    if is_up "$BACKEND_PORT"; then break; fi
    sleep 1
  done

  if is_up "$BACKEND_PORT"; then
    say "启动完成。前端访问: http://localhost:${FRONTEND_PORT}"
  else
    say "警告：等待 ${BACKEND_PORT} 端口超时，后端可能启动失败。用 status 查看详情。"
  fi
}

stop() {
  if tmux has-session -t "$SESSION" 2>/dev/null; then
    tmux kill-session -t "$SESSION"
    say "已停止所有服务。"
  else
    say "没有正在运行的服务。"
  fi
}

status() {
  echo "[instantvideo] 端口状态："
  if curl -s -o /dev/null -m 2 "http://localhost:${BACKEND_PORT}/api/health"; then
    echo "  后端 (${BACKEND_PORT}): 运行中"
  else
    echo "  后端 (${BACKEND_PORT}): 未启动"
  fi
  if curl -s -o /dev/null -m 2 "http://localhost:${FRONTEND_PORT}/"; then
    echo "  前端 (${FRONTEND_PORT}): 运行中"
  else
    echo "  前端 (${FRONTEND_PORT}): 未启动"
  fi

  if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo ""
    echo "[instantvideo] tmux 会话 '${SESSION}'："
    tmux list-windows -t "$SESSION" -F '  window #{window_index}: #{window_name} (#{window_activity})'
  fi
}

restart() {
  stop
  sleep 1
  start
}

case "${1:-}" in
  start)   start ;;
  stop)    stop ;;
  status)  status ;;
  restart) restart ;;
  *)
    cat <<EOF
用法: $0 {start|stop|status|restart}

一键启动/停止 InstantVideo 后端与前端。
服务运行在 tmux 会话 '${SESSION}' 中，关闭终端不会中断。

  start    启动后端(port ${BACKEND_PORT}) 和 前端(port ${FRONTEND_PORT})
  stop     停止所有服务
  status   查看端口与服务运行状态
  restart  重启所有服务
EOF
    exit 1
    ;;
esac
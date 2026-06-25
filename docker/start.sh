#!/usr/bin/env sh
set -eu

cd /app/backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
api_pid="$!"

term_handler() {
  kill "$api_pid" 2>/dev/null || true
  nginx -s quit 2>/dev/null || true
  wait "$api_pid" 2>/dev/null || true
}
trap term_handler INT TERM

nginx -g 'daemon off;' &
nginx_pid="$!"

wait "$nginx_pid"
term_handler

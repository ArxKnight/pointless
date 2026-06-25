#!/usr/bin/env sh
set -eu

cd /app/backend
# Bind FastAPI to 0.0.0.0 so users who publish 8000:8000 can still reach the API directly.
# Nginx remains the normal web entrypoint on port 80 and proxies /api to this backend.
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
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

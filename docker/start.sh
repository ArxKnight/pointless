#!/usr/bin/env sh
set -eu

cd /app/backend
: "${PORT:=80}"
sed "s/listen 80;/listen ${PORT};/" /etc/nginx/conf.d/default.conf > /tmp/pointless-nginx.conf
cp /tmp/pointless-nginx.conf /etc/nginx/conf.d/default.conf

# Bind FastAPI to 0.0.0.0 so users who publish 8000:8000 can still reach the API directly.
# Nginx remains the normal web entrypoint and proxies /api to this backend.
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

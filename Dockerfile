FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_CONFIG_PATH=/data/config.json

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/nginx/sites-enabled/default /etc/nginx/conf.d/default.conf \
    && mkdir -p /data /run/nginx /var/log/nginx /usr/share/nginx/html

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r ./backend/requirements.txt

COPY backend/alembic.ini ./backend/alembic.ini
COPY backend/alembic ./backend/alembic
COPY backend/app ./backend/app
COPY --from=frontend-build /frontend/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY docker/start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 80
VOLUME ["/data"]
CMD ["/start.sh"]

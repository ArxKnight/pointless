# Quarterly Points Distribution Web App

Self-hosted FastAPI + React app in one Docker container, with MySQL as the persistent database.

## Run from source

```bash
docker compose up -d --build
```

If port 80 is busy:

```bash
FRONTEND_PORT=8088 docker compose up -d --build
```

## Published Docker image

Prebuilt single-container app image on Docker Hub:

```text
arxknight/quarterly-points-app:latest
arxknight/quarterly-points-app:0.1.4
```

The app container includes both:

- Nginx serving the built React frontend
- FastAPI backend behind `/api`

MySQL remains a separate database service/connection so data can survive app reinstalls and can be hosted externally.

The normal web UI is served by Nginx on container port `80`. If you want to browse on host port `8000`, map host `8000` to container `80`:

```bash
docker run -d --name quarterly-points-app \
  -p 8000:80 \
  -v quarterly_points_app_data:/data \
  arxknight/quarterly-points-app:latest
```

Container port `8000` also serves the same React UI as a fallback as well as the API, so Docker platforms that auto-publish port `8000` will still open the installer instead of a JSON 404.

On first boot the logs include Uvicorn's standard `Application startup complete` message. That only means the web server has started; it does **not** mean the app installer has been completed. Check `GET /api/health`: a clean first boot returns `{"ok": true, "installed": false}` until you finish the web installer.

Open the frontend and complete the first-run installer. With the bundled Compose MySQL service, use:

```text
Host: mysql
Port: 3306
Database: pointsdb
Username: pointsapp
Password: points_password_change_me
```

The installer has an InfraDB-style connection test before setup. It reports whether the database exists, whether an existing Quarterly Points schema is present, and whether an admin account was found.

The installer creates/initialises the database schema and creates the first admin account you choose. It stores the MySQL connection in the persistent `app_data` volume at `/data/config.json`; the MySQL data lives in `mysql_data`. If you rebuild/reinstall the app container but keep those volumes, the app reconnects to the existing data automatically.

If the app config volume is lost but the MySQL database remains, run the installer again with the same MySQL connection. The connection test will detect the existing schema/admin and you can select **Reuse existing database** to save the connection without creating a new admin, restoring access to the existing data.

For an external MySQL server, enter that server's host, port, database, username and password in the installer. The user should either have permission to create the database or access to an already-created database.

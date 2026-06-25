# Quarterly Points Distribution Web App

Dockerised FastAPI + MySQL + React app.

## Run

```bash
docker compose up -d --build
```

If port 80 is busy:

```bash
FRONTEND_PORT=8088 docker compose up -d --build
```

Open the frontend and complete the first-run installer. With the bundled Compose MySQL service, use:

```text
Host: mysql
Port: 3306
Database: pointsdb
Username: pointsapp
Password: points_password_change_me
```

The installer has an InfraDB-style connection test before setup. It reports whether the database exists, whether an existing Quarterly Points schema is present, and whether an admin account was found.

The installer creates/initialises the database schema and creates the first admin account you choose. It stores the MySQL connection in the persistent `app_data` volume at `/data/config.json`; the MySQL data lives in `mysql_data`. If you rebuild/reinstall the app containers but keep those volumes, the app reconnects to the existing data automatically.

If the app config volume is lost but the MySQL database remains, run the installer again with the same MySQL connection. The connection test will detect the existing schema/admin and you can select **Reuse existing database** to save the connection without creating a new admin, restoring access to the existing data.

For an external MySQL server, enter that server's host, port, database, username and password in the installer. The user should either have permission to create the database or access to an already-created database.

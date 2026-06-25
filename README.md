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
arxknight/quarterly-points-app:0.2.0
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

## Overview Tree and teams

The former Overview page is now **Overview Tree**. It renders a top-down, team-grouped points graph from the backend `/api/quarters/active/overview-tree` response. Team and team-group headings are visual containers only: every displayed allocation link comes from a real `giving_plans` row.

Administrators manage team structure in **Settings → User Roles → Team Management**:

- Create, edit, rename and deactivate teams.
- Create, edit, rename and deactivate team groups.
- Assign users to any active team or leave them unassigned.
- Move users between teams without changing their application role.
- Configure each team's group, colour, display order and active status.

Team membership is stored on `users.team_id` using a nullable foreign key to `teams.id`; roles remain stored separately on `users.is_admin`. Renaming users, teams or groups does not break membership.

Initial team seed data creates empty groups and teams only; it does not create or guess user accounts:

- Team groups: `Shift A + Shift B`, `Shift C + Shift D`, `Others`
- Teams: `Shift A`, `Shift B`, `Shift C`, `Shift D`, `Others`

Existing installs are upgraded safely at startup with the new tables and nullable `users.team_id` column. Alembic migration `0002_teams` is also included for environments that run migrations manually.

## New team API endpoints

All endpoints require authentication. Write endpoints require administrator permission.

```text
GET    /api/teams?include_inactive=false
POST   /api/teams
GET    /api/teams/{team_id}
PATCH  /api/teams/{team_id}
DELETE /api/teams/{team_id}                 # soft-deactivates; optional {"move_users_to_team_id": id|null}
GET    /api/teams/{team_id}/users
GET    /api/teams/unassigned-users

GET    /api/teams/groups/?include_inactive=false
POST   /api/teams/groups/
GET    /api/teams/groups/{group_id}
PATCH  /api/teams/groups/{group_id}
DELETE /api/teams/groups/{group_id}         # soft-deactivates and ungroups its teams

PATCH  /api/users/{user_id}/team            # {"team_id": id|null}
GET    /api/quarters/active/overview-tree
```

Team payload fields: `name`, optional `description`, `colour` (`#RRGGBB`), `display_order`, `is_active`, optional `group_id`.

Team group payload fields: `name`, optional `description`, `display_order`, `is_active`.

## Development verification

```bash
cd backend
python3 -m pytest -q

cd ../frontend
npm run build
```

If using Docker locally:

```bash
docker build -t arxknight/quarterly-points-app:latest .
docker push arxknight/quarterly-points-app:latest
```

# Quarterly Points Distribution Web App

Self-hosted FastAPI + React app in one Docker container, with MySQL as the persistent database.

## Core purpose

An administrator manages quarterly points distributions:

1. Add distribution participants by typing or pasting names.
2. Configure who can reasonably give points to whom.
3. Select participants for a quarter.
4. Generate a balanced draft distribution.
5. Review/validate it.
6. Publish it.
7. Participants open their public Giving Tree page at `/tree/{slug}`.

Only administrators need login accounts. Participants do **not** need usernames, passwords, emails, roles, or app accounts.

## Published Docker image

Prebuilt single-container app image on Docker Hub:

```text
arxknight/quarterly-points-app:latest
arxknight/quarterly-points-app:0.3.6
```

The app container includes Nginx serving the React frontend and FastAPI behind `/api`. MySQL remains a separate persistent database.

## Run from source

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

The installer creates/initialises the database schema and creates the first admin account you choose. It stores the MySQL connection in the persistent `app_data` volume at `/data/config.json`; the MySQL data lives in `mysql_data`.

## Data model

### Administrator accounts

Administrator login accounts remain in `users`.

They are used only to manage the application:

- login
- participants
- compatibility
- quarters
- generation
- publishing

### Distribution participants

Participants are stored separately in `participants`:

- `id`
- `display_name`
- `slug`
- `is_active`
- `notes`
- `created_at`
- `updated_at`

Participants do not need:

- username
- password
- email address
- role
- login account

Existing `department_members` records are preserved and backfilled into `participants` during migration/startup upgrade.

## Participant management

Administrators can manage participants from **Settings → Participants**:

- add one participant
- paste a list of names
- ignore blank lines
- detect duplicate names
- generate unique slugs
- edit display names
- edit slugs separately
- deactivate/reactivate participants
- safely delete unused participants
- view/copy public tree links
- search/filter participants

Example slugs:

```text
Alex       -> /tree/alex
John Smith -> /tree/john-smith
Alex       -> /tree/alex-2
```

Renaming a participant does not automatically change their slug. If the slug is edited, the old slug is retained as a redirect record where practical.

## Compatibility

Permanent teams and team groups are deprecated from the core workflow.

Compatibility is now represented with direct participant-to-participant rules:

- `Allowed`
- `Blocked`
- unset/no rule

Rules are stored directionally so future one-way compatibility can be supported. The UI edits rules mutually by default.

Administrators can use **Settings → Compatibility** to click matrix cells or bulk-allow a selected working group.

## Quarters and publishing

Quarters now have statuses:

- `draft`
- `published`
- `completed`

Public Giving Tree pages only show the latest published quarter.

Workflow:

1. Open **Quarters**.
2. Create a draft quarter.
3. Select participants included in that quarter.
4. Validate compatibility.
5. Generate a draft distribution.
6. Review totals and allocations.
7. Publish when ready.

Regenerating a draft does not change public pages. Publishing explicitly updates the current public distribution.

## Allocation algorithm

The generator uses compatibility-aware constraint generation:

- participants are senders and recipients
- each sender must send exactly 50 points
- each recipient must receive exactly 50 points
- self-allocation is blocked
- blocked compatibility edges are never used
- allocation amounts are positive whole numbers
- default min allocation: 5
- default max allocation to one recipient: 25
- preferred recipient count: 2 to 5

It first tries balanced uneven ring-style allocations for good variety. If that cannot satisfy compatibility, it falls back to a bounded max-flow solver over the allowed directed graph. Every result is validated before being saved or published.

Feasibility validation reports clear errors such as:

- participant has no eligible recipients
- participant has no eligible givers
- maximum allocation prevents sending/receiving 50
- compatibility graph cannot balance every participant to exactly 50 received

## Public Giving Tree pages

Every participant has a public page:

```text
/tree/{slug}
```

Examples:

```text
/tree/alex
/tree/charlie
/tree/john-smith
```

The public page shows only the participant's outgoing allocations for the current published quarter:

- participant name
- quarter label
- recipient names
- amount for each recipient
- total allocated
- mobile-friendly visual tree
- printable layout

Public pages do not require login and do not expose admin data, user accounts, emails, passwords, roles, or internal database IDs.

The public endpoint sends `X-Robots-Tag: noindex, nofollow`.

## API summary

Admin endpoints require authentication/admin permission.

```text
GET    /api/participants
POST   /api/participants
POST   /api/participants/bulk
PATCH  /api/participants/{id}
POST   /api/participants/{id}/deactivate
POST   /api/participants/{id}/reactivate
DELETE /api/participants/{id}

GET    /api/compatibility/rules
PUT    /api/compatibility/rules
POST   /api/compatibility/bulk-allow
POST   /api/compatibility/bulk-block
POST   /api/compatibility/clear
POST   /api/compatibility/copy
GET    /api/compatibility/groups
POST   /api/compatibility/groups
POST   /api/compatibility/groups/{id}/allow-all

GET    /api/quarters
POST   /api/quarters
PUT    /api/quarters/{id}/participants
POST   /api/quarters/{id}/validate
POST   /api/quarters/{id}/generate
POST   /api/quarters/{id}/regenerate
PATCH  /api/quarters/{id}/allocations/{allocation_id}
POST   /api/quarters/{id}/validate-draft
POST   /api/quarters/{id}/publish
GET    /api/quarters/{id}
```

Public endpoint:

```text
GET /api/public/tree/{slug}
```

## Migration

Alembic migration:

```text
backend/alembic/versions/0003_participants.py
```

It adds participants, compatibility rules/groups, quarter participants, draft/published status fields, and participant allocation columns.

Existing installs are also upgraded safely at startup with `ensure_participant_schema()` for deployments that rely on `Base.metadata.create_all()` instead of manually running Alembic.

Migration behaviour:

- existing `users` remain administrator/login accounts
- existing `department_members` become `participants`
- existing historical `giving_plans` are backfilled to participant IDs
- existing teams/team groups are not deleted automatically
- existing historical data is preserved

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

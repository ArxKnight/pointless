# Pointless

<p align="center">
  <img src="frontend/public/assets/branding/pointless_logo.png" alt="Pointless logo" width="520">
</p>

Because patterns raise questions. Self-hosted FastAPI + React app in one Docker container, with MySQL as the persistent database.

## Core purpose

An administrator manages quarterly points distributions:

1. Add distribution participants by typing or pasting names.
2. Configure who can reasonably give points to whom.
3. Select participants for a quarter.
4. Generate and activate a balanced distribution.
5. Participants open their public Giving Tree page at `/{slug}`.

Only administrators need login accounts. Participants do **not** need usernames, passwords, emails, roles, or app accounts.

## Published Docker image

Prebuilt single-container app image on Docker Hub:

```text
arxknight/pointless:latest
arxknight/pointless:0.5.6
```

The app container includes Nginx serving the React frontend and FastAPI behind `/api`. MySQL remains a separate persistent database.

The Docker Hub image is published for both `linux/amd64` and `linux/arm64`, so it can run on standard x86 servers and ARM64 NAS devices such as UGREEN NAS systems.

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
- audit log review

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

Administrators can manage participants from **Participants** in the main navigation:

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
Participant A -> /participant-a
Participant F -> /participant-f
Participant A -> /participant-a-2
```

Renaming a participant does not automatically change their slug. If the slug is edited, the old slug is retained as a redirect record where practical.

## Compatibility

Permanent teams and team groups are deprecated from the core workflow.

Compatibility is now represented with direct participant-to-participant rules:

- `Allowed`
- `Blocked`
- unset/no rule

Rules are stored directionally so future one-way compatibility can be supported. The UI edits rules mutually by default.

Administrators can use the compatibility grid on **Participants** to click matrix cells or bulk-allow selected participants. Permanent teams and team groups are no longer shown in the main UI.

## Audit log

Administrators can review recent activity from **Audit Log** in the main navigation. The audit log records:

- admin account creation, updates and deactivation
- participant creation, updates, deletion and deactivation/reactivation
- compatibility rule changes
- quarter generation, publishing, completion and deletion
- public link views, counted without requiring visitor identity
- SMTP and access-control setting changes
- admin invite creation, revocation and acceptance

## Quarters and publishing

Quarters now have statuses:

- `created`
- `generating`
- `published`
- `completed`

Public Giving Tree pages show the published quarter for the current calendar period.

Workflow:

1. Open **Manage Quarters**.
2. Choose the quarter and selected participants.
3. Generate the quarter.
4. The app validates, generates, and activates/publishes the quarter in one flow.
5. Open the generated quarter to review allocations, or delete it before ledger history exists if it needs replacing.

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

### Randomness and repeatability

Generation is randomised, but it is still constrained: random choices can change *which* valid allocation is selected, but they cannot override compatibility rules or the exact 50-points-sent/50-points-received totals.

- If a seed is supplied when generating a quarter, the same participants, compatibility rules, history and seed will produce the same allocation. This is useful for debugging or reproducing a result.
- If no seed is supplied, the backend creates a fresh pseudo-random generator for that run, so repeated generation attempts can produce different valid allocations.
- Randomness is used to shuffle participant order, allowed edge order, split-pattern order and tie-breaks between otherwise similar candidate allocations.
- The solver favours variety rather than pure randomness. It applies soft penalties to less desirable but valid shapes, such as repeated recent pairings, reciprocal mirror pairings, single-recipient allocations and identical/even split patterns.
- Recent history is treated as a preference, not an absolute ban: the generator tries to avoid recent pairings, but it may reuse them if the compatibility graph is tight and reuse is required to make everyone balance exactly.
- The final allocation is always validated after generation, so random selection cannot save an invalid plan.

Feasibility validation reports clear errors such as:

- participant has no eligible recipients
- participant has no eligible givers
- maximum allocation prevents sending/receiving 50
- compatibility graph cannot balance every participant to exactly 50 received

## Public Giving Tree pages

Every participant has a public page:

```text
/{slug}
```

Examples:

```text
/participant-a
/participant-b
/participant-f
```

The public page shows the participant's outgoing and incoming allocations for the current published quarter:

- participant name
- quarter label
- recipient names
- amount for each recipient
- total allocated
- sender names for incoming allocations
- total incoming
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
POST   /api/quarters/generate-activate
POST   /api/quarters/{id}/regenerate
GET    /api/quarters/{id}
DELETE /api/quarters/{id}
GET    /api/settings/access
PATCH  /api/settings/access
GET    /api/settings/smtp
PATCH  /api/settings/smtp
POST   /api/settings/smtp/test
GET    /api/audit-logs
POST   /api/auth/change-password
POST   /api/auth/password-reset/request
POST   /api/auth/password-reset/confirm
```

Password reset is available from the login page after an administrator configures **Settings → SMTP Settings**. Admins can also change their own password from **Settings → Administrators** while logged in.

Public endpoint:

```text
GET /api/public/{slug}
```

## Migration

Alembic migration:

```text
backend/alembic/versions/0003_participants.py
backend/alembic/versions/0004_admin_invitations.py
backend/alembic/versions/0005_audit_logs.py
```

It adds participants, compatibility rules/groups, quarter participants, created/generating/published status fields, admin invitations, audit logs, and participant allocation columns.

Existing installs are also upgraded safely at startup with `ensure_participant_schema()`, `ensure_admin_schema()`, `ensure_password_reset_schema()` and `ensure_audit_schema()` for deployments that rely on `Base.metadata.create_all()` instead of manually running Alembic.

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
docker build -t arxknight/pointless:latest .
docker push arxknight/pointless:latest
```

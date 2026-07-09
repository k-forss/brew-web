# Brew-Web

[![Version](https://img.shields.io/badge/version-v1.4.0-blue)](#)
[![Docker](https://img.shields.io/badge/built%20with-Docker-blue)](#)
[![Flask](https://img.shields.io/badge/framework-Flask-yellow)](#)
[![License](https://img.shields.io/badge/license-MIT-green)](#)
[![Status](https://img.shields.io/badge/status-stable-brightgreen)](#)

Self-hosted web app for managing mead brewing recipes, batches, and calculators.

---

## Quick Start

[![Docker Compose](https://img.shields.io/badge/Setup-Docker%20Compose-informational)](#)

### Requirements
- Docker and Docker Compose
- `.env` in the project root (copy `.env.example`) with `SECRET_KEY` set
- **Before upgrading:** create a fresh SQL backup from `/settings/admin` (Export). The importer rewrites schemas and reseeds data to support old dumps, so keep a rollback handy.

### Installation
```bash
wget https://github.com/anndrox/brew-web/raw/main/brew-web.zip

unzip brew-web.zip -d .
cd brew-web

cp .env.example .env
$EDITOR .env   # set SECRET_KEY

docker compose up -d --build
```
Access at http://localhost:4452

> Imports from older backups now run schema repairs and yeast seeding automatically; no manual steps needed.

---

## Authentication & Security
- Run `/setup` on first start.
- Admin/user management via `/settings/admin`.
- Force password reset: create `/instance/force_reset.flag`.
- Keep behind TLS proxy; don't expose 4452 directly.
- Store secrets only in `.env`; rotate `SECRET_KEY` for production.
- CSRF and login protection are enabled by default.

### OIDC SSO Configuration

When `OIDC_ENABLED=true`, you **MUST** configure the following environment variables:

- `OIDC_ADMIN_GROUPS`: Comma-separated list of OIDC groups that should get admin role (e.g., `brew-admins`)
- `OIDC_EDITOR_GROUPS`: Groups that should get editor role
- `OIDC_USER_GROUPS`: Groups that should get user role (fallback)
- `OIDC_DEFAULT_ROLE`: Default role if user's groups don't match (default: `user`)
- `OIDC_ALLOW_UNMAPPED_USERS`: Allow users without matching groups to get default role (default: `false`)

**Security Note**: `OIDC_ALLOW_UNMAPPED_USERS` defaults to `false` to prevent unauthorized access. If your IdP is misconfigured, users without proper group memberships will be denied access rather than granted a default role.

**OIDC_ADMIN_GROUPS is required** - Without this, no users will get admin privileges via OIDC.

### OIDC Authority Principle

When OIDC mode is enabled:
- **ALL roles come from OIDC tokens** - no local overrides
- **NO "first user is admin" logic** - the first OIDC user does NOT automatically become admin
- **Mutually exclusive with local auth** - you cannot use both OIDC and local login simultaneously

### Breaking Changes (v1.4.0+)

**R1: Calendar API now requires CSRF tokens**

All calendar API endpoints (`POST /calendar-event`, `PUT /calendar-event/<id>`, `DELETE /calendar-event/<id>`) now require CSRF token validation.

If you have custom JavaScript integrations that call these endpoints directly, you must:

1. Fetch the CSRF token from the `/calendar` page (it's available as `csrf_token` in the template context)
2. Include it in your AJAX requests:
   ```javascript
   fetch('/calendar-event', {
     method: 'POST',
     headers: {
       'Content-Type': 'application/json',
       'X-CSRFToken': csrf_token  // or 'X-Requested-With': 'XMLHttpRequest'
     },
     body: JSON.stringify({...})
   })
   ```

Alternatively, set `X-Requested-With: XMLHttpRequest` header for CSRF validation to pass.

**Note**: CSRF protection is enabled on all routes. There are no CSRF exemptions in this version.

### Migration Notes

**Role migration** - The `viewer` role has been migrated to `user`. All existing users with role `viewer` are now `user`.

**Legacy Alembic reset** - If upgrading from a version with unknown Alembic revisions, the migration system will automatically reset the `alembic_version` table and reapply migrations. This is safe but may take extra time on first startup after upgrade.

**No hybrid mode** - OIDC and local authentication are mutually exclusive. When OIDC is enabled, local login is disabled. Existing local accounts remain but cannot be used while OIDC is active.

---

## Features
- ✓ Recipe scaling with structured ingredients
- ✓ Batch logging with gravities, honey, and notes
- ✓ Built-in brewing calculators:
  - ABV, **Target ABV**, TOSNA, dilution, sweetness, carbonation, temp correction, volume recovery, honey required
- ✓ Yeast reference guide
- ✓ Batch calendar tracker
- ✓ Role-based admin management
- ✓ Full PostgreSQL backup & restore
- ✓ Settings: theme, font, security
- ✓ Global unit preference (imperial/metric); recipes, forms, and calculators honor it

---

## Backup & Restore
[![Database](https://img.shields.io/badge/PostgreSQL-Export%2FImport-success)](#)

- **Export:** `/export-db` (admin) → saves to `/backups`
- **Import:** upload `.sql` via `/settings/admin`; runs in background with status page. Schema fixes and yeast reseed run automatically, even if Alembic revisions are missing.
- **Always export before upgrading** so you can roll back quickly.
- Safe for `docker compose down -v && up --build` cycles.

---

## Configuration
[![Configurable](https://img.shields.io/badge/Config-.env%20%2B%20docker--compose.yml-yellow)](#)

Key env:
```env
SECRET_KEY=changeme-in-production

OIDC_ENABLED=true
OIDC_DISCOVERY_URL=https://idp.example/.well-known/openid-configuration
OIDC_CLIENT_ID=brew-web
OIDC_CLIENT_SECRET=replace-me
OIDC_SCOPES=openid profile email groups
OIDC_GROUPS_CLAIM=groups

OIDC_ROLE_CLAIM=groups
OIDC_ADMIN_GROUPS=brew-admins
OIDC_EDITOR_GROUPS=brew-editors
OIDC_USER_GROUPS=brew-users
OIDC_DEFAULT_ROLE=user
OIDC_ALLOW_UNMAPPED_USERS=true

# DISABLE_LOCAL_LOGIN is computed automatically: it equals true when OIDC is
# configured and false otherwise. It is not a configurable environment variable.
LOCAL_USER_ROLES=admin,editor,user
```

- Brew stores internal roles as `admin`, `editor`, and `user`.
- OIDC role routing is env-driven: `OIDC_ROLE_CLAIM` selects the claim to inspect, and `OIDC_*_GROUPS` map external values to Brew roles.
- `OIDC_DEFAULT_ROLE` and `OIDC_ALLOW_UNMAPPED_USERS` control what happens when the configured claim does not match an explicit route.
- `LOCAL_USER_ROLES` controls which roles the admin UI can create for local accounts.

---

## Project Structure
[![Structure](https://img.shields.io/badge/Folder%20Layout-Described-lightgrey)](#)
```
brew-web/
├─ app/
│  ├─ templates/
│  ├─ static/
│  ├─ routes/
│  └─ models.py
├─ backups/
├─ config.py
├─ docker-compose.yml
├─ Dockerfile
└─ README.md
```

---

## Dev Tips
- Reset environment:
  ```bash
  docker compose down -v && docker compose up --build
  ```
- Customize UI: edit `base.html`, `admin.html`, `static/style.css`
- Logs: `/logs/brewweb.log`

---

Recent maintenance and import hardening provided with assistance from Codex.

# P1.1 Development Preview Runbook

## Status

- Lifecycle: `ACCEPTANCE_EVIDENCE`
- Scope: local P1.1 preview only
- Production use: forbidden

## Initialize Once

Run from the repository root:

```powershell
scripts\initialize-p1-1-preview.ps1
```

The script:

- prompts without echo for four passwords;
- requires two administrators, one implementation engineer and one auditor;
- creates `data/control-plane.db`;
- creates ignored `.env.p1-1-preview` with a randomly generated root key;
- never prints passwords or the root key;
- refuses implicit production bootstrap.

Do not commit, attach, upload or place `.env.p1-1-preview` in an evidence package.

## Start Locally

Docker is not required for the P1.1 development preview. Start the API in the
first PowerShell terminal:

```powershell
scripts\start-p1-1-local-api.ps1
```

The launcher reads only the allowlisted preview settings, overrides the
container database path with the absolute local `data/control-plane.db` path
and never prints the root key.

Start the web application in a second PowerShell terminal:

```powershell
Set-Location apps/web
pnpm install --frozen-lockfile
pnpm dev
```

Open:

```text
http://localhost:18000/manage
```

Stop both foreground processes with `Ctrl+C`.

## Optional Docker Preview

The candidate Docker build and isolated API/web runtime smoke have passed. Docker
is the preferred customer-delivery packaging path, but it remains optional for
local development.

```powershell
docker compose --env-file .env.p1-1-preview up --build
```

The same entry point is used:

```text
http://localhost:18000/manage
```

The browser uses a `Secure` host-only cookie. Standard production must run behind HTTPS. Localhost handling is only development-preview convenience and is not production transport evidence.

## Core Walkthrough

1. Sign in as `admin-a`.
2. Open 用户与角色 and submit a typed user creation. Record the returned action ID.
3. Sign out and sign in as `admin-b`.
4. Open 独立审批 and approve the exact action. Approval creates no user.
5. Sign in again as `admin-a`, enter the same user fields plus the approved action ID and execute.
6. Confirm the created record is `PROVISIONING`, disabled and has an empty role set.
7. Sign in as `auditor`, open 安全审计, and confirm 用户与角色 / 独立审批 / device mutation reads are denied by the API.
8. Sign in as `implementation`, request enrollment for `screen-trust-fixture`, have an administrator approve it, then resubmit the same request.
9. Use the displayed one-time enrollment material immediately. It is kept only in current page memory.
10. Rotate the returned device credential and call 认证并激活 with the successor.
11. As an administrator, load credential metadata, request whole-family revocation, have the other administrator approve, then execute the identical revoke.
12. Issue and claim a new enrollment for the same screen. Confirm the old family remains terminal and a distinct new family is the only active family.

Created network users intentionally remain non-authoritative `PROVISIONING` records in this batch. Production custodian/person binding, credential setup, role replacement and enabling are not simulated by a privileged fallback endpoint.

Stop the Docker alternative with:

```powershell
docker compose --env-file .env.p1-1-preview down
```

## Reset A Local Preview

The initializer refuses to overwrite existing state. To reset, first stop the preview and move these two exact files to a separately named local archive outside the active paths:

```text
data/control-plane.db
.env.p1-1-preview
```

The store verifies named migration `001_initial_identity_device_trust` and its source checksum at startup. A database created by an earlier pre-candidate P1.1 implementation is intentionally rejected instead of being silently relabeled; archive it and initialize a fresh development preview.

Then run initialization again. Never delete or overwrite an unknown database or environment file.

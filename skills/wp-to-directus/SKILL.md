---
name: wp-to-directus
description: Use when migrating content from a WordPress site to Directus headless CMS. Given WP and Directus connection credentials, drives a resumable state machine through env validation, MCP server install (with explicit Claude restart handshake), schema creation, content migration, verification, and a post-migration markdown report. Supports a bundled Docker test stack via `mode=test`. Triggers on WordPress migration, CMS migration, headless CMS transition, wp_posts to Directus, content migration automation.
---

# WordPress -> Directus Migration (State-machine orchestrator)

## Overview

This skill migrates WordPress content (posts, pages, media, taxonomies, custom post_types, custom taxonomies, known meta_keys) to Directus via a hybrid approach:

- **Read WordPress** via direct MySQL subprocess (for bulk content migration) AND via `wordpress-mysql` MCP (for Claude-side introspection during discovery/verify).
- **Write Directus** via REST API only (never direct PostgreSQL writes).
- **Verify Directus** via `directus-postgres` MCP (read-only) where available, REST fallback otherwise.

Execution is organised as a **state machine** with a sentinel `awaiting_restart` phase so Claude can install MCP servers and then wait for the user to restart Claude Code and re-invoke the skill.

## State machine

State file: `state/.state.json` (relative to project root).

Phases (in order):

| # | Phase | Action | Script |
|---|-------|--------|--------|
| 1 | `init` | Create state.json, prompt for `MIGRATION_MODE` | SKILL.md |
| 2 | `env_check` | Validate `.env`, prompt missing vars; ping connections (skipped in test mode) | `scripts/env_check.py` |
| 3 | `mcp_install` | Generate `.mcp.json` (merge-safe) | `scripts/mcp_install.py` |
| 4 | `awaiting_restart` | **STOP** — user must restart Claude | SKILL.md |
| 5 | `docker_or_connect` | Sanity-check MCP available; `docker compose up -d` if mode=test | SKILL.md + scripts |
| 6 | `discovery` | Scan plugins, custom types/tax/meta, non-core tables | `scripts/discover.py` |
| 7 | `schema` | Create Directus collections + relations via REST | `scripts/schema.py` |
| 8 | `migrate` | Content migration (authors -> taxonomies -> media -> posts -> pages -> custom types -> M2M) | `scripts/migrate.py` |
| 9 | `verify` | Counts WP vs Directus + spot-check | `scripts/verify.py` |
| 10 | `report` | Generate `state/MIGRATION_REPORT.md` | `scripts/report.py` |
| 11 | `done` | Print path to report | SKILL.md |

All paths are relative to the **project root** (the directory where the user ran `setup.sh` and where `.env` / `docker-compose.yml` live). `setup.sh` copied scripts into `./scripts/` and created `./state/`.

## Router behaviour (read this when invoked)

On every invocation, Claude MUST:

1. Read `state/.state.json`. If missing, treat as `phase=init`.
2. Look up the current phase in the table above.
3. Execute the corresponding script (or SKILL.md-driven action) exactly once.
4. Print a one-line status update.
5. If phase is `awaiting_restart`, **stop** — do NOT attempt to continue. Print the restart handshake message and return control to the user.
6. Otherwise, re-read state and recurse to the next phase — but only if the just-completed phase advanced the `phase` field in the state file.

## Per-phase router instructions

When invoked, read `state/.state.json` from the project root. Follow the per-phase instruction below for the current `phase` value, then re-read state and continue.

### `init`
- Ask the user: "Choose mode: (1) test [bundled Docker stack] or (2) external [your WP+Directus]?"
- Update state.json: set `mode` to `"test"` or `"external"`, set `phase=env_check`.

### `env_check`
Run (from the project root):
```
export $(grep -v '^#' .env 2>/dev/null | xargs -d '\n' 2>/dev/null) ; \
python3 scripts/env_check.py \
  --mode "$(python3 -c 'import json; print(json.load(open("state/.state.json"))["mode"])')" \
  --env-file .env \
  --state-file state/.state.json
```
In test mode, ping is intentionally skipped — services are not up yet. On exit 0, state advances to `mcp_install`. On non-zero, ask user to fix `.env` and re-invoke skill.

### `mcp_install`
Run:
```
python3 scripts/mcp_install.py \
  --env-file .env \
  --mcp-file .mcp.json \
  --state-file state/.state.json
```
Script sets `phase=awaiting_restart` and prints the Italian handshake message. **STOP HERE.** Do NOT call any further tools this turn. Return control to the user.

### `awaiting_restart`
- If this phase is read AT SKILL INVOCATION (i.e., user just restarted and re-invoked), verify MCP tools are loaded. Claude Code exposes MCP tools under names like `mcp__<server>__<tool>`. Check your available tools list for names starting with `mcp__wordpress-mysql` or `mcp__directus-postgres`.
- If MCP tools are NOT found: print "MCP tools not detected — verify Claude was restarted after `mcp_install`. State stays at `awaiting_restart`." and STOP.
- If MCP tools ARE found: set `phase=docker_or_connect` in state.json and continue.

### `docker_or_connect`
- If `mode == "test"`: run `docker compose up -d` and wait ~25s for Directus to bootstrap. Ping Directus: `curl -s http://localhost:8055/server/ping` must return `pong`. Also run `bash scripts/seed-wordpress.sh` if the seed has not been applied (idempotency: WP-CLI commands error out if objects already exist — safe to re-run).
- If `mode == "external"`: ping WP MySQL and Directus REST using credentials from .env.
- On success: set state.json `checkpoints.docker_up=true`, `phase=discovery`.

### `discovery`
Run:
```
export $(grep -v '^#' .env | xargs -d '\n') ; \
python3 scripts/discover.py \
  --state-file state/.state.json \
  --discovery-file state/discovery.json \
  $([ "$(jq -r .mode state/.state.json)" = "test" ] && echo "--wp-docker-service wordpress_db")
```
Script advances `phase=schema` on completion.

### `schema`
Run:
```
export $(grep -v '^#' .env | xargs -d '\n') ; \
python3 scripts/schema.py \
  --state-file state/.state.json \
  --discovery-file state/discovery.json
```
Script advances `phase=migrate`.

### `migrate`
Run:
```
export $(grep -v '^#' .env | xargs -d '\n') ; \
PYTHONUNBUFFERED=1 python3 scripts/migrate.py \
  --state-file state/.state.json \
  --mapping-file state/mappings.json \
  --discovery-file state/discovery.json \
  $([ "$(jq -r .mode state/.state.json)" = "test" ] && echo "--wp-docker-service wordpress_db")
```
Script advances `phase=verify`. Long-running (minutes to tens of minutes per API-call budget).

### `verify`
Run:
```
export $(grep -v '^#' .env | xargs -d '\n') ; \
python3 scripts/verify.py \
  --state-file state/.state.json \
  --verify-file state/verify.json \
  --discovery-file state/discovery.json \
  $([ "$(jq -r .mode state/.state.json)" = "test" ] && echo "--wp-docker-service wordpress_db")
```
Script advances `phase=report`. Exit code non-zero means post/page counts mismatch (flag in report but continue).

### `report`
Run:
```
python3 scripts/report.py \
  --state-file state/.state.json \
  --discovery-file state/discovery.json \
  --verify-file state/verify.json \
  --output state/MIGRATION_REPORT.md
```
Script advances `phase=done`.

### `done`
Print: `Migrazione completa. Report: state/MIGRATION_REPORT.md`.

## First-time setup

From project root:

```bash
bash .claude/skills/wp-to-directus/setup.sh
```

This copies `docker-compose.yml`, `.env` (from template), `scripts/` into the project root, and ensures the `state/` directory exists. It does NOT create `.mcp.json` — the skill does that during `mcp_install`.

Edit `.env` and set `MIGRATION_MODE=test` (to use the bundled Docker stack) or `MIGRATION_MODE=external` (to point at a live WP/Directus you manage).

## Mode: test

- Uses the bundled `docker-compose.yml` (WordPress + MySQL + Directus + PostgreSQL).
- `env_check` auto-validates all test credentials.
- Phase `docker_or_connect` runs `docker compose up -d` if the stack is not already up.
- `seed-wordpress.sh` (bundled) populates WordPress with a deterministic dataset (5 posts, 3 pages, 3 categories, 5 tags, 2 events custom post_type, 2 active fake plugins). Run it manually after the stack starts — the skill does NOT auto-seed.

## Mode: external

- User supplies `.env` with real WP+Directus credentials.
- Directus Postgres read-only user (`DIRECTUS_DB_*`) is optional; if absent, `verify` degrades to REST-only.
- To create the read-only user on your Directus PostgreSQL:

```sql
CREATE USER directus_readonly WITH PASSWORD '<pwd>';
GRANT CONNECT ON DATABASE directus TO directus_readonly;
GRANT USAGE ON SCHEMA public TO directus_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO directus_readonly;
```

## Restart handshake

Phase `mcp_install` writes `.mcp.json` then sets state to `awaiting_restart`. The skill will print:

```
AZIONE MANUALE RICHIESTA
...
  1. Esci da questa sessione Claude Code
  2. Riavvia: claude --continue
  3. Ri-invoca: /wp-to-directus
```

State is saved in `state/.state.json` under the project root — the skill resumes automatically from the next phase on re-invocation.

Claude MUST NOT call any tool after this message in the same turn. The user performs the restart. On next invocation, the sanity check in `docker_or_connect` confirms MCP tools are loaded and the skill resumes.

## Resumability

- Each phase checks its checkpoint in `state.json` and skips completed work.
- Within `migrate`, sub-checkpoint counters (`media_done_count`, `posts_done_count`, etc.) allow mid-batch resume.
- Idempotency is enforced via `MappingStore` — each insert checks `ms.get(collection, wp_id)` and skips if already migrated. `_rebuild_map` runs at the start of each phase to resync from Directus (so deleted `mappings.json` is recovered from `wp_original_id` field in Directus items).
- Junction tables pre-check existing pairs to avoid duplicates.

## Critical pitfalls (unchanged — see scripts for implementation)

1. **HTML content with newlines**: use `JSON_OBJECT()` + `mysql --batch --raw`.
2. **Python on Windows**: `PYTHONIOENCODING=utf-8`, `PYTHONUNBUFFERED=1`, `sys.stdout.reconfigure`.
3. **Media Docker URL**: replace `WP_SITE_URL` with `WP_INTERNAL_URL` in test mode.
4. **M2M creation**: alias field + two relations (3 calls total).
5. **Junction duplicates**: pre-check pair existence before POST.
6. **PHP-serialized meta**: detect `a:`/`s:` prefix, parse basic arrays, else raw.
7. **Directus API latency (~3s/call)**: report warns if migration exceeds 15 min.

## Output

After `done`, the report is at `state/MIGRATION_REPORT.md` (under the project root — the script writes wherever `--output` points).

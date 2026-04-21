---
name: fe-from-migration
description: Use when generating a React+Vite frontend from a Directus instance populated by the wp-to-directus skill, reproducing style and structure of the original WordPress site. Drives a resumable state machine through fetch, analysis, scaffold, component generation, verify and report.
---

# fe-from-migration — React+Vite frontend from Directus (state-machine orchestrator)

## Overview

Generate a React 18 + Vite + TypeScript + Tailwind + Vike + TanStack Query frontend in `./frontend/` from:
- a Directus instance (populated by `wp-to-directus` or externally)
- the original WordPress source (live URL, static dump, or Docker container)

Execution is a **state machine**. State file: `.claude/skills/fe-from-migration/state/.state.json`.

## State machine

| # | Phase | Action |
|---|-------|--------|
| 1 | `init` | Prompt mode (test/external), create state.json |
| 2 | `env_check` | Validate .env, ping Directus + WP source |
| 3 | `mcp_install` | Write .mcp.json (optional directus-postgres) |
| 4 | `awaiting_restart` | STOP — user restarts Claude |
| 5 | `docker_detect` | Mode=test: verify wp-to-directus stack up |
| 6 | `fetch_wp` | Scrape HTML+CSS for every WP route → state/wp_dump/ |
| 7 | `analyze_style` | Extract design tokens → state/tokens.json |
| 8 | `introspect_directus` | REST collections+fields → state/schema.json |
| 9 | `gen_scaffold` | Jinja2 templates → ./frontend/ (no LLM) |
| 10 | `gen_atoms` | Parallel subagents generate atom TSX |
| 11 | `gen_molecules` | Parallel subagents compose molecules |
| 12 | `gen_pages` | Parallel subagents generate page TSX |
| 13 | `gen_i18n` | Polylang/WPML → locales/*.json |
| 14 | `verify` | tsc + eslint + npm run build |
| 15 | `report` | Generate FRONTEND_REPORT.md |
| 16 | `done` | Print path to report |

## Router behavior (read this when invoked)

On every invocation, Claude MUST:

1. Read `.claude/skills/fe-from-migration/state/.state.json`. If missing, treat as `phase=init`.
2. Look up current phase in the table above.
3. Execute the corresponding script or SKILL.md-driven action exactly once.
4. Print a one-line Italian status update.
5. If phase is `awaiting_restart`, STOP — do NOT continue. Print restart handshake and return control.
6. Otherwise re-read state and continue to next phase — only if phase advanced.

**Placeholder resolution:** `<PROJECT_DIR>` in the bash blocks below refers to the current working directory, which must contain `.claude/skills/fe-from-migration/`. Before running any phase command, `cd` into this directory.

## Per-phase router instructions

### `init`
Ask user: "Scegli modalità: (1) test [usa stack Docker di wp-to-directus] o (2) external [tuo Directus]?"
Update state: `mode`=test/external, `phase`=env_check.

### `env_check`
Run:
```
cd <PROJECT_DIR> && python3 .claude/skills/fe-from-migration/scripts/env_check.py \
  --mode "$(python3 -c 'import json; print(json.load(open(".claude/skills/fe-from-migration/state/.state.json"))["mode"])')" \
  --env-file .env \
  --state-file .claude/skills/fe-from-migration/state/.state.json
```
On exit 0 → state advances to `mcp_install`. Non-zero → ask user to fix .env.

### `mcp_install`
Run:
```
cd <PROJECT_DIR> && python3 .claude/skills/fe-from-migration/scripts/mcp_install.py \
  --env-file .env \
  --mcp-file .mcp.json \
  --state-file .claude/skills/fe-from-migration/state/.state.json
```
Script sets `phase=awaiting_restart` + prints Italian handshake. **STOP.** Do NOT call further tools this turn.

### `awaiting_restart`
- If read at skill invocation (user just restarted): verify MCP tools loaded. Check tool names starting with `mcp__directus-postgres`.
- If MCP tools NOT found: print "MCP tools non rilevati — verifica riavvio Claude dopo `mcp_install`. Stato resta `awaiting_restart`." and STOP.
- If MCP tools found: set `phase=docker_detect` and continue.

### docker_detect

If mode==test: run this bash block and parse output:

```bash
docker ps --format '{{.Names}}|{{.Status}}' | awk -F'|' '/wordpress|directus/ {print}'
```

Check that both a `wordpress*` and `directus*` container are present with `Up` status.

- If BOTH present: update state `checkpoints.docker_ok=true`, also write `WP_INTERNAL_URL=http://wordpress:80` into `.env` if container named `wordpress` (use `echo "WP_INTERNAL_URL=..." >> .env` guarded by grep-check so it's not duplicated on resume), set `phase=fetch_wp`.
- If missing: print "Stack wp-to-directus non rilevato. Esegui prima `/wp-to-directus` in modalità test." and STOP.

If mode==external: ping Directus via curl:

```bash
curl -s -o /dev/null -w "%{http_code}" "$DIRECTUS_URL/server/ping"
```

Expected: `200`. Otherwise print error and STOP. On success set `phase=fetch_wp`.

### `fetch_wp`
Run:
```
cd <PROJECT_DIR> && python3 .claude/skills/fe-from-migration/scripts/fetch_wp.py \
  --state-file .claude/skills/fe-from-migration/state/.state.json \
  --env-file .env \
  --dump-dir .claude/skills/fe-from-migration/state/wp_dump \
  --routes-file .claude/skills/fe-from-migration/state/routes.json \
  --forms-file .claude/skills/fe-from-migration/state/forms.json
```
Script advances `phase=analyze_style`.

### `analyze_style`
Run:
```
cd <PROJECT_DIR> && python3 .claude/skills/fe-from-migration/scripts/analyze_style.py \
  --state-file .claude/skills/fe-from-migration/state/.state.json \
  --dump-dir .claude/skills/fe-from-migration/state/wp_dump \
  --tokens-file .claude/skills/fe-from-migration/state/tokens.json \
  --global-css .claude/skills/fe-from-migration/state/global.css
```
Script advances `phase=introspect_directus`.

### `introspect_directus`
Run:
```
cd <PROJECT_DIR> && python3 .claude/skills/fe-from-migration/scripts/introspect.py \
  --state-file .claude/skills/fe-from-migration/state/.state.json \
  --env-file .env \
  --schema-file .claude/skills/fe-from-migration/state/schema.json
```
Script advances `phase=gen_scaffold`.

### gen_scaffold
Run:
```
cd <PROJECT_DIR> && python3 .claude/skills/fe-from-migration/scripts/gen_scaffold.py \
  --state-file .claude/skills/fe-from-migration/state/.state.json \
  --tokens-file .claude/skills/fe-from-migration/state/tokens.json \
  --schema-file .claude/skills/fe-from-migration/state/schema.json \
  --global-css .claude/skills/fe-from-migration/state/global.css \
  --routes-file .claude/skills/fe-from-migration/state/routes.json \
  --templates-dir .claude/skills/fe-from-migration/templates \
  --output-dir ./frontend
```
Script advances `phase=gen_atoms`.

### gen_atoms

**Step 1 — detection (Python):**

Run:
```
cd <PROJECT_DIR> && python3 .claude/skills/fe-from-migration/scripts/detect_atoms.py \
  --dump-dir .claude/skills/fe-from-migration/state/wp_dump \
  --registry-file .claude/skills/fe-from-migration/state/atom_registry.json \
  --state-file .claude/skills/fe-from-migration/state/.state.json \
  --min-occurrences 3
```

**Step 2 — subagent dispatch:**

Read `.claude/skills/fe-from-migration/state/atom_registry.json`. For each atom in `atoms` array:

1. Check `.claude/skills/fe-from-migration/state/.state.json` `checkpoints.atoms`. Skip atoms already completed.
2. Read `.claude/skills/fe-from-migration/state/tokens.json`.
3. Read prompt template from `.claude/skills/fe-from-migration/subagent_prompts/gen_atom.md`.
4. Substitute placeholders: `{NAME}` ← atom.name, `{SAMPLE_HTML}` ← atom.sample_html, `{TOKENS_JSON}` ← tokens JSON stringified, `{OUTPUT_PATH}` ← atom.output_path.

**Dispatch in parallel batches of 5** using `superpowers:dispatching-parallel-agents`:

```
Use dispatching-parallel-agents with 5 concurrent agents. For each remaining atom:
  - subagent_type: "general-purpose"
  - description: "gen atom <name>"
  - prompt: the filled template from gen_atom.md
  - isolation: NOT used (subagents write directly to ./frontend/)
```

Wait for all agents in batch. For each atom:

- If output file exists at `atom.output_path`: mark checkpoint via `python3 .claude/skills/fe-from-migration/scripts/mark_done.py --state-file <...> --bucket atoms --item <name>`
- If output missing OR file fails `tsc --noEmit`: retry once with feedback "errore tsc: <errors>". After 2nd failure, mark `atoms_failed` bucket and continue.

**Step 3 — finalize:**

```
python3 .claude/skills/fe-from-migration/scripts/verify_generated.py \
  --output-dir ./frontend \
  --pattern "src/components/atoms/*.tsx" \
  --registry-file .claude/skills/fe-from-migration/state/atom_registry.json \
  --state-file .claude/skills/fe-from-migration/state/.state.json \
  --next-phase gen_molecules \
  --fail-threshold 0.2
```

Script: se >20% atoms falliti → exit non-zero e phase non avanza. Altrimenti advance `phase=gen_molecules`.

### gen_molecules

**Step 1 — detection:**

```
cd <PROJECT_DIR> && python3 .claude/skills/fe-from-migration/scripts/detect_molecules.py \
  --dump-dir .claude/skills/fe-from-migration/state/wp_dump \
  --atoms-registry .claude/skills/fe-from-migration/state/atom_registry.json \
  --registry-file .claude/skills/fe-from-migration/state/molecule_registry.json \
  --state-file .claude/skills/fe-from-migration/state/.state.json \
  --min-occurrences 2
```

**Step 2 — subagent dispatch:**

Same pattern as gen_atoms but using `subagent_prompts/gen_molecule.md`. Substitutions: `{NAME}`, `{SAMPLE_HTML}`, `{ATOMS_REGISTRY_JSON}` (content of `state/atom_registry.json`), `{TOKENS_JSON}`, `{OUTPUT_PATH}`.

Max 5 concurrent agents.

**Step 3 — verify:**

```
python3 .claude/skills/fe-from-migration/scripts/verify_generated.py \
  --output-dir ./frontend \
  --pattern "src/components/molecules/*.tsx" \
  --registry-file .claude/skills/fe-from-migration/state/molecule_registry.json \
  --state-file .claude/skills/fe-from-migration/state/.state.json \
  --next-phase gen_pages \
  --fail-threshold 0.2
```

### gen_pages

**Step 1 — batch preparation:**

```
cd <PROJECT_DIR> && python3 .claude/skills/fe-from-migration/scripts/prepare_pages_batch.py \
  --routes-file .claude/skills/fe-from-migration/state/routes.json \
  --dump-dir .claude/skills/fe-from-migration/state/wp_dump \
  --schema-file .claude/skills/fe-from-migration/state/schema.json \
  --molecules-registry .claude/skills/fe-from-migration/state/molecule_registry.json \
  --batch-file .claude/skills/fe-from-migration/state/pages_batch.json \
  --state-file .claude/skills/fe-from-migration/state/.state.json
```

**Step 2 — subagent dispatch:**

Read `state/pages_batch.json` (list of {name, route_slug, html, collection, molecules, output_path}). For each entry, fill `subagent_prompts/gen_page.md` and dispatch max 5 concurrent agents.

**Step 3 — verify:**

```
python3 .claude/skills/fe-from-migration/scripts/verify_generated.py \
  --output-dir ./frontend \
  --pattern "pages/**/+Page.tsx" \
  --registry-file .claude/skills/fe-from-migration/state/pages_batch.json \
  --state-file .claude/skills/fe-from-migration/state/.state.json \
  --next-phase gen_i18n \
  --fail-threshold 0.2
```

### gen_i18n

Run:
```
cd <PROJECT_DIR> && python3 .claude/skills/fe-from-migration/scripts/gen_i18n.py \
  --env-file .env \
  --state-file .claude/skills/fe-from-migration/state/.state.json \
  --output-dir ./frontend
```
Script avanza `phase=verify` (skip se nessun multi-lingua rilevato).

### verify

Run:
```
cd <PROJECT_DIR> && python3 .claude/skills/fe-from-migration/scripts/verify.py \
  --state-file .claude/skills/fe-from-migration/state/.state.json \
  --verify-file .claude/skills/fe-from-migration/state/verify.json \
  --output-dir ./frontend
```
Exit 0 → phase avanza a `report`. Exit non-zero → phase resta `verify`. Stampa sintesi errori e istruisce user a fixare manualmente o re-invocare dopo fix.

### report

Run:
```
cd <PROJECT_DIR> && python3 .claude/skills/fe-from-migration/scripts/report.py \
  --state-file .claude/skills/fe-from-migration/state/.state.json \
  --routes-file .claude/skills/fe-from-migration/state/routes.json \
  --forms-file .claude/skills/fe-from-migration/state/forms.json \
  --verify-file .claude/skills/fe-from-migration/state/verify.json \
  --atoms-registry .claude/skills/fe-from-migration/state/atom_registry.json \
  --molecules-registry .claude/skills/fe-from-migration/state/molecule_registry.json \
  --pages-batch .claude/skills/fe-from-migration/state/pages_batch.json \
  --output-dir ./frontend \
  --templates-dir .claude/skills/fe-from-migration/report_templates \
  --report-file FRONTEND_REPORT.md
```
Script avanza `phase=done`.

### done

Print: `Generazione frontend completa. Report: FRONTEND_REPORT.md`

#!/usr/bin/env bash
# Copia scripts e struttura di fe-from-migration nella working directory progetto.
set -euo pipefail

SKILL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${1:-$(pwd)}"
TARGET="$PROJECT_ROOT/.claude/skills/fe-from-migration"

mkdir -p "$TARGET/scripts/lib"
mkdir -p "$TARGET/templates"
mkdir -p "$TARGET/subagent_prompts"
mkdir -p "$TARGET/state/wp_dump"

cp -r "$SKILL_ROOT/scripts/"* "$TARGET/scripts/"
cp -r "$SKILL_ROOT/templates/"* "$TARGET/templates/" 2>/dev/null || true
cp -r "$SKILL_ROOT/subagent_prompts/"* "$TARGET/subagent_prompts/" 2>/dev/null || true

if [ ! -f "$PROJECT_ROOT/.env" ]; then
  if [ -f "$SKILL_ROOT/../../.env.example" ]; then
    cp "$SKILL_ROOT/../../.env.example" "$PROJECT_ROOT/.env"
    echo "Creato $PROJECT_ROOT/.env da template. Completa le variabili."
  fi
fi

echo "Setup completato in $TARGET"

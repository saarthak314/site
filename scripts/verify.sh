#!/usr/bin/env bash
set -euo pipefail

uv run ruff check .
uv run ruff format --check .
uv run python -m unittest discover -s src -p 'test*.py'
uv run python -m compileall -q src
uv run sitegen build --no-incremental
uv run sitegen check

if grep -R -n -E '\{\{|\{%|\{#' docs --include='*.html'; then
  echo "unresolved template marker found"
  exit 1
fi

git diff --check

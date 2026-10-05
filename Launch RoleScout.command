#!/bin/zsh -l
# :A follows a Finder/Desktop symlink back to this project.
cd "${0:A:h}/backend" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  echo 'RoleScout needs initial setup: run uv sync in backend. See README.'
  read '?Press Enter to close.'
  exit 1
fi
if ! .venv/bin/python -m app.launcher; then
  read '?Press Enter to close.'
  exit 1
fi

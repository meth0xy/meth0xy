#!/bin/zsh
set -euo pipefail
cd "${0:A:h}"
git pull --ff-only --quiet
.venv/bin/python stats.py >/dev/null
.venv/bin/python build.py >/dev/null
git add assets README.md
git diff --cached --quiet && exit 0
git commit --quiet -m "chore: update store stats"
git push --quiet origin master

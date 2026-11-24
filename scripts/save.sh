#!/usr/bin/env bash
# Commit this run's changes and push them, even when another run pushed in the meantime.
# On a clash, this run's version of the clashing lines wins (it is the newest draft); everything else from both runs is kept.
# Tries 5 times, then gives up without leaving the repository half-merged.
msg="${1:-Autopilot update}"
git config user.name "arah-autopilot"
git config user.email "autopilot@users.noreply.github.com"
git rm -r -q --cached --ignore-unmatch "*__pycache__*" "*.pyc" >/dev/null 2>&1 || true   # Python temp files never belong in the repo (they caused save clashes)
git add -A
if git diff --cached --quiet; then echo "nothing new"; exit 0; fi
git commit -q -m "$msg"
for i in 1 2 3 4 5; do
  if git pull --rebase -X theirs -q; then
    if git push -q; then echo "saved: $msg"; exit 0; fi
  else
    git checkout --theirs -- . 2>/dev/null; git rm -r -q --cached --ignore-unmatch "*__pycache__*" "*.pyc" >/dev/null 2>&1
    if GIT_EDITOR=true git rebase --continue >/dev/null 2>&1 && git push -q; then echo "saved: $msg"; exit 0; fi
    git rebase --abort 2>/dev/null || true
  fi
  echo "someone else saved at the same time; trying again ($i)"
  sleep $((i * 7))
done
echo "could not save after 5 tries"; exit 1

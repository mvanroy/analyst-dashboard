#!/usr/bin/env bash
set -euo pipefail

approved_sha="${1:-}"
if [[ -z "$approved_sha" ]]; then
  echo "Usage: scripts/promote_staging_to_production.sh <approved-staging-commit>" >&2
  exit 2
fi

git fetch origin staging analyst-dashboard

staging_sha="$(git rev-parse origin/staging)"
production_sha="$(git rev-parse origin/analyst-dashboard)"
approved_sha="$(git rev-parse "$approved_sha")"

if [[ "$approved_sha" != "$staging_sha" ]]; then
  echo "Refusing promotion: approved commit is not the current staging commit." >&2
  echo "Approved: $approved_sha" >&2
  echo "Staging:  $staging_sha" >&2
  exit 1
fi

if ! git merge-base --is-ancestor "$production_sha" "$staging_sha"; then
  echo "Refusing promotion: production cannot fast-forward to staging." >&2
  echo "Production: $production_sha" >&2
  echo "Staging:    $staging_sha" >&2
  exit 1
fi

git push origin "$staging_sha:refs/heads/analyst-dashboard"
git fetch origin analyst-dashboard

deployed_sha="$(git rev-parse origin/analyst-dashboard)"
if [[ "$deployed_sha" != "$staging_sha" ]]; then
  echo "Promotion verification failed." >&2
  exit 1
fi

echo "Production source promoted to exact staging commit: $staging_sha"

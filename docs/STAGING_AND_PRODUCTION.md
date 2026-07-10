# Igby staging and production workflow

Igby has one responsive codebase. Desktop and mobile are tested from the same
staging deployment so a change is implemented only once.

## Environments

- `staging` Git branch -> Railway `staging` environment
- `analyst-dashboard` Git branch -> Railway `production` environment

All development and visual tuning must be committed to `staging`. Do not make a
second version of an approved change on the production branch.

## Approval checklist

1. Confirm the Railway staging deployment is online.
2. Record the full staging commit SHA.
3. Test the staging URL at desktop and mobile viewport sizes.
4. Obtain explicit approval for that commit.
5. Promote with:

   `scripts/promote_staging_to_production.sh <approved-staging-commit>`

The promotion command refuses to continue unless:

- the approved commit is the current remote `staging` commit; and
- production can fast-forward directly to that exact commit.

It then verifies that the remote production branch equals the approved staging
commit. No files are copied, recreated, cherry-picked, or recommitted during
promotion.

## Deployment verification

The shared page header includes a hidden `data-igby-build` attribute populated
from Railway's `RAILWAY_GIT_COMMIT_SHA`. Inspect this value on staging and
production to confirm which revision each environment is serving.

If a production-only emergency change is ever required, merge or fast-forward
that commit back into `staging` before resuming normal work. This preserves the
fast-forward-only guarantee.

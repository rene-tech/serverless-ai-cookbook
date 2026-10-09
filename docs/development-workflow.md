# Scientific AI development workflow

`main` is the only maintained local and personal-fork branch. This applies to
`rene-tech/nebius-solutions-library`, `rene-tech/serverless-ai-cookbook` and
`rene-tech/nebius-scientific-ai-platform`. Nebius-owned upstream repositories
are read-only for this consolidation. Do not create lasting `agent/`, task,
release, backup, rejected or per-review-version branches.

## Isolated work

Install repository-local guards once from the main checkout:

```sh
python3 scripts/single_main.py install
python3 scripts/single_main.py start /absolute/path/to/task-worktree
```

Task Deck uses detached worktrees when `scientificai.singlemain=true`. Old ticket
branch fields do not select the base; new tasks start at current `main`. Resume
an existing detached task without resetting its files or index. Do not start a
parallel writer in the main checkout. Commit in detached HEAD and retain its SHA.

## Integrate and close

One integrator owns main at a time. Incorporate current main, review conflicts,
include deployed sibling features and run checks appropriate to the change.
After committing, save an external JSON receipt naming that exact commit:

```json
{"commit": "<full commit SHA>", "checks": [{"command": "<actual relevant check>", "exit_code": 0}]}
```

From a checkout of this repository, publish with the serialized helper:

```sh
python3 scripts/single_main.py integrate /absolute/path/to/task-worktree --evidence /absolute/path/to/checks.json --push
```

The helper refuses dirty main/task worktrees, stale validation and divergent
main. If main moves, rebase the detached task and rerun checks. Push only main
to the authorized personal fork; do not force-push main or push to Nebius upstream.
A task is done only after integration/publication or an explicit recoverable
archive and recorded follow-up disposition for work that is not qualified.
Once the session exits, remove only its clean finished task worktree. Never
remove dirty or active worktrees, unrelated resources, or untracked evidence.
Check closeout with `python3 scripts/single_main.py check --remote`.

## Preservation and deployment

Branches are not a substitute for an evidence archive. Before retiring unique
work, preserve verified Git bundles, branch-to-SHA mappings, staged/unstaged
patches and untracked files outside the repositories. Record whether each change
is integrated, superseded, rejected, or retained for qualification; archiving
never counts as merging a feature. Restore archived work into a detached worktree.

Git integration does not authorize a live rollout. Record exact live image and
source provenance before choosing the integration baseline. Preserve running
clients, models, credentials, storage, Gateway routing and monitoring. The
Scientific AI hostname is intentionally unavailable; use `https://89.169.99.188`
for current presentation/API checks and leave its DNS/redirect untouched.

The local reference-transaction hook rejects non-main branch creation/updates;
the pre-push hook rejects task branches, wrong remotes, main deletion and
non-fast-forward updates. Keep these hooks installed. GitHub's current private
repository plan does not support server-side rulesets: the local guards do not
control another machine or GitHub UI. Any explicit exception needs an owner,
purpose, expiry and closeout, and must follow the user's authorized scope.

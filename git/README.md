# git/

Human-browsable automation suite backing `.github/workflows/agent_sync.yml`,
kept separate from the dot-prefixed `.git/` directory (which GitHub itself
reads) so the actual logic is easy to find, read, and edit.

Ported from Visual-Graph-Programming's `git/` automation suite.

| Directory | Purpose |
| --- | --- |
| `config/` | `automation_rules.yaml` (policy DSL) and `project_labels.json` (label taxonomy) |
| `scripts/` | `agent_tools.py` (ProjectV2 GraphQL client), `sync_backlog.py` (roadmap→board reconciler), `check_commit_ref.py` (commit-message ticket linker) |
| `hooks/` | Local git hooks (`pre-commit`, `post-commit`) plus `install.sh` to symlink them into `.git/hooks/` |

## Setup

```bash
bash git/hooks/install.sh
export PROJECT_ID="PVT_..."      # ProjectV2 node ID, see `gh project view <n> --owner <o> --format json`
export GITHUB_TOKEN="..."        # token with repo + project scopes
```

## CI

`.github/workflows/agent_sync.yml` runs `git/scripts/sync_backlog.py`
(invoked as `uv run python -m git.scripts.sync_backlog`, since it imports
`agent_tools` via a relative import and must run as the `git.scripts`
package) on demand via `workflow_dispatch`. It needs two repository secrets
(`REPO_PROJECT_TOKEN`, mapped to the `GITHUB_TOKEN` env var; `GEMINI_API_KEY`)
and one repository variable (`PROJECT_NUMBER`) configured before it can
mutate a live board — `GITHUB_PROJECT_OWNER` defaults to the repository
owner automatically. Until those are set, runs will fail fast rather than
silently no-op.

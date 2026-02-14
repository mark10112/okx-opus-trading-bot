---
description: Git workflow commands for creating branches, committing, merging, and tagging in the OKX Opus Trading Bot monorepo
---

# Git Workflow

This workflow provides common git operations following the project's branch strategy and commit conventions.

---

## Start Feature Branch

Use this when starting new work on a feature, bugfix, or refactor.

1. Check current branch and status:
// turbo
```bash
git status && git branch --show-current
```

2. Switch to `dev` and pull latest:
```bash
git checkout dev && git pull origin dev
```

3. Create a new feature branch. Branch naming rules:
   - **Feature:** `feat/p<N>-<short-desc>` (e.g. `feat/p4-haiku-screener`)
   - **Cross-phase:** `feat/<scope>-<desc>` (e.g. `feat/redis-stream-protocol`)
   - **Bugfix:** `fix/<desc>` (e.g. `fix/ws-reconnect-loop`)
   - **Refactor:** `refactor/<desc>` (e.g. `refactor/indicator-pipeline`)
   - **Docs:** `docs/<desc>`
   - **CI/Infra:** `chore/<desc>`

   Ask the user for the branch name, then run:
```bash
git checkout -b <branch-name>
```

---

## TDD Commit Cycle

Use this for committing during Red-Green-Refactor TDD cycles. Each step is a separate atomic commit.

### RED — Commit failing tests

1. Stage only test files:
```bash
git add tests/
```

2. Commit with conventional format:
```bash
git commit -m "test(<scope>): <description>"
```

### GREEN — Commit implementation

3. Stage only source files:
```bash
git add src/
```

4. Commit with conventional format:
```bash
git commit -m "feat(<scope>): <description>"
```

### REFACTOR — Commit cleanup

5. Stage all related changes:
```bash
git add .
```

6. Commit with conventional format:
```bash
git commit -m "refactor(<scope>): <description>"
```

**Valid scopes:** `indicator`, `trade`, `orchestrator`, `ui`, `infra`, `db`, `redis`, `grafana`

**Valid types:** `feat`, `fix`, `test`, `refactor`, `docs`, `chore`, `ci`

---

## Merge Feature to Dev

Use this when a feature branch is complete and all tests pass.

1. Check current branch:
// turbo
```bash
git branch --show-current
```

2. Identify which repo(s) were affected and run the full test suite. For each affected repo run:
```bash
cd <affected-repo> && python -m pytest tests/ -v
```
   Where `<affected-repo>` is one of: `indicator-trade-server`, `orchestrator`, `ui`

3. Switch to dev and pull latest:
```bash
git checkout dev && git pull origin dev
```

4. Switch back to feature branch and rebase onto dev:
```bash
git checkout <feature-branch> && git rebase dev
```
   If rebase has conflicts, resolve them. If too complex, abort with `git rebase --abort` and use merge instead.

5. Merge into dev with `--no-ff` to preserve feature boundary:
```bash
git checkout dev && git merge --no-ff <feature-branch>
```

6. Push dev to origin:
```bash
git push origin dev
```

7. Delete the feature branch locally and remotely:
```bash
git branch -d <feature-branch> && git push origin --delete <feature-branch>
```

---

## Merge Dev to Main (Phase Milestone)

Use this when a Phase is complete and dev is stable.

1. Run full test suite for all affected repos to confirm stability:
```bash
cd indicator-trade-server && python -m pytest tests/ -v
cd orchestrator && python -m pytest tests/ -v
cd ui && python -m pytest tests/ -v
```

2. Switch to main and pull latest:
```bash
git checkout main && git pull origin main
```

3. Merge dev into main with `--no-ff`:
```bash
git merge --no-ff dev
```

4. Tag the phase milestone using semantic versioning:
   - `v0.0.x` — P0 Infrastructure
   - `v0.1.x` — P1 Indicator server
   - `v0.2.x` — P2 Trade server
   - `v0.3.x` — P3 Orchestrator core
   - `v0.4.x` — P4 AI integration
   - `v0.5.x` — P5 Telegram bot
   - `v0.6.x` — P6 Grafana dashboards
   - `v0.7.x` — P7 Integration testing
   - `v1.0.0` — P8 Production ready

```bash
git tag -a v0.<phase>.0 -m "Phase <N>: <description>"
```

5. Push main with tags:
```bash
git push origin main --tags
```

---

## Pre-commit Setup

Use this once per machine to install pre-commit hooks (ruff linting + formatting).

1. Install pre-commit:
```bash
pip install pre-commit
```

2. Install hooks into the repo:
```bash
pre-commit install
```

3. (Optional) Run against all files to verify:
```bash
pre-commit run --all-files
```

After setup, every `git commit` will auto-run:
- `ruff check --fix` — lint fixes (F, E, W, I, N, UP, B, C4, SIM)
- `ruff format` — code formatting

If a commit fails due to ruff, fix the issues and re-commit:
```bash
ruff check --fix .
ruff format .
git add . && git commit -m "<same message>"
```

---

## Quick Status Check

Use this to see the current state of the repo.

// turbo
1. Show status, current branch, and recent history:
```bash
git status && git log --oneline --graph -10
```

// turbo
2. List all branches:
```bash
git branch -a
```

---

## Rebase from Dev

Use this to keep a long-running feature branch up to date with dev (especially for parallel P5/P6 branches).

// turbo
1. Fetch latest from origin:
```bash
git fetch origin
```

2. Rebase current branch onto dev:
```bash
git rebase origin/dev
```

   If conflicts arise and are too complex, abort and merge instead:
```bash
git rebase --abort && git merge origin/dev
```

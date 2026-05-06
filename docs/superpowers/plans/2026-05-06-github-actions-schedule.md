# GitHub Actions Weather Schedule — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Schedule `weather.py` to run daily on GitHub Actions and commit the refreshed `weather_data.csv` back to `main`.

**Architecture:** Single workflow file (`.github/workflows/weather.yml`) with one job that checks out the repo, installs Python deps, runs `weather.py` with `WEATHER_API_KEY` injected from GitHub Secrets, then commits and pushes the updated CSV using inline `git`. Triggered daily by cron at 11:17 UTC and manually via `workflow_dispatch`.

**Tech Stack:** GitHub Actions (`actions/checkout@v4`, `actions/setup-python@v5`), Python 3.12, `gh` CLI for secret management and manual triggering.

**Spec:** `docs/superpowers/specs/2026-05-06-github-actions-schedule-design.md`

---

## File Structure

**Files created:**
- `.github/workflows/weather.yml` — the workflow definition

**Files modified:** None.

**Repository configuration changes (not files):**
- New GitHub repository secret `WEATHER_API_KEY`
- "Workflow permissions" set to "Read and write" (under repo Settings → Actions → General)

There are no Python source changes. `weather.py` already reads `WEATHER_API_KEY` from `os.environ` and is unchanged.

---

## Task 1: Configure repo for write access and add the secret

**Files:** None. This task only touches GitHub repo settings.

- [ ] **Step 1: Confirm your local `.env` has the API key**

Run: `grep -c '^WEATHER_API_KEY=' .env`
Expected output: `1`

Verify the file is gitignored (so the real key never gets committed):
Run: `git check-ignore -v .env`
Expected output: a line like `.gitignore:151:.env	.env` (the trailing `.env` is the path; the rule is `.env` at line 151 of `.gitignore`). Exit code `0`.

- [ ] **Step 2: Set the GitHub repo secret using the value from `.env`**

Run:
```bash
gh secret set WEATHER_API_KEY --body "$(grep '^WEATHER_API_KEY=' .env | cut -d= -f2-)"
```

Expected output: `✓ Set Actions secret WEATHER_API_KEY for nchabot14/weather-api-pipeline`

- [ ] **Step 3: Verify the secret is registered**

Run: `gh secret list`
Expected output (the timestamp will differ):
```
NAME                UPDATED
WEATHER_API_KEY     less than a minute ago
```

- [ ] **Step 4: Set workflow permissions to "Read and write"**

Run:
```bash
gh api -X PUT /repos/nchabot14/weather-api-pipeline/actions/permissions/workflow \
  -f default_workflow_permissions=write \
  -F can_approve_pull_request_reviews=false
```

Expected: HTTP 204 (empty response, no error).

Verify:
```bash
gh api /repos/nchabot14/weather-api-pipeline/actions/permissions/workflow
```
Expected output:
```json
{
  "default_workflow_permissions": "write",
  "can_approve_pull_request_reviews": false
}
```

- [ ] **Step 5: No commit (this task changes no files in the repo)**

---

## Task 2: Create the workflow file

**Files:**
- Create: `.github/workflows/weather.yml`

- [ ] **Step 1: Create the workflow file**

Write the following file at `.github/workflows/weather.yml`:

```yaml
name: Daily weather forecast refresh

on:
  schedule:
    - cron: '17 11 * * *'
  workflow_dispatch: {}

permissions:
  contents: write

concurrency:
  group: weather-fetch
  cancel-in-progress: false

jobs:
  fetch-and-commit:
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Fetch forecasts
        env:
          WEATHER_API_KEY: ${{ secrets.WEATHER_API_KEY }}
        run: python weather.py

      - name: Commit updated CSV
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add weather_data.csv
          if git diff --staged --quiet; then
            echo "No changes to commit."
            exit 0
          fi
          git commit -m "Update weather forecasts ($(date -u +'%Y-%m-%d %H:%M UTC'))"
          git push
```

- [ ] **Step 2: Validate YAML syntax locally**

Run:
```bash
python -c "import yaml, sys; yaml.safe_load(open('.github/workflows/weather.yml')); print('YAML OK')"
```
Expected output: `YAML OK`
Expected exit code: `0`

If it fails, the error message will point at the line — fix and re-run.

- [ ] **Step 3: Commit the workflow file**

```bash
git add .github/workflows/weather.yml
git commit -m "Add GitHub Actions workflow for daily weather refresh"
```

Expected: one commit added to `main`, working tree clean.

---

## Task 3: Push to GitHub and trigger a manual run

**Files:** None modified — only pushing existing commits and watching a remote run.

- [ ] **Step 1: Push commits to origin**

Run: `git push origin main`
Expected: push succeeds, two commits ahead of origin become zero (the design-doc commit from earlier plus the workflow commit from Task 2).

- [ ] **Step 2: Confirm the workflow is registered on GitHub**

Run: `gh workflow list`
Expected output includes a row like:
```
Daily weather forecast refresh    active    <numeric_id>
```

- [ ] **Step 3: Trigger a manual run**

Run: `gh workflow run "Daily weather forecast refresh"`
Expected output: `✓ Created workflow_dispatch event for weather.yml at main`

- [ ] **Step 4: Watch the run to completion**

The dispatched run takes a few seconds to register. Get its ID, then watch it:

```bash
sleep 5
RUN_ID=$(gh run list --workflow="Daily weather forecast refresh" --limit 1 --json databaseId --jq '.[0].databaseId')
gh run watch "$RUN_ID" --exit-status
```

Expected: `gh run watch` streams step status, then exits with code `0` and prints `✓ Run Daily weather forecast refresh ... completed with 'success'`.

If it exits non-zero:
- View logs with `gh run view "$RUN_ID" --log-failed` to see which step failed.
- Most likely failure: `KeyError: 'WEATHER_API_KEY'` (Task 1 secret missing) or push permission denied (Task 1 Step 4 not done).

---

## Task 4: Verify the outputs

**Files:** None modified locally — verification only.

- [ ] **Step 1: Confirm a new bot commit was pushed to `main`**

Run: `git fetch origin && git log origin/main -1 --pretty=format:'%an <%ae>%n%s'`
Expected: author is `github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>` and the subject starts with `Update weather forecasts (`.

- [ ] **Step 2: Confirm the CSV reflects today's data**

Run:
```bash
git show "origin/main:weather_data.csv" | head -2
```
Expected: header row, then a data row whose `date` column equals today's UTC date (e.g., `2026-05-06`).

- [ ] **Step 3: Pull the bot commit into your local clone**

Run: `git pull --ff-only origin main`
Expected: fast-forward succeeds; local `main` matches `origin/main`.

- [ ] **Step 4: No new commit — verification only**

This task makes no local changes. The "commit" produced by this work is the one the bot just pushed.

---

## Task 5: (Optional) Confirm the scheduled run fires

This task is not actionable in the same session — it's a follow-up check the next day.

- [ ] **Step 1: After the next 11:17 UTC cron tick, list recent runs**

Run: `gh run list --workflow="Daily weather forecast refresh" --limit 5`
Expected: a run with event `schedule` appears with status `completed` / conclusion `success`.

- [ ] **Step 2: If the scheduled run is missing**

Possible causes (check in this order):
1. The repo had no activity for 60+ days — GitHub disables scheduled workflows on dormant repos. Reactivate via `gh workflow enable "Daily weather forecast refresh"`.
2. GitHub-side delay during a high-load window — the run will appear later. Verify via the "Actions" tab.
3. Workflow file not on default branch — `schedule` triggers only fire from `main`. Confirm with `git ls-tree origin/main .github/workflows/`.

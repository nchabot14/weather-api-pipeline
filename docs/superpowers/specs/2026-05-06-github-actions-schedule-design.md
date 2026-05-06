# Design: Schedule weather pipeline via GitHub Actions

**Date:** 2026-05-06
**Status:** Approved (pending spec review)

## Goal

Run `weather.py` automatically on a daily schedule using GitHub Actions, and commit the refreshed `weather_data.csv` back to `main` each run so the file in the repo always reflects the latest 7-day forecast for the 20 tracked US cities.

## Non-goals

- Building a historical archive of forecasts (would require append-mode + a `fetched_at` column; explicitly rejected).
- Pushing data to external storage (S3, Sheets, a database).
- Notifying on failure beyond GitHub's default email-the-repo-owner behavior.
- Any modifications to `weather.py` itself — the existing script already reads `WEATHER_API_KEY` from the environment, which is exactly the contract Actions needs.

## Architecture

A single workflow file at `.github/workflows/weather.yml` defining one job, `fetch-and-commit`, on `ubuntu-latest`.

### Triggers

- **`schedule`** — cron `17 11 * * *` (daily at 11:17 UTC ≈ 6:17 AM CDT / 5:17 AM CST). The off-the-hour minute avoids GitHub's documented load-related delays for on-the-hour cron jobs. Cron does not auto-adjust for DST; the local time will shift by one hour at DST transitions, which is acceptable.
- **`workflow_dispatch: {}`** — exposes a "Run workflow" button in the GitHub UI for manual runs (needed for testing the workflow itself and for ad-hoc refreshes).

### Permissions

`permissions: contents: write` declared at the workflow level. The default `GITHUB_TOKEN` is read-only on private repos and on newer org defaults; write access is required for the final `git push` of the updated CSV.

### Concurrency

```yaml
concurrency:
  group: weather-fetch
  cancel-in-progress: false
```

If a manual `workflow_dispatch` run overlaps the cron run, the second one queues rather than running concurrently. Prevents two parallel runs racing on the same `weather_data.csv` and `git push`.

## Job steps

The job runs five steps in order:

1. **Checkout** — `actions/checkout@v4` with default `persist-credentials: true` so the `GITHUB_TOKEN` remains in git config for the final push.
2. **Set up Python** — `actions/setup-python@v5` with `python-version: '3.12'` and `cache: 'pip'`. Built-in pip caching keyed on `requirements.txt` makes warm reruns ~10–20s faster.
3. **Install dependencies** — `pip install -r requirements.txt` using the existing pinned versions (no changes to `requirements.txt`).
4. **Fetch forecasts** — `python weather.py`, with `WEATHER_API_KEY` injected as a step-scoped env var (see Secrets section).
5. **Commit & push CSV** — inline `git` commands (see Commit strategy section).

### Python version rationale

Python 3.12 because: it's GA, supported on `ubuntu-latest`, and the pinned `pandas==3.0.2` and `numpy==2.4.4` both support it. Local dev Python version doesn't need to match — pinned dependencies cover compatibility.

### `weather.py` behavior in CI

The script's `load_dotenv()` call is a no-op when no `.env` file is present (which is the case in the runner). `os.environ["WEATHER_API_KEY"]` then resolves to the env var injected by the workflow step. No script changes required.

## Secrets

A single repository secret, `WEATHER_API_KEY`, holds the weatherapi.com API key. Added via GitHub → Settings → Secrets and variables → Actions → New repository secret.

The secret is injected **only on the step that runs the script**, not at job level:

```yaml
- name: Fetch forecasts
  env:
    WEATHER_API_KEY: ${{ secrets.WEATHER_API_KEY }}
  run: python weather.py
```

Rationale: smaller blast radius. The key is not in the environment of `pip install` or the `git` commands, so a compromised dependency or stray subprocess cannot trivially read it. GitHub auto-masks secret values in logs; step-scoped injection is defense in depth on top of that.

`.env` is already gitignored at `.gitignore:151`, so the local key cannot be committed accidentally.

## Commit strategy

After `python weather.py` overwrites `weather_data.csv`, an inline `git` block commits and pushes:

```yaml
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

### Design choices

- **No-op guard.** If the API returns identical data (e.g., a manual run immediately after the cron run), `git commit` would otherwise fail with "nothing to commit" and fail the whole job. The `git diff --staged --quiet` check exits the step cleanly.
- **Bot identity.** `github-actions[bot]` with the `41898282+github-actions[bot]@users.noreply.github.com` noreply email is GitHub's official convention; commits render with the Actions bot avatar and are visually distinct from human commits.
- **No `[skip ci]` needed.** Pushes authenticated with the default `GITHUB_TOKEN` do not retrigger workflows on `push`, so no infinite-loop risk. (Would only be needed with a personal access token.)
- **No retry on push failure.** A push race (someone else pushed to `main` between checkout and push) is essentially impossible on a personal repo running once a day. If it ever happens, the next day's run resolves it. Not worth the workflow complexity.
- **Inline `git`, not `stefanzweifel/git-auto-commit-action`.** Avoiding third-party actions keeps trust scope minimal and the workflow easy to audit.

## File layout (planned)

```
.github/
  workflows/
    weather.yml         # the new workflow file
docs/
  superpowers/
    specs/
      2026-05-06-github-actions-schedule-design.md   # this doc
```

No other files change.

## Validation plan

1. Add `WEATHER_API_KEY` secret in repo settings.
2. Merge the workflow file to `main`.
3. Trigger a manual run via the "Run workflow" button on the Actions tab.
4. Confirm: workflow succeeds, the run produces a commit authored by `github-actions[bot]` updating `weather_data.csv`, the CSV content reflects a fresh fetch (e.g., `date` column starts at today).
5. Wait for the next scheduled cron run (within 24 hours) and confirm it also produces a commit.

## Risks & mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Cron skipped during high GitHub load | Low–medium | 11:17 UTC (off-the-hour) reduces this; a single skipped day is tolerable. |
| `weatherapi.com` rate limit / outage | Low | The job will fail visibly; GitHub emails the repo owner on failure by default. No retry needed for daily cadence. |
| Concurrent runs corrupt the CSV | Very low | `concurrency: weather-fetch` serializes overlapping runs. |
| `GITHUB_TOKEN` write permission disabled at org level | Repo-dependent | Workflow declares `permissions: contents: write` explicitly; if org policy still blocks, surfaces as a clear push error. |
| Secret accidentally leaked in logs | Low | Step-scoped env var + GitHub's automatic log masking. |

# University Web Rankings

Daily Google Lighthouse tests of UK university homepages, published as a dashboard at
**https://ibrouos.github.io/uni-website-rankings/**.

The dashboard has three views:

- **Rankings**: every university with its current score, 30-day change and a 90-day trend chart
  (Web Vitals or Lighthouse scores, mobile or desktop).
- **Compare**: up to six universities side by side. The selection is kept in the URL, so links can be shared.
- **University pages**: full history, Web Vitals charts and every test run.

## How it works

```
Lighthouse Monitor (daily, 06:00 UTC)          Build Dashboard (after each monitor run, and 08:00 UTC)
  6 parallel jobs, each testing its share        builds docs/ from results/
  of the sites one at a time                     deploys it to GitHub Pages
        │                                                   ▲
        ▼                                                   │
  publish job: merges the shards, appends to results/, commits ───┘
```

- **`.github/workflows/lighthouse-monitor.yml`** runs `lighthouse_top50.py`. Sites are split into shards
  (`--shard`/`--shards`) so each GitHub machine runs one test at a time. Parallel tests on one machine
  compete for CPU, which inflates total blocking time and lowers performance scores.
  Lighthouse is pinned (`LIGHTHOUSE_VERSION`), so scoring only changes when the version is bumped on purpose.
  If you change the number of shards, update both `SHARDS` and the `matrix.shard` list.
- **`.github/workflows/build-dashboard.yml`** runs `build_dashboard_new.py` and deploys `docs/` with
  GitHub Actions. Pages must be set to deploy from **GitHub Actions** (Settings → Pages).
  `docs/` is generated and is not committed.

Mobile tests use Lighthouse's default mobile settings (4× CPU slowdown, slow 4G). Desktop tests use
`--preset=desktop`.

## Configuration

`config.json`:

| Setting | What it does |
|---|---|
| `sites_file` | Which list of universities is tested and shown, e.g. `universities_top50.json` or `universities.json` (130) |
| `display_settings.hidden_universities` | Names to leave off the dashboard |

## Results data

`results_store.py` reads and writes all results.

- `results/index.json`: every university with results, as `{name, slug, url}`.
- `results/<slug>.jsonl`: one line per test, oldest first. Runs only ever append, which keeps the
  repository small. A line looks like:

```json
{"timestamp":"2026-11-04T06:20:11","device":"desktop","scores":{"performance":92,"accessibility":99,"best_practices":100,"seo":100},"metrics":{"first_contentful_paint":1801,"largest_contentful_paint":2901,"total_blocking_time":410,"cumulative_layout_shift":0.0012,"speed_index":3100,"interactive":5001},"lighthouse_version":"12.8.2","form_factor":"desktop","throttling":{"rttMs":40,"throughputKbps":10240,"cpuSlowdownMultiplier":1},"benchmark_index":2104.5}
```

Timings are in milliseconds. `benchmark_index` is how fast the test machine was. Tests go back to
21 June 2025; results for universities outside the current `sites_file` are kept for when the list grows.

### Methodology change

Earlier tests had two problems:

- "Desktop" runs used a Lighthouse flag that had been removed, so they actually emulated a phone on a
  faster connection.
- Several tests ran at once on the same machine.

Only tests from the corrected runner record `form_factor`. The dashboard dates the change from the first
of those, marks it on every chart, and hides change figures that would compare results across it.

## Running locally

```bash
python build_dashboard_new.py          # builds docs/ from results/
python -m http.server -d docs 8000     # then open http://localhost:8000
```

Running tests needs Node.js and Chrome:

```bash
npm install -g lighthouse@12.8.2
python lighthouse_top50.py --shard 0 --shards 50 --output shard-results/test.json   # one site, results to a scratch file
python lighthouse_top50.py --merge shard-results                                      # append those results to results/
```

## Real-user data (not yet wired in)

`fetch_crux_data.py` and `crux_only_monitor.py` fetch Chrome UX Report field data. They need a
`CRUX_API_KEY` (see `CRUX_SETUP.md`), which is set as a repository secret for Actions.

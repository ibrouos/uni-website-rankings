# GitHub Actions Setup Guide

## Current Status ✅

Your GitHub Actions workflows have been updated to work with the new dashboard system. Here's what's configured:

## Workflows

### 1. **Lighthouse Performance Monitor** (`lighthouse-monitor.yml`)
**Trigger**: Daily at 6 AM UTC + Manual
**Purpose**: Run Lighthouse tests and generate dashboard

**What it does:**
1. Checks out the repository
2. Sets up Node.js 18 and Python 3.9
3. Installs Lighthouse CLI and Chrome
4. Creates necessary directories (`lighthouse_results`, `results`, `docs`)
5. Runs `lighthouse_monitor.py` (tests all universities)
6. Runs `build_dashboard_new.py` (generates the new dashboard)
7. Commits and pushes results
8. Deploys to GitHub Pages

**Updated**: ✅ Now creates `results/` directory and uses `build_dashboard_new.py`

### 2. **Build Dashboard** (`build-dashboard.yml`)
**Trigger**: Manual + After Lighthouse Monitor completes
**Purpose**: Rebuild dashboard from existing data

**What it does:**
1. Checks out the repository
2. Sets up Python 3.9
3. Runs `build_dashboard_new.py` (regenerates dashboard from existing data)
4. Uploads and deploys to GitHub Pages

**Updated**: ✅ Now uses `build_dashboard_new.py`

### 3. **Migrate Data** (`migrate-data.yml`) - NEW!
**Trigger**: Manual only (one-time use)
**Purpose**: Migrate existing data to new per-university format

**What it does:**
1. Checks out full repository history
2. Runs `reorganize_data.py` (converts old data to new format)
3. Runs `build_dashboard_new.py` (generates new dashboard)
4. Commits and pushes migrated data

**Status**: ⚠️ Run this ONCE to migrate your existing data

## Setup Steps

### Step 1: Enable GitHub Pages (if not already enabled)

1. Go to your repository: https://github.com/ibrouos/uni-website-rankings
2. Click **Settings** → **Pages**
3. Under **Source**, ensure it's set to:
   - **Source**: GitHub Actions (not "Deploy from a branch")
4. Save

### Step 2: Run the One-Time Migration

1. Go to **Actions** tab in your repository
2. Click **Migrate Data to New Format (One-time)**
3. Click **Run workflow** → **Run workflow**
4. Wait for it to complete (check for ✅ green checkmark)

This will:
- Create the `results/` directory with per-university files
- Generate the new dashboard in `docs/`
- Commit everything to the repository

### Step 3: Verify the Migration

After the migration workflow completes:

1. Check that `results/` directory exists with individual university JSON files
2. Check that `docs/` contains:
   - `index.html` (new main dashboard)
   - Individual university detail pages (e.g., `university-of-oxford.html`)
3. Visit your GitHub Pages URL to see the new dashboard

### Step 4: Test the Automated Workflow

1. Go to **Actions** → **Lighthouse Performance Monitor**
2. Click **Run workflow** → **Run workflow** (manual test)
3. Wait for completion
4. Visit your GitHub Pages URL to verify it updated

## GitHub Pages URL

Your dashboard will be available at:
```
https://ibrouos.github.io/uni-website-rankings/
```

## Configuration

### Hiding Universities

Edit `config.json` in the repository to hide specific universities:

```json
{
  "display_settings": {
    "hidden_universities": [
      "Heriot-Watt University",
      "Another University Name"
    ]
  }
}
```

Commit and push the changes. The next time the workflow runs, those universities will be hidden from the dashboard (but still tested).

## Workflow Schedule

Current schedule:
- **Lighthouse tests**: Daily at 6 AM UTC (7 AM BST / 6 AM GMT)
- **Dashboard rebuild**: After lighthouse tests complete

To change the schedule, edit `.github/workflows/lighthouse-monitor.yml` line 6:
```yaml
- cron: '0 6 * * *'  # Change this cron expression
```

Example cron expressions:
- `0 6 * * *` - Daily at 6 AM UTC
- `0 */6 * * *` - Every 6 hours
- `0 0 * * 1` - Every Monday at midnight
- `0 0 1 * *` - First day of every month

## Troubleshooting

### ❌ Workflow fails with "No such file or directory: results/"

**Solution**: Run the **Migrate Data** workflow first to create the directory structure.

### ❌ Dashboard shows old design

**Possible causes:**
1. Browser cache - Hard refresh (Ctrl+Shift+R / Cmd+Shift+R)
2. Migration not run - Run the **Migrate Data** workflow
3. Wrong builder being used - Check that workflows reference `build_dashboard_new.py`

### ❌ GitHub Pages not updating

**Check:**
1. Actions tab - Is the workflow succeeding? (green ✅)
2. Settings → Pages - Is source set to "GitHub Actions"?
3. Workflow permissions:
   - Go to Settings → Actions → General
   - Scroll to "Workflow permissions"
   - Ensure "Read and write permissions" is selected
   - Save

### ❌ "Permission denied" errors

**Fix workflow permissions:**
1. Repository Settings → Actions → General
2. Under "Workflow permissions", select:
   - ✅ Read and write permissions
   - ✅ Allow GitHub Actions to create and approve pull requests
3. Save

### ❌ University still showing after adding to hidden list

**Steps:**
1. Ensure `config.json` is committed and pushed
2. Wait for next automated run, or manually trigger **Build Dashboard** workflow
3. The university will be hidden but still tested

## Manual Operations

### Rebuild Dashboard Only (no testing)
1. Actions → **Build Dashboard**
2. Run workflow
3. Uses existing data in `results/` directory

### Run Full Test + Rebuild
1. Actions → **Lighthouse Performance Monitor**
2. Run workflow
3. Tests all universities and rebuilds dashboard

### Local Testing
```bash
# Run locally before pushing
cd /Users/ianbromwich/Documents/code/uni-website-rankings

# Test the migration
python3 reorganize_data.py

# Build dashboard
python3 build_dashboard_new.py

# Open in browser
open docs/index.html
```

## File Structure After Migration

```
uni-website-rankings/
├── .github/workflows/
│   ├── lighthouse-monitor.yml    # Daily tests + dashboard
│   ├── build-dashboard.yml       # Dashboard rebuild only
│   └── migrate-data.yml          # One-time migration
├── config.json                   # Hide/show universities
├── lighthouse_results/           # Old format (kept for compatibility)
│   └── lighthouse_results_*.json
├── results/                      # NEW: Per-university files
│   ├── index.json
│   ├── university-of-oxford.json
│   ├── university-of-cambridge.json
│   └── ...
└── docs/                         # Generated dashboard
    ├── index.html                # Main dashboard with cards
    ├── university-of-oxford.html
    ├── university-of-cambridge.html
    └── ...
```

## Success Checklist

- [ ] Migration workflow completed successfully
- [ ] `results/` directory exists with university files
- [ ] New dashboard visible at GitHub Pages URL
- [ ] University cards show 7-day and 30-day averages
- [ ] Can click into individual universities for details
- [ ] Charts display correctly on detail pages
- [ ] Hidden universities (e.g., Heriot-Watt) not showing
- [ ] Daily automated workflow runs successfully

## Next Steps

1. **Run the migration** (Step 2 above) - Do this ONCE
2. **Verify the new dashboard** works on GitHub Pages
3. **Configure hidden universities** in `config.json` if needed
4. **Let it run automatically** daily from now on

The system is now set up to:
- ✅ Run tests daily
- ✅ Save data per-university
- ✅ Generate modern dashboard
- ✅ Auto-deploy to GitHub Pages
- ✅ Respect hide configuration

Need help? Check the [README_NEW_SYSTEM.md](./README_NEW_SYSTEM.md) for more details about the new dashboard features.

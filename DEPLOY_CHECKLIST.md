# 🚀 Deployment Checklist

## ✅ Confirmed: GitHub Actions Ready!

Your GitHub Actions workflows have been **updated and verified** to work with the new dashboard system.

## What's Been Updated

### ✅ GitHub Actions Workflows
- **lighthouse-monitor.yml**: Now creates `results/` directory and uses `build_dashboard_new.py`
- **build-dashboard.yml**: Now uses `build_dashboard_new.py` instead of old builder
- **migrate-data.yml**: NEW workflow to migrate existing data (run once)

### ✅ Configuration Files
- **config.json**: Controls which universities to hide from display
- All Python scripts are in place and tested

## Quick Start (3 Steps)

### 1. Push Your Changes

```bash
cd /Users/ianbromwich/Documents/code/uni-website-rankings

# Stage all new files
git add .

# Commit
git commit -m "Add new dashboard system with per-university data structure"

# Push to GitHub
git push origin main
```

### 2. Run Migration Workflow (ONE TIME)

1. Go to: https://github.com/ibrouos/uni-website-rankings/actions
2. Click on **"Migrate Data to New Format (One-time)"**
3. Click **"Run workflow"** button (top right)
4. Select **"main"** branch
5. Click **"Run workflow"** green button
6. Wait 2-5 minutes for completion

✅ This creates the `results/` directory and new dashboard

### 3. Verify It Works

Visit your GitHub Pages site:
```
https://ibrouos.github.io/uni-website-rankings/
```

You should see:
- ✅ Card-based layout (not 8,000+ rows)
- ✅ One card per university
- ✅ 7-day and 30-day toggle switches
- ✅ Click any card to see detailed view with charts

## GitHub Pages Settings

**IMPORTANT**: Ensure GitHub Pages is configured correctly:

1. Go to: https://github.com/ibrouos/uni-website-rankings/settings/pages
2. Under **"Source"**, select: **"GitHub Actions"** (not "Deploy from a branch")
3. Save (if changed)

## Workflow Permissions

**IMPORTANT**: Check workflow permissions:

1. Go to: https://github.com/ibrouos/uni-website-rankings/settings/actions
2. Scroll to **"Workflow permissions"**
3. Select: **"Read and write permissions"** ✅
4. Check: **"Allow GitHub Actions to create and approve pull requests"** ✅
5. Save (if changed)

## Testing the System

### Test Manual Run
After migration completes:

1. Go to **Actions** → **"Lighthouse Performance Monitor"**
2. Click **"Run workflow"** → **"Run workflow"**
3. Wait for green checkmark (takes ~20-30 minutes for all tests)
4. Check GitHub Pages URL again to see updated data

## Automated Schedule

Once setup is complete, the system runs automatically:

- **Daily at 6 AM UTC**: Lighthouse tests + dashboard rebuild
- **After tests complete**: Dashboard rebuild only
- **Result**: Fresh data every day, auto-deployed to GitHub Pages

## Configuration Management

### To Hide Universities

1. Edit `config.json` in your repository:
   ```json
   {
     "display_settings": {
       "hidden_universities": [
         "Heriot-Watt University",
         "University Name Here"
       ]
     }
   }
   ```

2. Commit and push:
   ```bash
   git add config.json
   git commit -m "Update hidden universities list"
   git push
   ```

3. Trigger rebuild:
   - Wait for next daily run, OR
   - Manually run "Build Dashboard" workflow

## Troubleshooting

### ❌ "No such file or directory: results/"
**Solution**: Run the "Migrate Data" workflow (Step 2 above)

### ❌ Dashboard shows old layout
**Solution**: 
1. Hard refresh browser (Cmd+Shift+R on Mac, Ctrl+Shift+R on Windows)
2. Check that migration workflow completed successfully
3. Verify `docs/` contains new HTML files (not just old `index.html` and `data.js`)

### ❌ Workflow fails with permission error
**Solution**: Check workflow permissions (see "Workflow Permissions" section above)

### ❌ Chart.js charts not displaying
**Solution**: Charts require internet connection (uses CDN). Check browser console for errors.

## File Summary

### New Files Created
- ✅ `config.json` - Configuration
- ✅ `reorganize_data.py` - Data migration script
- ✅ `build_dashboard_new.py` - New dashboard builder
- ✅ `.github/workflows/migrate-data.yml` - Migration workflow
- ✅ `README_NEW_SYSTEM.md` - Detailed system documentation
- ✅ `GITHUB_ACTIONS_SETUP.md` - Complete GitHub Actions guide
- ✅ `DEPLOY_CHECKLIST.md` - This file

### Updated Files
- ✅ `lighthouse_monitor.py` - Now saves per-university data
- ✅ `.github/workflows/lighthouse-monitor.yml` - Uses new builder
- ✅ `.github/workflows/build-dashboard.yml` - Uses new builder

### Unchanged (Still Working)
- ✅ `universities.json` - Still used for test URLs
- ✅ `lighthouse_results/` - Still created for backward compatibility
- ✅ Old `build_dashboard.py` - Kept for reference, not used

## Expected Results After Setup

### Main Dashboard (`index.html`)
- ~130 university cards (not 8,000+ items)
- Toggle between 7-day and 30-day averages
- Mobile and Desktop scores side-by-side
- Trend indicators (📈📉➡️)
- Search and sort controls

### Detail Pages
- One HTML file per university
- Interactive Chart.js line chart
- Time range filters (week/month/year/all)
- Device filters (both/mobile/desktop)
- Complete historical data table

### Performance
- **Before**: ~4.7 MB `data.js` file, slow loading
- **After**: Small index page, data loaded per-university on-demand
- **Result**: Instant main page load, fast drilldowns

## Success Criteria ✅

After completing all steps, you should be able to:

- [ ] Visit GitHub Pages URL and see card-based dashboard
- [ ] Click a university card and see detail page with charts
- [ ] Toggle between 7-day and 30-day views
- [ ] See that Heriot-Watt (and any other hidden unis) don't appear
- [ ] See workflow runs automatically each day
- [ ] See new data appearing daily

## Support

If something isn't working:

1. Check `GITHUB_ACTIONS_SETUP.md` for detailed troubleshooting
2. Check GitHub Actions logs for specific errors
3. Verify all workflow permissions are set correctly
4. Ensure GitHub Pages source is "GitHub Actions"

---

**Ready to deploy?** Follow the 3 steps above! 🚀

The system is fully configured and ready to use. Just push your changes and run the migration workflow.

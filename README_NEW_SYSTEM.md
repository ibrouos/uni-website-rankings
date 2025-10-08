# University Performance Dashboard - New System

## Overview

This update completely reorganizes the dashboard to be more performant and user-friendly by:

1. **Per-university data files** instead of one giant file
2. **Card-based UI** showing one card per university with averages
3. **Detailed drilldown pages** for each university with charts and tables
4. **Configuration system** to hide specific universities
5. **Better performance** by showing only aggregated data on the main page

## New File Structure

```
├── config.json                    # Configuration for hiding universities
├── reorganize_data.py            # Script to migrate old data to new format
├── build_dashboard_new.py        # New dashboard builder
├── lighthouse_monitor.py         # Updated to save per-university files
├── results/                      # New directory for per-university data
│   ├── index.json               # Index of all universities
│   ├── university-of-oxford.json
│   ├── university-of-cambridge.json
│   └── ...
└── docs/                         # Generated dashboard
    ├── index.html               # Main dashboard with cards
    ├── university-of-oxford.html
    ├── university-of-cambridge.html
    └── ...
```

## Setup Instructions

### 1. Reorganize Existing Data

First, run the reorganization script to convert your existing data into per-university files:

```bash
cd /Users/ianbromwich/Documents/code/uni-website-rankings
python3 reorganize_data.py
```

This will:
- Read all files in `lighthouse_results/`
- Create individual JSON files for each university in `results/`
- Create an index file listing all universities

### 2. Build the New Dashboard

Generate the new dashboard with cards and detail pages:

```bash
python3 build_dashboard_new.py
```

This will create:
- `docs/index.html` - Main dashboard with university cards
- `docs/{university-slug}.html` - Detail page for each university

### 3. Configuration

Edit `config.json` to hide specific universities:

```json
{
  "display_settings": {
    "hidden_universities": [
      "Heriot-Watt University",
      "Another University"
    ]
  }
}
```

Universities in this list will:
- Still be tested by `lighthouse_monitor.py`
- Have their data saved in `results/`
- NOT appear on the dashboard

### 4. Future Lighthouse Runs

The updated `lighthouse_monitor.py` now automatically:
- Saves data in both old format (for backward compatibility)
- Saves data in new per-university format
- Updates the index file

Just run as normal:

```bash
python3 lighthouse_monitor.py
```

Then rebuild the dashboard:

```bash
python3 build_dashboard_new.py
```

## Dashboard Features

### Main Dashboard (`index.html`)

- **University Cards**: One card per university showing:
  - University name and trend indicator (📈📉➡️)
  - Toggle between 7-day and 30-day averages
  - Separate scores for Mobile and Desktop
  - Performance, Accessibility, Best Practices, SEO scores
  - Last updated date and total test count

- **Controls**:
  - Search universities by name or URL
  - Sort by name, performance, accessibility, or last updated
  - Click any card to see detailed view

### Detail Pages (`{university-slug}.html`)

- **Interactive Chart**:
  - Line chart showing performance scores over time
  - Time range selector: Last Week, Month, Year, All Time
  - Device filter: Both, Mobile Only, Desktop Only
  - Powered by Chart.js

- **Data Table**:
  - All historical test results
  - Columns: Date, Device, Performance, FCP, LCP, CLS, Speed Index, Accessibility, Best Practice, SEO
  - Color-coded scores (green/yellow/red)
  - Scrollable with sticky header

## Benefits of New System

1. **Fast Loading**: Main page only loads aggregated data, not 8k+ items
2. **Easy Navigation**: Click into specific universities for details
3. **Better UX**: Card-based design is cleaner and more scannable
4. **Flexible Configuration**: Hide universities without deleting data
5. **Historical Analysis**: Charts and tables show trends over time
6. **Responsive**: Works on mobile, tablet, and desktop

## Migration Notes

- Old system files are preserved (no data loss)
- Old dashboard at `docs/index.html` will be overwritten
- Both data formats are maintained during transition
- You can always regenerate from historical data

## Automation

For continuous monitoring, set up a cron job or GitHub Action:

```bash
# Daily at 2 AM: Run tests and rebuild dashboard
0 2 * * * cd /path/to/project && python3 lighthouse_monitor.py && python3 build_dashboard_new.py
```

## Troubleshooting

**Q: Dashboard shows "No universities found"**
A: Run `python3 reorganize_data.py` first to create the `results/` directory

**Q: University not showing on dashboard**
A: Check `config.json` to ensure it's not in `hidden_universities`

**Q: Charts not displaying**
A: Ensure Chart.js CDN is accessible (requires internet connection)

**Q: Want to use old dashboard**
A: Rename `build_dashboard_new.py` and keep using `build_dashboard.py`

## Next Steps

1. Run the reorganization script
2. Build the new dashboard
3. Open `docs/index.html` in your browser
4. Configure which universities to show/hide
5. Set up automated runs if desired

Enjoy your new performant dashboard! 🚀

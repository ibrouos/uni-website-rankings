# Lighthouse Performance Monitor Setup

This Python application runs daily Lighthouse tests on your websites and generates a GitHub Pages dashboard.

## Quick Setup

### 1. Repository Setup
1. Create a new GitHub repository
2. Copy all the files into your repository
3. Edit `universities.json` to include the websites you want to test
4. The script will automatically read from this JSON file

### 2. GitHub Pages Configuration
1. Go to your repository Settings → Pages
2. Set Source to "GitHub Actions"
3. The dashboard will be available at `https://yourusername.github.io/your-repo-name/`

### 3. Local Development (Optional)

If you want to run tests locally:

```bash
# Install Node.js and npm (if not already installed)
# Then install Lighthouse CLI globally
npm install -g lighthouse

# Run the Python script
python lighthouse_monitor.py
```

## How It Works

**The script does the following:**
1. **Daily Tests**: Runs Lighthouse tests on all URLs for both mobile and desktop
2. **Data Storage**: Saves results as JSON files in `lighthouse_results/` directory
3. **Dashboard Generation**: Creates a static HTML dashboard in `docs/` directory
4. **Automatic Deployment**: GitHub Actions deploys the dashboard to GitHub Pages

**Key Features:**
- Tests performance, accessibility, best practices, and SEO scores
- Captures Core Web Vitals (FCP, LCP, CLS, TBT, Speed Index)
- Sortable dashboard by any metric
- Filter by device type or URL
- Historical data retention
- Responsive design

## Configuration

### Adding/Removing Sites
Edit the `universities.json` file in your repository root:

```json
[
  {"name": "Your Site Name", "url": "https://yoursite.com"},
  {"name": "Another Site", "url": "https://anotherdomain.com"},
  {"name": "Example Site", "url": "https://example.org"}
]
```

The JSON format requires:
- `name`: A friendly display name for your site
- `url`: The full URL including https://

### Changing Schedule
Edit the cron schedule in `.github/workflows/lighthouse-monitor.yml`:

```yaml
schedule:
  - cron: '0 6 * * *'  # Daily at 6 AM UTC
```

### Customizing Metrics
The script captures these metrics by default:
- Performance, Accessibility, Best Practices, SEO scores
- First Contentful Paint (FCP)
- Largest Contentful Paint (LCP)
- Cumulative Layout Shift (CLS)
- Total Blocking Time (TBT)
- Speed Index
- Time to Interactive (TTI)

To add more metrics, modify the `metrics` section in the `run_lighthouse_test` method.

## File Structure

```
your-repo/
├── lighthouse_monitor.py          # Main Python script
├── universities.json              # Sites configuration file
├── .github/workflows/
│   └── lighthouse-monitor.yml     # GitHub Actions workflow
├── lighthouse_results/            # JSON data files (auto-created)
│   ├── lighthouse_results_2025-01-15.json
│   └── lighthouse_results_latest.json
└── docs/                          # GitHub Pages site (auto-created)
    ├── index.html                 # Dashboard HTML
    └── data.js                    # Dashboard data
```

## Troubleshooting

### Tests Failing
- Check that all URLs are accessible and return 200 status codes
- Verify URLs include the protocol (https://)
- Check GitHub Actions logs for specific error messages

### Dashboard Not Updating
- Ensure GitHub Pages is enabled in repository settings
- Check that the workflow has proper permissions to push to the repository
- Verify the `docs/` directory is being created and populated

### Local Testing
```bash
# Test a single URL manually
lighthouse https://example.com --output=json --chrome-flags="--headless"

# Run the Python script locally
python lighthouse_monitor.py
```

## Dashboard Features

The generated dashboard includes:
- **Sortable Results**: Sort by performance, accessibility, SEO, or date
- **Device Filtering**: View mobile-only or desktop-only results
- **URL Search**: Filter results by website name or URL
- **Color-coded Scores**: Green (90+), Orange (50-89), Red (<50)
- **Core Web Vitals**: Key performance metrics displayed
- **Historical Data**: All previous test results retained

## Customization

The dashboard can be customized by modifying the HTML template in the `generate_html_template` method. You can:
- Change the styling/colors
- Add new metrics to display
- Modify the layout or add charts
- Add additional filtering options

## Security Notes

- The script runs in GitHub Actions with standard permissions
- No sensitive data is stored (only public website performance metrics)
- All results are public via GitHub Pages
- Consider using private repositories if you're testing internal/private sites
# CrUX-Only Performance Monitoring

## Why CrUX Instead of Lighthouse?

We've switched from Lighthouse lab tests to **Chrome UX Report (CrUX) field data** for several critical reasons:

### ⚡ Speed
- **CrUX**: ~2-3 minutes for 130 universities (API calls)
- **Lighthouse**: 40-50+ minutes with many timeouts and failures

### 📊 Real User Data
- **CrUX**: Actual performance metrics from real Chrome users
- **Lighthouse**: Synthetic lab tests that don't reflect real-world usage

### 🆓 GitHub Actions Friendly
- **CrUX**: Lightweight, no browser needed, fits free tier
- **Lighthouse**: Heavy, requires Chrome, often times out

### 🎯 More Reliable
- **CrUX**: Consistent API responses, no site-specific errors
- **Lighthouse**: 50%+ failure rate due to timeouts, 405 errors, connection issues

## Getting Your CrUX API Key

### Step 1: Get a Google Cloud API Key
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the **Chrome UX Report API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Chrome UX Report API"
   - Click "Enable"

### Step 2: Create API Key
1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "API Key"
3. Copy your API key
4. (Optional) Restrict the key to only "Chrome UX Report API" for security

### Step 3: Add to GitHub Secrets
1. Go to your GitHub repository
2. Settings > Secrets and variables > Actions
3. Click "New repository secret"
4. Name: `CRUX_API_KEY`
5. Value: Paste your API key
6. Click "Add secret"

### Step 4: Test Locally
```bash
# Set environment variable
export CRUX_API_KEY="your-api-key-here"

# Run the script
python crux_only_monitor.py
```

## Understanding CrUX Data

### Metrics Collected
- **Largest Contentful Paint (LCP)**: Load performance
- **First Input Delay (FID)**: Interactivity
- **Cumulative Layout Shift (CLS)**: Visual stability
- **First Contentful Paint (FCP)**: Initial render
- **Interaction to Next Paint (INP)**: Responsiveness
- **Time to First Byte (TTFB)**: Server response

### Scores
CrUX provides percentage of users experiencing "good" performance:
- **90-100**: Excellent (green)
- **50-89**: Needs improvement (orange)
- **0-49**: Poor (red)

### Data Freshness
- CrUX data is aggregated over 28 days
- Updated regularly by Google
- Represents real Chrome users visiting these sites

## Comparison: CrUX vs Lighthouse

| Feature | CrUX | Lighthouse |
|---------|------|-----------|
| Data Type | Real user field data | Synthetic lab data |
| Speed (130 sites) | ~3 minutes | 40-50+ minutes |
| Reliability | High (API-based) | Low (50%+ failures) |
| GitHub Actions | ✅ Works great | ❌ Too slow |
| Real-world accuracy | ✅ Actual users | ⚠️ Simulated |
| Cost | Free (25K req/day) | Free but slow |

## Migration Benefits

### Before (Lighthouse)
```
- 520 tests (130 × 2 devices × 2 runs)
- ~90 seconds per test
- 50%+ failure rate
- 40-50+ minutes total
- Chrome crashes, timeouts, 405 errors
```

### After (CrUX)
```
- 260 API calls (130 × 2 devices)
- ~0.5 seconds per call
- <5% failure rate
- ~3 minutes total
- Reliable, consistent data
```

## Dashboard Compatibility

The CrUX data works with your existing dashboard! The script outputs the same JSON structure with:
- `scores`: Performance metrics (0-100 scale)
- `metrics`: Raw metric values (milliseconds, etc.)
- `test_type`: Set to "field" to distinguish from "lab"
- `data_source`: "Chrome UX Report"

## Notes

- Some universities may not have CrUX data if they don't get enough Chrome traffic
- Data is aggregated over 28 days, so changes take time to reflect
- More accurate than Lighthouse for understanding real user experience
- Perfect for tracking trends over time

## Support

If you have issues:
1. Check your API key is valid
2. Verify the API is enabled in Google Cloud Console
3. Check your quota hasn't been exceeded (25,000 requests/day free tier)
4. Review logs: `cat crux_monitor.log`

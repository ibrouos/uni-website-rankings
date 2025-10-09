# Top 50 Universities - Optimized Lighthouse Testing

## Why Top 50 Only?

Testing all 130 universities was taking **40-50+ minutes** with a **50%+ failure rate**. By focusing on the **top 50 universities**, we get:

### ⚡ Speed Improvements
- **Before**: 130 sites = 40-50+ minutes
- **After**: 50 sites = **~10-12 minutes**
- **62% faster** with more reliable results

### 📊 Better Data Quality
- Focus on the most important/popular universities
- More consistent results (fewer timeouts)
- Daily tracking remains meaningful
- Still get comprehensive coverage

### 💰 GitHub Actions Friendly
- Fits well within free tier limits
- Reduces risk of timeouts
- Lower failure rate = more complete data

## Which Universities Are Included?

The `universities_top50.json` includes:
- Russell Group universities
- Top-ranked UK institutions
- Major city universities
- Popular student destinations

You can easily modify the list to include different universities based on your priorities.

## Key Optimizations

### 1. Single Run Per Site/Device
- **Before**: 2 runs × 2 devices = 4 tests per site
- **After**: 1 run × 2 devices = 2 tests per site
- **50% reduction** in test count

### 2. Faster Timeouts
- Test timeout: 120s (down from 180s)
- Max wait for load: 45s (configurable)
- Quicker failure detection

### 3. Optimized Chrome Flags
```bash
--disable-dev-shm-usage  # Prevents memory issues
--disable-storage-reset  # Speeds up tests
--max-wait-for-load=45000 # Don't wait forever
```

### 4. More Workers
- 16 concurrent workers (vs 12 before)
- Better parallelization
- Faster completion

## Performance Comparison

### 130 Universities (Old)
```
- 520 tests total (130 × 2 devices × 2 runs)
- 12 workers
- 40-50+ minutes runtime
- 50%+ failure rate
- Many timeouts and errors
```

### 50 Universities (New)
```
- 100 tests total (50 × 2 devices × 1 run)
- 16 workers  
- 10-12 minutes runtime
- <10% failure rate
- Reliable, consistent data
```

## Test Methodology

### Throttling (PageSpeed Insights Settings)
**Mobile:**
- RTT: 150ms
- Throughput: 1638.4 Kbps
- CPU: 4x slowdown

**Desktop:**
- RTT: 40ms  
- Throughput: 10240 Kbps
- CPU: 1x (no slowdown)

### Metrics Collected
- Performance score (0-100)
- Accessibility score (0-100)
- Best Practices score (0-100)
- SEO score (0-100)
- First Contentful Paint (ms)
- Largest Contentful Paint (ms)
- Cumulative Layout Shift
- Total Blocking Time (ms)
- Speed Index (ms)
- Time to Interactive (ms)

## Running Locally

### Test Top 50
```bash
python lighthouse_top50.py
```

### Test Custom List
1. Create your own JSON file (e.g., `universities_custom.json`)
2. Modify the script to load your file:
```python
sites_to_test = load_sites_from_json("universities_custom.json")
```

### Quick Test (5 universities)
```bash
# Take first 5 from top50 list
head -n 22 universities_top50.json > universities_test.json
echo "]" >> universities_test.json
```

## Expanding the List

Want to add more universities? Edit `universities_top50.json`:

```json
[
  {"name": "Your University", "url": "https://www.youruniversity.ac.uk"},
  ...
]
```

**Guidelines:**
- Keep under 70-80 sites for reliable GitHub Actions runs
- Test locally first with new additions
- Some sites may still timeout (that's okay)

## Monitoring & Logs

### View Progress
```bash
tail -f lighthouse_top50.log
```

### Check Last Run
```bash
cat lighthouse_top50.log | grep "Completed in"
```

### Success Rate
```bash
cat lighthouse_top50.log | grep -E "✅|❌" | tail -5
```

## Troubleshooting

### Still Too Slow?
- Reduce to top 30 (`head -n 122 universities_top50.json`)
- Increase timeout to 180s
- Run tests less frequently (weekly instead of daily)

### High Failure Rate?
- Some universities have slow/unreliable sites
- Check which ones are failing: `grep "❌" lighthouse_top50.log`
- Remove problematic sites from the list
- Increase timeout for specific sites

### Out of Memory?
- GitHub Actions has 7GB RAM limit
- Reduce workers to 12 instead of 16
- Reduce number of sites

## Future Enhancements

### Tier System
Consider creating tiers:
- **Tier 1** (Daily): Top 20 most important
- **Tier 2** (Weekly): Next 30
- **Tier 3** (Monthly): Remaining 80

### Smart Retry
- Automatically retry failed tests once
- Skip consistently failing sites
- Alert on new failures

### Adaptive Testing
- Increase frequency for universities with recent changes
- Reduce frequency for stable sites
- Smart scheduling based on patterns

## Cost Comparison

### GitHub Actions (Free Tier)
- 2,000 minutes/month
- ~10-12 minutes per run
- **~180 runs/month** = 6 runs/day ✅

### All 130 Universities
- ~45 minutes per run  
- **~44 runs/month** = 1.5 runs/day ❌

**Verdict**: Top 50 is sustainable on free tier! 🎉

#!/usr/bin/env python3
"""
Lighthouse Performance Monitor
Runs daily Lighthouse tests and generates a GitHub Pages dashboard
"""

import json
import subprocess
import os
from datetime import datetime, date
from pathlib import Path
import logging
from typing import Dict, List, Any
import tempfile
import asyncio
import concurrent.futures
from functools import partial
import re
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('lighthouse_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def slugify(text: str) -> str:
    """Convert university name to URL-safe slug"""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')


class LighthouseMonitor:
    def __init__(self, sites: List[Dict[str, str]], output_dir: str = "lighthouse_results", max_workers: int = 16, runs_per_test: int = 2):
        self.sites = sites
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.results_dir = Path("results")
        self.results_dir.mkdir(exist_ok=True)
        self.today = date.today().isoformat()
        self.max_workers = max_workers  # Number of concurrent tests
        self.runs_per_test = runs_per_test  # Number of runs per site/device for consistency
        
    def run_lighthouse_test(self, site: Dict[str, str], device: str, run_number: int = 1) -> Dict[str, Any]:
        """Run Lighthouse test for a single site and device type"""
        url = site['url']
        name = site['name']
        
        logger.info(f"Testing {name} ({url}) on {device} - Run {run_number}")
        
        # Lighthouse CLI command matching PageSpeed Insights settings
        cmd = [
            "lighthouse",
            url,
            "--output=json",
            "--quiet",
            "--chrome-flags=--headless --no-sandbox",
            "--only-categories=performance,accessibility,best-practices,seo",
            "--throttling-method=simulate",  # More accurate simulation
        ]
        
        # Add device-specific flags matching PageSpeed Insights
        if device == "mobile":
            cmd.extend([
                "--emulated-form-factor=mobile",
                "--throttling.rttMs=150",
                "--throttling.throughputKbps=1638.4",
                "--throttling.requestLatencyMs=150",
                "--throttling.downloadThroughputKbps=1638.4",
                "--throttling.uploadThroughputKbps=675",
                "--throttling.cpuSlowdownMultiplier=4"
            ])
        else:  # desktop
            cmd.extend([
                "--emulated-form-factor=desktop",
                "--throttling.rttMs=40",
                "--throttling.throughputKbps=10240",
                "--throttling.requestLatencyMs=0",
                "--throttling.downloadThroughputKbps=10240",
                "--throttling.uploadThroughputKbps=10240",
                "--throttling.cpuSlowdownMultiplier=1"
            ])
        
        try:
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as tmp_file:
                # Run lighthouse and save to temp file
                result = subprocess.run(
                    cmd + [f"--output-path={tmp_file.name}"],
                    capture_output=True,
                    text=True,
                    timeout=90  # 90 second timeout per test
                )
                
                if result.returncode != 0:
                    logger.error(f"Lighthouse failed for {name} ({url}) on {device}: {result.stderr}")
                    return None
                
                # Read the results
                with open(tmp_file.name, 'r') as f:
                    lighthouse_data = json.load(f)
                
                # Extract key metrics
                categories = lighthouse_data.get('categories', {})
                audits = lighthouse_data.get('audits', {})
                
                # Core Web Vitals and performance metrics
                metrics = {
                    'name': name,
                    'url': url,
                    'device': device,
                    'timestamp': datetime.now().isoformat(),
                    'lighthouse_version': lighthouse_data.get('lighthouseVersion', 'unknown'),
                    'test_type': 'lab',  # Lab data (simulated)
                    'run_number': run_number,  # Track which run this was
                    'scores': {
                        'performance': categories.get('performance', {}).get('score', 0) * 100,
                        'accessibility': categories.get('accessibility', {}).get('score', 0) * 100,
                        'best_practices': categories.get('best-practices', {}).get('score', 0) * 100,
                        'seo': categories.get('seo', {}).get('score', 0) * 100
                    },
                    'metrics': {
                        'first_contentful_paint': audits.get('first-contentful-paint', {}).get('numericValue', 0),
                        'largest_contentful_paint': audits.get('largest-contentful-paint', {}).get('numericValue', 0),
                        'cumulative_layout_shift': audits.get('cumulative-layout-shift', {}).get('numericValue', 0),
                        'total_blocking_time': audits.get('total-blocking-time', {}).get('numericValue', 0),
                        'speed_index': audits.get('speed-index', {}).get('numericValue', 0),
                        'interactive': audits.get('interactive', {}).get('numericValue', 0)
                    },
                    'throttling_config': {
                        'method': 'simulate',
                        'device': device
                    }
                }
                
                # Clean up temp file
                os.unlink(tmp_file.name)
                
                return metrics
                
        except subprocess.TimeoutExpired:
            logger.error(f"Lighthouse test timed out for {name} ({url}) on {device}")
            return None
        except Exception as e:
            logger.error(f"Error running Lighthouse for {name} ({url}) on {device}: {str(e)}")
            return None
    
    def run_all_tests(self) -> List[Dict[str, Any]]:
        """Run Lighthouse tests for all sites on both mobile and desktop concurrently"""
        # Create list of all test tasks (including multiple runs)
        test_tasks = []
        for site in self.sites:
            for device in ['mobile', 'desktop']:
                for run in range(1, self.runs_per_test + 1):
                    test_tasks.append((site, device, run))
        
        total_tests = len(test_tasks)
        logger.info(f"Running {total_tests} tests ({len(self.sites)} sites × 2 devices × {self.runs_per_test} runs) with {self.max_workers} concurrent workers")
        logger.info(f"Estimated time: {(total_tests * 60) / self.max_workers / 60:.1f} minutes")
        
        # Run tests concurrently using ThreadPoolExecutor
        all_results = []
        completed = 0
        failed = 0
        start_time = datetime.now()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(self.run_lighthouse_test, site, device, run): (site, device, run)
                for site, device, run in test_tasks
            }
            
            # Process completed tests
            for future in concurrent.futures.as_completed(future_to_task):
                site, device, run = future_to_task[future]
                completed += 1
                
                # Calculate progress stats
                elapsed = (datetime.now() - start_time).total_seconds()
                avg_time_per_test = elapsed / completed
                remaining = total_tests - completed
                eta_seconds = avg_time_per_test * remaining
                eta_minutes = eta_seconds / 60
                
                try:
                    result = future.result()
                    if result:
                        all_results.append(result)
                        logger.info(f"✅ [{completed}/{total_tests}] {site['name']} ({device}) Run {run} - ETA: {eta_minutes:.1f}m")
                    else:
                        failed += 1
                        logger.warning(f"❌ [{completed}/{total_tests}] {site['name']} ({device}) Run {run} FAILED")
                except Exception as e:
                    failed += 1
                    logger.error(f"❌ [{completed}/{total_tests}] {site['name']} ({device}) Run {run}: {str(e)}")
        
        total_time = (datetime.now() - start_time).total_seconds() / 60
        logger.info(f"\n{'='*60}")
        logger.info(f"Completed all tests in {total_time:.1f} minutes")
        logger.info(f"✅ Successful: {len(all_results)} | ❌ Failed: {failed} | Total: {total_tests}")
        logger.info(f"{'='*60}\n")
        return all_results
    
    def save_results(self, results: List[Dict[str, Any]]):
        """Save results to JSON file (both old format and new per-university format)"""
        # Save in old format (for backward compatibility)
        results_file = self.output_dir / f"lighthouse_results_{self.today}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {results_file}")
        
        # Also update the latest results file
        latest_file = self.output_dir / "lighthouse_results_latest.json"
        with open(latest_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Save in new per-university format
        self.save_per_university_results(results)
    
    def save_per_university_results(self, new_results: List[Dict[str, Any]]):
        """Save results to per-university files"""
        # Group new results by university
        university_results = defaultdict(list)
        for result in new_results:
            uni_name = result.get('name')
            if uni_name:
                university_results[uni_name].append(result)
        
        # Update each university's file
        for uni_name, results in university_results.items():
            slug = slugify(uni_name)
            uni_file = self.results_dir / f"{slug}.json"
            
            # Load existing data if file exists
            existing_data = {'results': []}
            if uni_file.exists():
                try:
                    with open(uni_file, 'r') as f:
                        existing_data = json.load(f)
                except Exception as e:
                    logger.warning(f"Could not load existing data for {uni_name}: {e}")
            
            # Append new results
            all_results = existing_data.get('results', []) + results
            
            # Sort by timestamp
            all_results.sort(key=lambda x: x.get('timestamp', ''))
            
            # Update metadata
            uni_data = {
                'name': uni_name,
                'slug': slug,
                'url': results[0].get('url', '') if results else existing_data.get('url', ''),
                'last_updated': all_results[-1].get('timestamp', '') if all_results else '',
                'total_tests': len(all_results),
                'results': all_results
            }
            
            # Save updated file
            with open(uni_file, 'w') as f:
                json.dump(uni_data, f, indent=2)
            
            logger.info(f"Updated {slug}.json ({len(results)} new results, {len(all_results)} total)")
        
        # Update index file
        self.update_index_file()
    
    def update_index_file(self):
        """Update the index file with all universities"""
        index_data = []
        
        for uni_file in sorted(self.results_dir.glob("*.json")):
            if uni_file.name == "index.json":
                continue
            
            try:
                with open(uni_file, 'r') as f:
                    uni_data = json.load(f)
                    index_data.append({
                        'name': uni_data.get('name'),
                        'slug': uni_data.get('slug'),
                        'url': uni_data.get('url'),
                        'total_tests': uni_data.get('total_tests', 0),
                        'last_updated': uni_data.get('last_updated')
                    })
            except Exception as e:
                logger.warning(f"Error reading {uni_file.name}: {e}")
        
        index_file = self.results_dir / "index.json"
        with open(index_file, 'w') as f:
            json.dump(index_data, f, indent=2)
        
        logger.info(f"Updated index.json with {len(index_data)} universities")
    
    def generate_dashboard(self):
        """Generate HTML dashboard for GitHub Pages"""
        dashboard_generator = DashboardGenerator(self.results_dir)
        dashboard_generator.create_dashboard()

class DashboardGenerator:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.docs_dir = Path("docs")  # GitHub Pages directory
        self.docs_dir.mkdir(exist_ok=True)
    
    def load_all_results(self) -> List[Dict[str, Any]]:
        """Load all historical results"""
        all_results = []
        
        # Load all daily result files
        for result_file in self.data_dir.glob("lighthouse_results_*.json"):
            if result_file.name == "lighthouse_results_latest.json":
                continue
                
            try:
                with open(result_file, 'r') as f:
                    daily_results = json.load(f)
                    all_results.extend(daily_results)
            except Exception as e:
                logger.error(f"Error loading {result_file}: {str(e)}")
        
        return all_results
    
    def create_dashboard(self):
        """Create the HTML dashboard"""
        all_results = self.load_all_results()
        
        # Copy results data to docs directory for JavaScript access
        data_js_file = self.docs_dir / "data.js"
        with open(data_js_file, 'w') as f:
            f.write(f"window.lighthouseData = {json.dumps(all_results, indent=2)};")
        
        # Create the HTML dashboard
        html_content = self.generate_html_template()
        
        index_file = self.docs_dir / "index.html"
        with open(index_file, 'w') as f:
            f.write(html_content)
        
        logger.info(f"Dashboard generated at {index_file}")
    
    def generate_html_template(self) -> str:
        """Generate the HTML template for the dashboard"""
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lighthouse Performance Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .controls { background: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .controls select, .controls input { margin: 0 10px 10px 0; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
        .results-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .result-card { background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .site-name { font-size: 18px; font-weight: bold; margin-bottom: 10px; color: #333; }
        .device-badge { display: inline-block; padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; margin-left: 10px; }
        .mobile { background: #e3f2fd; color: #1976d2; }
        .desktop { background: #f3e5f5; color: #7b1fa2; }
        .scores { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 15px 0; }
        .score { text-align: center; padding: 10px; border-radius: 6px; }
        .score-label { font-size: 12px; color: #666; }
        .score-value { font-size: 20px; font-weight: bold; }
        .score-good { background: #e8f5e8; color: #2e7d32; }
        .score-average { background: #fff3e0; color: #f57c00; }
        .score-poor { background: #ffebee; color: #d32f2f; }
        .metrics { margin-top: 15px; }
        .metric { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #eee; }
        .metric:last-child { border-bottom: none; }
        .timestamp { font-size: 12px; color: #666; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚦 Lighthouse Performance Dashboard</h1>
            <p>Monitor website performance, accessibility, and SEO scores</p>
        </div>
        
        <div class="controls">
            <select id="sortBy">
                <option value="performance">Sort by Performance</option>
                <option value="accessibility">Sort by Accessibility</option>
                <option value="best_practices">Sort by Best Practices</option>
                <option value="seo">Sort by SEO</option>
                <option value="timestamp">Sort by Date</option>
            </select>
            
            <select id="deviceFilter">
                <option value="all">All Devices</option>
                <option value="mobile">Mobile Only</option>
                <option value="desktop">Desktop Only</option>
            </select>
            
            <input type="text" id="urlFilter" placeholder="Filter by name or URL..." />
        </div>
        
        <div id="results" class="results-grid"></div>
    </div>
    
    <script src="data.js"></script>
    <script>
        let currentData = window.lighthouseData || [];
        
        function getScoreClass(score) {
            if (score >= 90) return 'score-good';
            if (score >= 50) return 'score-average';
            return 'score-poor';
        }
        
        function formatMetric(value, unit = 'ms') {
            if (value < 1000) return `${Math.round(value)}${unit}`;
            return `${(value / 1000).toFixed(1)}s`;
        }
        
        function renderResults(data) {
            const resultsContainer = document.getElementById('results');
            resultsContainer.innerHTML = '';
            
            data.forEach(result => {
                const card = document.createElement('div');
                card.className = 'result-card';
                
                const url = new URL(result.url);
                const siteName = url.hostname.replace('www.', '');
                
                card.innerHTML = `
                    <div class="site-name">
                        ${siteName}
                        <span class="device-badge ${result.device}">${result.device}</span>
                    </div>
                    
                    <div class="scores">
                        <div class="score ${getScoreClass(result.scores.performance)}">
                            <div class="score-label">Performance</div>
                            <div class="score-value">${Math.round(result.scores.performance)}</div>
                        </div>
                        <div class="score ${getScoreClass(result.scores.accessibility)}">
                            <div class="score-label">Accessibility</div>
                            <div class="score-value">${Math.round(result.scores.accessibility)}</div>
                        </div>
                        <div class="score ${getScoreClass(result.scores.best_practices)}">
                            <div class="score-label">Best Practices</div>
                            <div class="score-value">${Math.round(result.scores.best_practices)}</div>
                        </div>
                        <div class="score ${getScoreClass(result.scores.seo)}">
                            <div class="score-label">SEO</div>
                            <div class="score-value">${Math.round(result.scores.seo)}</div>
                        </div>
                    </div>
                    
                    <div class="metrics">
                        <div class="metric">
                            <span>First Contentful Paint</span>
                            <span>${formatMetric(result.metrics.first_contentful_paint)}</span>
                        </div>
                        <div class="metric">
                            <span>Largest Contentful Paint</span>
                            <span>${formatMetric(result.metrics.largest_contentful_paint)}</span>
                        </div>
                        <div class="metric">
                            <span>Cumulative Layout Shift</span>
                            <span>${result.metrics.cumulative_layout_shift.toFixed(3)}</span>
                        </div>
                        <div class="metric">
                            <span>Speed Index</span>
                            <span>${formatMetric(result.metrics.speed_index)}</span>
                        </div>
                    </div>
                    
                    <div class="timestamp">
                        Last tested: ${new Date(result.timestamp).toLocaleString()}
                    </div>
                `;
                
                resultsContainer.appendChild(card);
            });
        }
        
        function filterAndSort() {
            let filteredData = [...currentData];
            
            // Apply URL filter
            const urlFilter = document.getElementById('urlFilter').value.toLowerCase();
            if (urlFilter) {
                filteredData = filteredData.filter(result => 
                    result.name.toLowerCase().includes(urlFilter) || 
                    result.url.toLowerCase().includes(urlFilter)
                );
            }
            
            // Apply device filter
            const deviceFilter = document.getElementById('deviceFilter').value;
            if (deviceFilter !== 'all') {
                filteredData = filteredData.filter(result => result.device === deviceFilter);
            }
            
            // Sort data
            const sortBy = document.getElementById('sortBy').value;
            filteredData.sort((a, b) => {
                if (sortBy === 'timestamp') {
                    return new Date(b.timestamp) - new Date(a.timestamp);
                }
                return b.scores[sortBy] - a.scores[sortBy];
            });
            
            renderResults(filteredData);
        }
        
        // Event listeners
        document.getElementById('sortBy').addEventListener('change', filterAndSort);
        document.getElementById('deviceFilter').addEventListener('change', filterAndSort);
        document.getElementById('urlFilter').addEventListener('input', filterAndSort);
        
        // Initial render
        filterAndSort();
    </script>
</body>
</html>'''

def load_sites_from_json(filename: str = "universities.json") -> List[Dict[str, str]]:
    """Load sites configuration from JSON file"""
    try:
        with open(filename, 'r') as f:
            sites = json.load(f)
        
        # Validate the structure
        for site in sites:
            if 'name' not in site or 'url' not in site:
                raise ValueError(f"Invalid site entry: {site}. Must have 'name' and 'url' fields.")
        
        logger.info(f"Loaded {len(sites)} sites from {filename}")
        return sites
        
    except FileNotFoundError:
        logger.error(f"File {filename} not found. Please create it with your sites list.")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {filename}: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error loading sites from {filename}: {str(e)}")
        raise

def main():
    # Load sites from JSON file
    try:
        sites_to_test = load_sites_from_json()
    except Exception as e:
        logger.error(f"Failed to load sites configuration: {str(e)}")
        return
    
    # Determine optimal number of workers based on site count
    # More workers for larger batches to reduce total time
    if len(sites_to_test) <= 10:
        max_workers = 8
    elif len(sites_to_test) <= 50:
        max_workers = 16
    else:
        max_workers = 20  # Aggressive parallelism for large batches
    
    # Number of runs per test for consistency (2 is good balance)
    runs_per_test = 2
    
    logger.info(f"Using {max_workers} concurrent workers for {len(sites_to_test)} sites ({runs_per_test} runs each)")
    
    # Initialize monitor
    monitor = LighthouseMonitor(sites_to_test, max_workers=max_workers, runs_per_test=runs_per_test)
    
    # Run tests
    logger.info("Starting Lighthouse tests...")
    results = monitor.run_all_tests()
    
    if results:
        # Save results
        monitor.save_results(results)
        
        # Generate dashboard
        logger.info("Generating dashboard...")
        monitor.generate_dashboard()
        
        logger.info("All tasks completed successfully!")
    else:
        logger.error("No results to save")

if __name__ == "__main__":
    main()
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

class LighthouseMonitor:
    def __init__(self, sites: List[Dict[str, str]], output_dir: str = "lighthouse_results"):
        self.sites = sites
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.today = date.today().isoformat()
        
    def run_lighthouse_test(self, site: Dict[str, str], device: str) -> Dict[str, Any]:
        """Run Lighthouse test for a single site and device type"""
        url = site['url']
        name = site['name']
        
        logger.info(f"Testing {name} ({url}) on {device}")
        
        # Lighthouse CLI command
        cmd = [
            "lighthouse",
            url,
            "--output=json",
            "--quiet",
            "--chrome-flags=--headless",
            f"--preset={device}",  # 'mobile' or 'desktop'
            "--only-categories=performance,accessibility,best-practices,seo"
        ]
        
        try:
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as tmp_file:
                # Run lighthouse and save to temp file
                result = subprocess.run(
                    cmd + [f"--output-path={tmp_file.name}"],
                    capture_output=True,
                    text=True,
                    timeout=120  # 2 minute timeout
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
        """Run Lighthouse tests for all sites on both mobile and desktop"""
        all_results = []
        
        for site in self.sites:
            for device in ['mobile', 'desktop']:
                result = self.run_lighthouse_test(site, device)
                if result:
                    all_results.append(result)
        
        return all_results
    
    def save_results(self, results: List[Dict[str, Any]]):
        """Save results to JSON file"""
        results_file = self.output_dir / f"lighthouse_results_{self.today}.json"
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Results saved to {results_file}")
        
        # Also update the latest results file
        latest_file = self.output_dir / "lighthouse_results_latest.json"
        with open(latest_file, 'w') as f:
            json.dump(results, f, indent=2)
    
    def generate_dashboard(self):
        """Generate HTML dashboard for GitHub Pages"""
        dashboard_generator = DashboardGenerator(self.output_dir)
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
    
    # Initialize monitor
    monitor = LighthouseMonitor(sites_to_test)
    
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
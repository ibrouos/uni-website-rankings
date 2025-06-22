#!/usr/bin/env python3
"""
Dashboard Builder
Builds the static HTML dashboard from existing Lighthouse results
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DashboardGenerator:
    def __init__(self, data_dir: Path = Path("lighthouse_results")):
        self.data_dir = data_dir
        self.docs_dir = Path("docs")  # GitHub Pages directory
        self.docs_dir.mkdir(exist_ok=True)
    
    def load_all_results(self) -> List[Dict[str, Any]]:
        """Load all historical results"""
        all_results = []
        
        if not self.data_dir.exists():
            logger.warning(f"Data directory {self.data_dir} does not exist")
            return all_results
        
        # Load all daily result files
        result_files = list(self.data_dir.glob("lighthouse_results_*.json"))
        logger.info(f"Found {len(result_files)} result files")
        
        for result_file in result_files:
            if result_file.name == "lighthouse_results_latest.json":
                continue
                
            try:
                with open(result_file, 'r') as f:
                    daily_results = json.load(f)
                    all_results.extend(daily_results)
                    logger.info(f"Loaded {len(daily_results)} results from {result_file.name}")
            except Exception as e:
                logger.error(f"Error loading {result_file}: {str(e)}")
        
        logger.info(f"Total results loaded: {len(all_results)}")
        return all_results
    
    def create_dashboard(self):
        """Create the HTML dashboard"""
        all_results = self.load_all_results()
        
        if not all_results:
            logger.warning("No results found - creating empty dashboard")
        
        # Copy results data to docs directory for JavaScript access
        data_js_file = self.docs_dir / "data.js"
        with open(data_js_file, 'w') as f:
            f.write(f"window.lighthouseData = {json.dumps(all_results, indent=2)};")
        
        # Create the HTML dashboard
        html_content = self.generate_html_template()
        
        index_file = self.docs_dir / "index.html"
        with open(index_file, 'w') as f:
            f.write(html_content)
        
        logger.info(f"Dashboard generated with {len(all_results)} results")
        logger.info(f"Dashboard files created in {self.docs_dir}")
        
        # List created files
        for file in self.docs_dir.iterdir():
            logger.info(f"Created: {file.name} ({file.stat().st_size} bytes)")
    
    def generate_html_template(self) -> str:
        """Generate the HTML template for the dashboard"""
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎓 University Website Performance Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { 
            background: white; 
            padding: 30px; 
            border-radius: 12px; 
            margin-bottom: 30px; 
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            text-align: center;
        }
        .header h1 { 
            font-size: 2.5rem; 
            color: #2d3748; 
            margin-bottom: 10px;
        }
        .header p { 
            color: #718096; 
            font-size: 1.1rem;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .stat-number {
            font-size: 2rem;
            font-weight: bold;
            color: #4299e1;
        }
        .stat-label {
            color: #718096;
            margin-top: 5px;
        }
        .controls { 
            background: white; 
            padding: 20px; 
            border-radius: 12px; 
            margin-bottom: 30px; 
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .controls select, .controls input { 
            margin: 0 10px 10px 0; 
            padding: 12px; 
            border: 2px solid #e2e8f0; 
            border-radius: 8px; 
            font-size: 14px;
            transition: border-color 0.2s;
        }
        .controls select:focus, .controls input:focus {
            outline: none;
            border-color: #4299e1;
        }
        .results-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); 
            gap: 25px; 
        }
        .result-card { 
            background: white; 
            border-radius: 12px; 
            padding: 25px; 
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .result-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.15);
        }
        .site-name { 
            font-size: 18px; 
            font-weight: bold; 
            margin-bottom: 15px; 
            color: #2d3748;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .device-badge { 
            padding: 6px 12px; 
            border-radius: 20px; 
            font-size: 12px; 
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .mobile { background: #bee3f8; color: #2b6cb0; }
        .desktop { background: #e9d8fd; color: #6b46c1; }
        .scores { 
            display: grid; 
            grid-template-columns: 1fr 1fr; 
            gap: 15px; 
            margin: 20px 0; 
        }
        .score { 
            text-align: center; 
            padding: 15px; 
            border-radius: 8px;
            transition: transform 0.1s;
        }
        .score:hover { transform: scale(1.02); }
        .score-label { 
            font-size: 11px; 
            color: #718096; 
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 5px;
        }
        .score-value { 
            font-size: 24px; 
            font-weight: bold; 
        }
        .score-good { background: #c6f6d5; color: #22543d; }
        .score-average { background: #feebc8; color: #c05621; }
        .score-poor { background: #fed7d7; color: #c53030; }
        .metrics { 
            margin-top: 20px; 
            border-top: 1px solid #e2e8f0;
            padding-top: 15px;
        }
        .metric { 
            display: flex; 
            justify-content: space-between; 
            padding: 8px 0; 
            border-bottom: 1px solid #f7fafc;
            font-size: 14px;
        }
        .metric:last-child { border-bottom: none; }
        .metric-label { color: #4a5568; }
        .metric-value { font-weight: 600; color: #2d3748; }
        .timestamp { 
            font-size: 12px; 
            color: #a0aec0; 
            margin-top: 15px;
            text-align: center;
            padding-top: 10px;
            border-top: 1px solid #f7fafc;
        }
        .no-results {
            text-align: center;
            padding: 60px 20px;
            color: #718096;
            font-size: 18px;
        }
        .loading {
            text-align: center;
            padding: 60px 20px;
            color: #4299e1;
            font-size: 18px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎓 University Website Performance Dashboard</h1>
            <p>Lighthouse performance monitoring for university websites</p>
        </div>
        
        <div class="stats" id="stats">
            <div class="stat-card">
                <div class="stat-number" id="totalSites">-</div>
                <div class="stat-label">Universities</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="totalTests">-</div>
                <div class="stat-label">Total Tests</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="avgPerformance">-</div>
                <div class="stat-label">Avg Performance</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="lastUpdate">-</div>
                <div class="stat-label">Last Updated</div>
            </div>
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
            
            <input type="text" id="urlFilter" placeholder="Search universities..." />
        </div>
        
        <div id="results" class="results-grid">
            <div class="loading">Loading dashboard...</div>
        </div>
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
        
        function updateStats() {
            if (currentData.length === 0) return;
            
            const uniqueSites = new Set(currentData.map(r => r.name)).size;
            const totalTests = currentData.length;
            const avgPerformance = Math.round(
                currentData.reduce((sum, r) => sum + r.scores.performance, 0) / totalTests
            );
            const lastUpdate = new Date(
                Math.max(...currentData.map(r => new Date(r.timestamp)))
            ).toLocaleDateString();
            
            document.getElementById('totalSites').textContent = uniqueSites;
            document.getElementById('totalTests').textContent = totalTests;
            document.getElementById('avgPerformance').textContent = avgPerformance;
            document.getElementById('lastUpdate').textContent = lastUpdate;
        }
        
        function renderResults(data) {
            const resultsContainer = document.getElementById('results');
            
            if (data.length === 0) {
                resultsContainer.innerHTML = '<div class="no-results">No results found matching your criteria.</div>';
                return;
            }
            
            resultsContainer.innerHTML = '';
            
            data.forEach(result => {
                const card = document.createElement('div');
                card.className = 'result-card';
                
                card.innerHTML = `
                    <div class="site-name">
                        <span>${result.name}</span>
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
                            <span class="metric-label">First Contentful Paint</span>
                            <span class="metric-value">${formatMetric(result.metrics.first_contentful_paint)}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Largest Contentful Paint</span>
                            <span class="metric-value">${formatMetric(result.metrics.largest_contentful_paint)}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Cumulative Layout Shift</span>
                            <span class="metric-value">${result.metrics.cumulative_layout_shift.toFixed(3)}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Speed Index</span>
                            <span class="metric-value">${formatMetric(result.metrics.speed_index)}</span>
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
        if (currentData.length > 0) {
            updateStats();
            filterAndSort();
        } else {
            document.getElementById('results').innerHTML = '<div class="no-results">No lighthouse results found. Run the monitoring workflow first!</div>';
        }
    </script>
</body>
</html>'''

def main():
    """Main function to build the dashboard"""
    logger.info("Starting dashboard build...")
    
    generator = DashboardGenerator()
    generator.create_dashboard()
    
    logger.info("Dashboard build completed!")

if __name__ == "__main__":
    main()
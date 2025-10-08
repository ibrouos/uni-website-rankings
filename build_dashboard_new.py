#!/usr/bin/env python3
"""
New Dashboard Builder
Builds a modern card-based dashboard with university cards and detail pages
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from statistics import mean
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UniversityDashboard:
    def __init__(self, results_dir: Path = Path("results"), docs_dir: Path = Path("docs")):
        self.results_dir = results_dir
        self.docs_dir = docs_dir
        self.docs_dir.mkdir(exist_ok=True)
        
        # Load configuration
        self.config = self.load_config()
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from config.json"""
        try:
            with open("config.json", 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning("config.json not found, using defaults")
            return {
                "display_settings": {"hidden_universities": []},
                "time_ranges": {"short_term_days": 7, "medium_term_days": 30},
                "chart_settings": {"default_view": "week"}
            }
    
    def calculate_averages(self, results: List[Dict[str, Any]], days: int) -> Optional[Dict[str, float]]:
        """Calculate averages for the last N days (or most recent if none in range)"""
        if not results:
            return None
        
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_results = [
            result for result in results 
            if datetime.fromisoformat(result.get('timestamp', '').replace('Z', '').split('+')[0]) >= cutoff_date
        ]
        
        # If no results in the time range, use the most recent results instead
        if not recent_results:
            # Sort by timestamp descending and take last 4 results (2 devices * 2 tests)
            sorted_results = sorted(results, key=lambda x: x.get('timestamp', ''), reverse=True)
            recent_results = sorted_results[:min(4, len(sorted_results))]
        
        # Group by device type and calculate averages
        mobile_results = [r for r in recent_results if r.get('device') == 'mobile']
        desktop_results = [r for r in recent_results if r.get('device') == 'desktop']
        
        def calc_device_averages(device_results):
            if not device_results:
                return {}
            
            scores = {}
            for metric in ['performance', 'accessibility', 'best_practices', 'seo']:
                values = [r['scores'][metric] for r in device_results if metric in r.get('scores', {})]
                scores[metric] = mean(values) if values else 0
            return scores
        
        return {
            'mobile': calc_device_averages(mobile_results),
            'desktop': calc_device_averages(desktop_results),
            'total_tests': len(recent_results)
        }
    
    def calculate_trend(self, results: List[Dict[str, Any]], days: int) -> str:
        """Calculate trend (up/down/stable) for performance score"""
        if len(results) < 2:
            return "stable"
        
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_results = sorted([
            r for r in results 
            if datetime.fromisoformat(r.get('timestamp', '').replace('Z', '').split('+')[0]) >= cutoff_date
        ], key=lambda x: x.get('timestamp', ''))
        
        if len(recent_results) < 2:
            return "stable"
        
        # Compare first and last performance scores
        first_score = recent_results[0]['scores'].get('performance', 0)
        last_score = recent_results[-1]['scores'].get('performance', 0)
        
        diff = last_score - first_score
        if diff > 2:
            return "up"
        elif diff < -2:
            return "down"
        return "stable"
    
    def load_university_data(self) -> List[Dict[str, Any]]:
        """Load all university data"""
        universities = []
        hidden = self.config['display_settings']['hidden_universities']
        
        for uni_file in sorted(self.results_dir.glob("*.json")):
            if uni_file.name == "index.json":
                continue
            
            try:
                with open(uni_file, 'r') as f:
                    uni_data = json.load(f)
                    
                # Skip hidden universities
                if uni_data.get('name') in hidden:
                    continue
                    
                # Calculate metrics
                results = uni_data.get('results', [])
                
                # 7-day averages
                week_avg = self.calculate_averages(results, 7)
                # 30-day averages  
                month_avg = self.calculate_averages(results, 30)
                # Trend
                trend = self.calculate_trend(results, 7)
                
                university = {
                    'name': uni_data.get('name'),
                    'slug': uni_data.get('slug'),
                    'url': uni_data.get('url'),
                    'total_tests': uni_data.get('total_tests', 0),
                    'last_updated': uni_data.get('last_updated'),
                    'week_averages': week_avg,
                    'month_averages': month_avg,
                    'trend': trend,
                    'results': results
                }
                
                universities.append(university)
                
            except Exception as e:
                logger.error(f"Error loading {uni_file.name}: {e}")
        
        return universities
    
    def create_main_dashboard(self, universities: List[Dict[str, Any]]):
        """Create the main dashboard with university cards"""
        html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎓 University Website Performance Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #2d3748;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .header {{
            background: white;
            padding: 40px;
            border-radius: 16px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 3rem;
            color: #2d3748;
            margin-bottom: 15px;
            font-weight: 700;
        }}
        
        .header p {{
            color: #718096;
            font-size: 1.2rem;
            margin-bottom: 20px;
        }}
        
        .stats-bar {{
            display: flex;
            justify-content: center;
            gap: 40px;
            flex-wrap: wrap;
        }}
        
        .stat {{
            text-align: center;
        }}
        
        .stat-number {{
            font-size: 2.5rem;
            font-weight: bold;
            color: #4299e1;
        }}
        
        .stat-label {{
            color: #718096;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .controls {{
            background: white;
            padding: 25px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
            display: flex;
            align-items: center;
            gap: 20px;
            flex-wrap: wrap;
        }}
        
        .controls input, .controls select {{
            padding: 12px 16px;
            border: 2px solid #e2e8f0;
            border-radius: 8px;
            font-size: 14px;
            transition: all 0.2s;
            min-width: 200px;
        }}
        
        .controls input:focus, .controls select:focus {{
            outline: none;
            border-color: #4299e1;
            box-shadow: 0 0 0 3px rgba(66, 153, 225, 0.1);
        }}
        
        .university-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
            gap: 25px;
        }}
        
        .university-card {{
            background: white;
            border-radius: 16px;
            padding: 25px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
            transition: all 0.3s ease;
            cursor: pointer;
            border: 1px solid transparent;
        }}
        
        .university-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.15);
            border-color: #4299e1;
        }}
        
        .uni-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
        }}
        
        .uni-name {{
            font-size: 18px;
            font-weight: 700;
            color: #2d3748;
            line-height: 1.3;
        }}
        
        .trend-icon {{
            font-size: 24px;
            padding: 8px;
            border-radius: 50%;
        }}
        
        .trend-up {{ background: #c6f6d5; color: #22543d; }}
        .trend-down {{ background: #fed7d7; color: #c53030; }}
        .trend-stable {{ background: #e2e8f0; color: #4a5568; }}
        
        .time-period {{
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
        }}
        
        .period-tab {{
            flex: 1;
            padding: 8px 12px;
            text-align: center;
            background: #f7fafc;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            cursor: pointer;
            transition: all 0.2s;
        }}
        
        .period-tab.active {{
            background: #4299e1;
            color: white;
        }}
        
        .device-scores {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-bottom: 15px;
        }}
        
        .device-section {{
            background: #f8fafc;
            padding: 15px;
            border-radius: 8px;
        }}
        
        .device-title {{
            font-size: 12px;
            font-weight: 600;
            color: #4a5568;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .score-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
        }}
        
        .score {{
            text-align: center;
            padding: 8px;
            border-radius: 6px;
            font-size: 12px;
        }}
        
        .score-label {{
            font-weight: 500;
            opacity: 0.7;
            margin-bottom: 2px;
        }}
        
        .score-value {{
            font-size: 16px;
            font-weight: bold;
        }}
        
        .score-good {{ background: #c6f6d5; color: #22543d; }}
        .score-average {{ background: #fefcbf; color: #744210; }}
        .score-poor {{ background: #fed7d7; color: #c53030; }}
        .score-none {{ background: #e2e8f0; color: #4a5568; }}
        
        .uni-footer {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
            color: #718096;
            padding-top: 15px;
            border-top: 1px solid #e2e8f0;
        }}
        
        .last-updated {{
            font-style: italic;
        }}
        
        .total-tests {{
            font-weight: 600;
        }}
        
        .no-data {{
            text-align: center;
            color: #a0aec0;
            padding: 40px;
            font-style: italic;
        }}
        
        @media (max-width: 768px) {{
            .header h1 {{ font-size: 2rem; }}
            .stats-bar {{ gap: 20px; }}
            .university-grid {{ grid-template-columns: 1fr; }}
            .controls {{ flex-direction: column; align-items: stretch; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎓 University Website Performance</h1>
            <p>Lighthouse performance monitoring for UK universities</p>
            <div class="stats-bar">
                <div class="stat">
                    <div class="stat-number">{len(universities)}</div>
                    <div class="stat-label">Universities</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{sum(u.get('total_tests', 0) for u in universities):,}</div>
                    <div class="stat-label">Total Tests</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{len([u for u in universities if u.get('week_averages')])}</div>
                    <div class="stat-label">Active This Week</div>
                </div>
            </div>
        </div>
        
        <div class="controls">
            <input type="text" id="searchInput" placeholder="🔍 Search universities..." />
            <select id="sortSelect">
                <option value="name">Sort by Name</option>
                <option value="performance">Sort by Performance</option>
                <option value="accessibility">Sort by Accessibility</option>
                <option value="last_updated">Sort by Last Updated</option>
            </select>
        </div>
        
        <div class="university-grid" id="universityGrid">
            {self.render_university_cards(universities)}
        </div>
    </div>
    
    <script>
        const universities = {json.dumps(universities, indent=2)};
        let currentPeriod = 'week';
        
        function getScoreClass(score) {{
            if (!score || score === 0) return 'score-none';
            if (score >= 90) return 'score-good';
            if (score >= 50) return 'score-average';
            return 'score-poor';
        }}
        
        function getTrendIcon(trend) {{
            switch(trend) {{
                case 'up': return '📈';
                case 'down': return '📉';
                default: return '➡️';
            }}
        }}
        
        function formatDate(dateString) {{
            return new Date(dateString).toLocaleDateString('en-GB', {{
                day: '2-digit',
                month: 'short',
                year: '2-digit'
            }});
        }}
        
        function renderUniversityCard(uni) {{
            const period = currentPeriod === 'week' ? 'week_averages' : 'month_averages';
            const averages = uni[period];
            
            if (!averages) {{
                return `
                    <div class="university-card" onclick="openDetail('${{uni.slug}}')">
                        <div class="uni-header">
                            <div class="uni-name">${{uni.name}}</div>
                        </div>
                        <div class="no-data">No recent data available</div>
                    </div>
                `;
            }}
            
            return `
                <div class="university-card" onclick="openDetail('${{uni.slug}}')">
                    <div class="uni-header">
                        <div class="uni-name">${{uni.name}}</div>
                        <div class="trend-icon trend-${{uni.trend}}">
                            ${{getTrendIcon(uni.trend)}}
                        </div>
                    </div>
                    
                    <div class="time-period">
                        <div class="period-tab ${{currentPeriod === 'week' ? 'active' : ''}}" onclick="event.stopPropagation(); switchPeriod('week')">
                            7 Days
                        </div>
                        <div class="period-tab ${{currentPeriod === 'month' ? 'active' : ''}}" onclick="event.stopPropagation(); switchPeriod('month')">
                            30 Days
                        </div>
                    </div>
                    
                    <div class="device-scores">
                        <div class="device-section">
                            <div class="device-title">📱 Mobile</div>
                            <div class="score-grid">
                                <div class="score ${{getScoreClass(averages.mobile?.performance || 0)}}">
                                    <div class="score-label">Perf</div>
                                    <div class="score-value">${{Math.round(averages.mobile?.performance || 0)}}</div>
                                </div>
                                <div class="score ${{getScoreClass(averages.mobile?.accessibility || 0)}}">
                                    <div class="score-label">A11y</div>
                                    <div class="score-value">${{Math.round(averages.mobile?.accessibility || 0)}}</div>
                                </div>
                                <div class="score ${{getScoreClass(averages.mobile?.best_practices || 0)}}">
                                    <div class="score-label">Best</div>
                                    <div class="score-value">${{Math.round(averages.mobile?.best_practices || 0)}}</div>
                                </div>
                                <div class="score ${{getScoreClass(averages.mobile?.seo || 0)}}">
                                    <div class="score-label">SEO</div>
                                    <div class="score-value">${{Math.round(averages.mobile?.seo || 0)}}</div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="device-section">
                            <div class="device-title">💻 Desktop</div>
                            <div class="score-grid">
                                <div class="score ${{getScoreClass(averages.desktop?.performance || 0)}}">
                                    <div class="score-label">Perf</div>
                                    <div class="score-value">${{Math.round(averages.desktop?.performance || 0)}}</div>
                                </div>
                                <div class="score ${{getScoreClass(averages.desktop?.accessibility || 0)}}">
                                    <div class="score-label">A11y</div>
                                    <div class="score-value">${{Math.round(averages.desktop?.accessibility || 0)}}</div>
                                </div>
                                <div class="score ${{getScoreClass(averages.desktop?.best_practices || 0)}}">
                                    <div class="score-label">Best</div>
                                    <div class="score-value">${{Math.round(averages.desktop?.best_practices || 0)}}</div>
                                </div>
                                <div class="score ${{getScoreClass(averages.desktop?.seo || 0)}}">
                                    <div class="score-label">SEO</div>
                                    <div class="score-value">${{Math.round(averages.desktop?.seo || 0)}}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="uni-footer">
                        <div class="last-updated">
                            Last: ${{formatDate(uni.last_updated)}}
                        </div>
                        <div class="total-tests">
                            ${{uni.total_tests}} tests
                        </div>
                    </div>
                </div>
            `;
        }}
        
        function renderGrid(unis) {{
            const grid = document.getElementById('universityGrid');
            grid.innerHTML = unis.map(renderUniversityCard).join('');
        }}
        
        function switchPeriod(period) {{
            currentPeriod = period;
            renderGrid(getFilteredUniversities());
        }}
        
        function getFilteredUniversities() {{
            let filtered = [...universities];
            
            // Search filter
            const search = document.getElementById('searchInput').value.toLowerCase();
            if (search) {{
                filtered = filtered.filter(uni => 
                    uni.name.toLowerCase().includes(search) ||
                    uni.url.toLowerCase().includes(search)
                );
            }}
            
            // Sort
            const sort = document.getElementById('sortSelect').value;
            filtered.sort((a, b) => {{
                switch(sort) {{
                    case 'name':
                        return a.name.localeCompare(b.name);
                    case 'performance':
                        const aPref = a[currentPeriod === 'week' ? 'week_averages' : 'month_averages'];
                        const bPerf = b[currentPeriod === 'week' ? 'week_averages' : 'month_averages'];
                        const aScore = aPref?.desktop?.performance || 0;
                        const bScore = bPerf?.desktop?.performance || 0;
                        return bScore - aScore;
                    case 'accessibility':
                        const aAcc = a[currentPeriod === 'week' ? 'week_averages' : 'month_averages'];
                        const bAcc = b[currentPeriod === 'week' ? 'week_averages' : 'month_averages'];
                        const aAccScore = aAcc?.desktop?.accessibility || 0;
                        const bAccScore = bAcc?.desktop?.accessibility || 0;
                        return bAccScore - aAccScore;
                    case 'last_updated':
                        return new Date(b.last_updated) - new Date(a.last_updated);
                    default:
                        return 0;
                }}
            }});
            
            return filtered;
        }}
        
        function openDetail(slug) {{
            window.location.href = `${{slug}}.html`;
        }}
        
        // Event listeners
        document.getElementById('searchInput').addEventListener('input', () => {{
            renderGrid(getFilteredUniversities());
        }});
        
        document.getElementById('sortSelect').addEventListener('change', () => {{
            renderGrid(getFilteredUniversities());
        }});
        
        // Initial render
        renderGrid(getFilteredUniversities());
    </script>
</body>
</html>'''
        
        index_file = self.docs_dir / "index.html"
        with open(index_file, 'w') as f:
            f.write(html_content)
        
        logger.info(f"Created main dashboard with {len(universities)} universities")
    
    def render_university_cards(self, universities: List[Dict[str, Any]]) -> str:
        """Generate initial HTML for university cards (server-side)"""
        if not universities:
            return '<div class="no-data">No universities found</div>'
        
        # Just return placeholder - JavaScript will handle the actual rendering
        return '<div class="no-data">Loading universities...</div>'
    
    def create_detail_page(self, university: Dict[str, Any]):
        """Create a detail page for a specific university"""
        
        # Chart.js CDN for charts
        chart_js_cdn = "https://cdn.jsdelivr.net/npm/chart.js"
        
        html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{university['name']} - Performance Dashboard</title>
    <script src="{chart_js_cdn}"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #2d3748;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .header {{
            background: white;
            padding: 30px;
            border-radius: 16px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        
        .back-button {{
            background: #4299e1;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            transition: all 0.2s;
        }}
        
        .back-button:hover {{
            background: #3182ce;
            transform: translateY(-1px);
        }}
        
        .header-info h1 {{
            font-size: 2.5rem;
            color: #2d3748;
            margin-bottom: 8px;
        }}
        
        .header-info p {{
            color: #718096;
            font-size: 1.1rem;
        }}
        
        .controls {{
            background: white;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
            display: flex;
            align-items: center;
            gap: 15px;
            flex-wrap: wrap;
        }}
        
        .time-range-selector {{
            display: flex;
            background: #f7fafc;
            border-radius: 8px;
            padding: 4px;
        }}
        
        .time-range-btn {{
            padding: 8px 16px;
            border: none;
            background: transparent;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s;
        }}
        
        .time-range-btn.active {{
            background: #4299e1;
            color: white;
        }}
        
        .device-selector {{
            display: flex;
            gap: 10px;
        }}
        
        .device-btn {{
            padding: 8px 16px;
            border: 2px solid #e2e8f0;
            background: white;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s;
        }}
        
        .device-btn.active {{
            border-color: #4299e1;
            background: #e6fffa;
            color: #2d3748;
        }}
        
        .chart-container {{
            background: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
        }}
        
        .chart-header {{
            text-align: center;
            margin-bottom: 20px;
        }}
        
        .chart-title {{
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 5px;
        }}
        
        .chart-subtitle {{
            color: #718096;
        }}
        
        .data-table {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
            overflow: hidden;
        }}
        
        .table-header {{
            background: #f8fafc;
            padding: 20px 30px;
            border-bottom: 1px solid #e2e8f0;
        }}
        
        .table-title {{
            font-size: 1.2rem;
            font-weight: 700;
            margin-bottom: 5px;
        }}
        
        .table-subtitle {{
            color: #718096;
            font-size: 14px;
        }}
        
        .table-container {{
            overflow-x: auto;
            max-height: 600px;
            overflow-y: auto;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        th, td {{
            text-align: left;
            padding: 12px 20px;
            border-bottom: 1px solid #e2e8f0;
        }}
        
        th {{
            background: #f8fafc;
            font-weight: 600;
            color: #4a5568;
            position: sticky;
            top: 0;
            z-index: 1;
        }}
        
        .score-cell {{
            font-weight: 600;
            border-radius: 4px;
            padding: 4px 8px;
            text-align: center;
            display: inline-block;
            min-width: 40px;
        }}
        
        .score-good {{ background: #c6f6d5; color: #22543d; }}
        .score-average {{ background: #fefcbf; color: #744210; }}
        .score-poor {{ background: #fed7d7; color: #c53030; }}
        
        .device-badge {{
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }}
        
        .mobile {{ background: #bee3f8; color: #2b6cb0; }}
        .desktop {{ background: #e9d8fd; color: #6b46c1; }}
        
        @media (max-width: 768px) {{
            .header {{ flex-direction: column; gap: 20px; text-align: center; }}
            .controls {{ flex-direction: column; align-items: stretch; }}
            .chart-container {{ padding: 20px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-info">
                <h1>{university['name']}</h1>
                <p>{university['url']}</p>
            </div>
            <a href="index.html" class="back-button">
                ← Back to Dashboard
            </a>
        </div>
        
        <div class="controls">
            <div class="time-range-selector">
                <button class="time-range-btn active" data-range="week">Last Week</button>
                <button class="time-range-btn" data-range="month">Last Month</button>
                <button class="time-range-btn" data-range="year">Last Year</button>
                <button class="time-range-btn" data-range="all">All Time</button>
            </div>
            
            <div class="device-selector">
                <button class="device-btn active" data-device="both">Both Devices</button>
                <button class="device-btn" data-device="mobile">Mobile Only</button>
                <button class="device-btn" data-device="desktop">Desktop Only</button>
            </div>
        </div>
        
        <div class="chart-container">
            <div class="chart-header">
                <h2 class="chart-title">Performance Trends</h2>
                <p class="chart-subtitle">Lighthouse scores over time</p>
            </div>
            <canvas id="performanceChart" width="400" height="200"></canvas>
        </div>
        
        <div class="data-table">
            <div class="table-header">
                <h2 class="table-title">Historical Test Results</h2>
                <p class="table-subtitle">All Lighthouse test results for this university</p>
            </div>
            <div class="table-container">
                <table id="resultsTable">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Device</th>
                            <th>Performance</th>
                            <th>FCP</th>
                            <th>LCP</th>
                            <th>CLS</th>
                            <th>Speed Index</th>
                            <th>Accessibility</th>
                            <th>Best Practice</th>
                            <th>SEO</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
    </div>
    
    <script>
        const universityData = {json.dumps(university, indent=2)};
        let currentRange = 'week';
        let currentDevice = 'both';
        let chart;
        
        function getScoreClass(score) {{
            if (score >= 90) return 'score-good';
            if (score >= 50) return 'score-average';
            return 'score-poor';
        }}
        
        function formatMetric(value, unit = 'ms') {{
            if (!value) return '-';
            if (value < 1000) return `${{Math.round(value)}}${{unit}}`;
            return `${{(value / 1000).toFixed(1)}}s`;
        }}
        
        function filterData(data, range, device) {{
            let filtered = [...data];
            
            // Time range filter
            if (range !== 'all') {{
                const now = new Date();
                const cutoff = new Date();
                switch(range) {{
                    case 'week': cutoff.setDate(now.getDate() - 7); break;
                    case 'month': cutoff.setDate(now.getDate() - 30); break;
                    case 'year': cutoff.setFullYear(now.getFullYear() - 1); break;
                }}
                filtered = filtered.filter(result => 
                    new Date(result.timestamp) >= cutoff
                );
            }}
            
            // Device filter
            if (device !== 'both') {{
                filtered = filtered.filter(result => result.device === device);
            }}
            
            return filtered.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
        }}
        
        function createChart(data) {{
            const ctx = document.getElementById('performanceChart').getContext('2d');
            
            if (chart) {{
                chart.destroy();
            }}
            
            const mobileData = data.filter(r => r.device === 'mobile');
            const desktopData = data.filter(r => r.device === 'desktop');
            
            const datasets = [];
            
            if (currentDevice === 'both' || currentDevice === 'mobile') {{
                datasets.push({{
                    label: 'Mobile Performance',
                    data: mobileData.map(r => ({{
                        x: r.timestamp,
                        y: r.scores.performance
                    }})),
                    borderColor: '#3182ce',
                    backgroundColor: 'rgba(49, 130, 206, 0.1)',
                    tension: 0.4
                }});
            }}
            
            if (currentDevice === 'both' || currentDevice === 'desktop') {{
                datasets.push({{
                    label: 'Desktop Performance',
                    data: desktopData.map(r => ({{
                        x: r.timestamp,
                        y: r.scores.performance
                    }})),
                    borderColor: '#805ad5',
                    backgroundColor: 'rgba(128, 90, 213, 0.1)',
                    tension: 0.4
                }});
            }}
            
            chart = new Chart(ctx, {{
                type: 'line',
                data: {{ datasets }},
                options: {{
                    responsive: true,
                    plugins: {{
                        legend: {{
                            position: 'top',
                        }}
                    }},
                    scales: {{
                        x: {{
                            type: 'time',
                            time: {{
                                unit: 'day'
                            }}
                        }},
                        y: {{
                            beginAtZero: true,
                            max: 100,
                            title: {{
                                display: true,
                                text: 'Score'
                            }}
                        }}
                    }}
                }}
            }});
        }}
        
        function updateTable(data) {{
            const tbody = document.querySelector('#resultsTable tbody');
            tbody.innerHTML = '';
            
            data.slice().reverse().forEach(result => {{
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${{new Date(result.timestamp).toLocaleDateString('en-GB')}}</td>
                    <td><span class="device-badge ${{result.device}}">${{result.device}}</span></td>
                    <td><span class="score-cell ${{getScoreClass(result.scores.performance)}}">${{Math.round(result.scores.performance)}}</span></td>
                    <td>${{formatMetric(result.metrics.first_contentful_paint)}}</td>
                    <td>${{formatMetric(result.metrics.largest_contentful_paint)}}</td>
                    <td>${{result.metrics.cumulative_layout_shift.toFixed(3)}}</td>
                    <td>${{formatMetric(result.metrics.speed_index)}}</td>
                    <td><span class="score-cell ${{getScoreClass(result.scores.accessibility)}}">${{Math.round(result.scores.accessibility)}}</span></td>
                    <td><span class="score-cell ${{getScoreClass(result.scores.best_practices)}}">${{Math.round(result.scores.best_practices)}}</span></td>
                    <td><span class="score-cell ${{getScoreClass(result.scores.seo)}}">${{Math.round(result.scores.seo)}}</span></td>
                `;
                tbody.appendChild(row);
            }});
        }}
        
        function updateView() {{
            const filteredData = filterData(universityData.results, currentRange, currentDevice);
            createChart(filteredData);
            updateTable(filteredData);
        }}
        
        // Event listeners
        document.querySelectorAll('.time-range-btn').forEach(btn => {{
            btn.addEventListener('click', (e) => {{
                document.querySelectorAll('.time-range-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                currentRange = e.target.dataset.range;
                updateView();
            }});
        }});
        
        document.querySelectorAll('.device-btn').forEach(btn => {{
            btn.addEventListener('click', (e) => {{
                document.querySelectorAll('.device-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                currentDevice = e.target.dataset.device;
                updateView();
            }});
        }});
        
        // Initial load
        updateView();
    </script>
</body>
</html>'''
        
        detail_file = self.docs_dir / f"{university['slug']}.html"
        with open(detail_file, 'w') as f:
            f.write(html_content)
        
        logger.info(f"Created detail page for {university['name']}")
    
    def create_dashboard(self):
        """Main method to create the complete dashboard"""
        logger.info("Creating new university dashboard...")
        
        # Load university data
        universities = self.load_university_data()
        
        if not universities:
            logger.warning("No university data found")
            return
        
        # Create main dashboard
        self.create_main_dashboard(universities)
        
        # Create detail pages for each university
        for university in universities:
            self.create_detail_page(university)
        
        logger.info(f"Dashboard complete with {len(universities)} universities")


def main():
    dashboard = UniversityDashboard()
    dashboard.create_dashboard()


if __name__ == "__main__":
    main()
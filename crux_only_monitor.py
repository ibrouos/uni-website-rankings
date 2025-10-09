#!/usr/bin/env python3
"""
CrUX-Only Performance Monitor
Fast collection of real user field data from Chrome UX Report API
"""

import json
import os
from datetime import datetime, date
from pathlib import Path
import logging
import requests
import time
from typing import Dict, List, Any
from collections import defaultdict
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crux_monitor.log'),
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


class CrUXMonitor:
    def __init__(self, sites: List[Dict[str, str]], api_key: str):
        self.sites = sites
        self.api_key = api_key
        self.results_dir = Path("results")
        self.results_dir.mkdir(exist_ok=True)
        self.today = date.today().isoformat()
        
    def fetch_crux_data(self, url: str, form_factor: str = "PHONE") -> Dict[str, Any]:
        """Fetch CrUX data for a URL and form factor"""
        endpoint = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"
        
        params = {
            "key": self.api_key
        }
        
        payload = {
            "url": url,
            "formFactor": form_factor  # PHONE, DESKTOP, or TABLET
        }
        
        try:
            response = requests.post(endpoint, params=params, json=payload, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.warning(f"No CrUX data available for {url} ({form_factor})")
                return None
            else:
                logger.error(f"CrUX API error for {url}: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching CrUX data for {url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching CrUX data for {url}: {str(e)}")
            return None
    
    def parse_crux_metrics(self, crux_data: Dict, name: str, url: str, device: str) -> Dict[str, Any]:
        """Parse CrUX response into standardized format"""
        if not crux_data or 'record' not in crux_data:
            return None
            
        record = crux_data['record']
        metrics = record.get('metrics', {})
        
        # Helper to get p75 value
        def get_p75(metric_name):
            metric = metrics.get(metric_name, {})
            percentiles = metric.get('percentiles', {})
            return percentiles.get('p75', 0)
        
        # Helper to convert to score (0-100)
        def get_score(metric_name):
            metric = metrics.get(metric_name, {})
            histogram = metric.get('histogram', [])
            
            # Calculate percentage in "good" range
            good_percentage = 0
            for bin in histogram:
                if bin.get('start') == 0:  # Usually "good" range starts at 0
                    good_percentage = bin.get('density', 0)
                    break
            
            return round(good_percentage * 100)
        
        return {
            'name': name,
            'url': url,
            'device': device,
            'timestamp': datetime.now().isoformat(),
            'test_type': 'field',  # Real user field data
            'data_source': 'Chrome UX Report',
            'collection_period': record.get('collectionPeriod', {}),
            'scores': {
                'lcp_score': get_score('largest_contentful_paint'),
                'fid_score': get_score('first_input_delay'),
                'cls_score': get_score('cumulative_layout_shift'),
                'fcp_score': get_score('first_contentful_paint'),
                'inp_score': get_score('interaction_to_next_paint'),
                'ttfb_score': get_score('experimental_time_to_first_byte')
            },
            'metrics': {
                'largest_contentful_paint': get_p75('largest_contentful_paint'),
                'first_input_delay': get_p75('first_input_delay'),
                'cumulative_layout_shift': get_p75('cumulative_layout_shift'),
                'first_contentful_paint': get_p75('first_contentful_paint'),
                'interaction_to_next_paint': get_p75('interaction_to_next_paint'),
                'time_to_first_byte': get_p75('experimental_time_to_first_byte')
            }
        }
    
    def run_all_tests(self) -> List[Dict[str, Any]]:
        """Fetch CrUX data for all sites"""
        all_results = []
        total = len(self.sites) * 2  # mobile + desktop
        completed = 0
        failed = 0
        start_time = datetime.now()
        
        logger.info(f"Fetching CrUX field data for {len(self.sites)} sites ({total} total requests)")
        
        for site in self.sites:
            name = site['name']
            url = site['url']
            
            # Fetch mobile data
            completed += 1
            logger.info(f"[{completed}/{total}] Fetching {name} (mobile)...")
            crux_mobile = self.fetch_crux_data(url, "PHONE")
            
            if crux_mobile:
                parsed = self.parse_crux_metrics(crux_mobile, name, url, "mobile")
                if parsed:
                    all_results.append(parsed)
                    logger.info(f"✅ [{completed}/{total}] {name} (mobile)")
                else:
                    failed += 1
                    logger.warning(f"❌ [{completed}/{total}] {name} (mobile) - parsing failed")
            else:
                failed += 1
                logger.warning(f"❌ [{completed}/{total}] {name} (mobile) - no data")
            
            time.sleep(0.5)  # Rate limiting
            
            # Fetch desktop data
            completed += 1
            logger.info(f"[{completed}/{total}] Fetching {name} (desktop)...")
            crux_desktop = self.fetch_crux_data(url, "DESKTOP")
            
            if crux_desktop:
                parsed = self.parse_crux_metrics(crux_desktop, name, url, "desktop")
                if parsed:
                    all_results.append(parsed)
                    logger.info(f"✅ [{completed}/{total}] {name} (desktop)")
                else:
                    failed += 1
                    logger.warning(f"❌ [{completed}/{total}] {name} (desktop) - parsing failed")
            else:
                failed += 1
                logger.warning(f"❌ [{completed}/{total}] {name} (desktop) - no data")
            
            time.sleep(0.5)  # Rate limiting
        
        total_time = (datetime.now() - start_time).total_seconds() / 60
        logger.info(f"\n{'='*60}")
        logger.info(f"Completed all requests in {total_time:.1f} minutes")
        logger.info(f"✅ Successful: {len(all_results)} | ❌ Failed: {failed} | Total: {total}")
        logger.info(f"{'='*60}\n")
        
        return all_results
    
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
    # Get API key from environment variable
    api_key = os.environ.get('CRUX_API_KEY')
    if not api_key:
        logger.error("CRUX_API_KEY environment variable not set!")
        logger.error("Get your key from: https://developers.google.com/web/tools/chrome-user-experience-report/api/reference")
        return
    
    # Load sites from JSON file
    try:
        sites_to_test = load_sites_from_json()
    except Exception as e:
        logger.error(f"Failed to load sites configuration: {str(e)}")
        return
    
    # Initialize monitor
    monitor = CrUXMonitor(sites_to_test, api_key)
    
    # Run tests
    logger.info("Starting CrUX field data collection...")
    results = monitor.run_all_tests()
    
    if results:
        # Save results
        monitor.save_per_university_results(results)
        logger.info("All tasks completed successfully!")
    else:
        logger.error("No results to save")


if __name__ == "__main__":
    main()

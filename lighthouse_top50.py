#!/usr/bin/env python3
"""
Optimized Lighthouse Monitor for Top 50 Universities
- Single run per site/device (not 2)
- Faster timeout settings
- Better error handling
- 16 concurrent workers for speed
"""

import json
import subprocess
import os
from datetime import datetime, date
from pathlib import Path
import logging
from typing import Dict, List, Any
import tempfile
import concurrent.futures
import re
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('lighthouse_top50.log'),
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
    def __init__(self, sites: List[Dict[str, str]], max_workers: int = 16, max_retries: int = 2):
        self.sites = sites
        self.output_dir = Path("lighthouse_results")
        self.output_dir.mkdir(exist_ok=True)
        self.results_dir = Path("results")
        self.results_dir.mkdir(exist_ok=True)
        self.today = date.today().isoformat()
        self.max_workers = max_workers
        self.max_retries = max_retries  # Retry failed tests
        self.known_slow_sites = [
            'soas.ac.uk', 'bangor.ac.uk', 'leedsbeckett.ac.uk',
            'uea.ac.uk', 'gcu.ac.uk', 'uws.ac.uk'
        ]
        
    def is_slow_site(self, url: str) -> bool:
        """Check if this is a known slow site"""
        return any(slow in url for slow in self.known_slow_sites)
    
    def run_lighthouse_test(self, site: Dict[str, str], device: str, retry_count: int = 0) -> Dict[str, Any]:
        """Run Lighthouse test for a single site and device type"""
        url = site['url']
        name = site['name']
        
        retry_suffix = f" (retry {retry_count})" if retry_count > 0 else ""
        logger.info(f"Testing {name} ({url}) on {device}{retry_suffix}")
        
        # Adjust timeout for known slow sites - increased for reliability
        timeout = 240 if self.is_slow_site(url) else 180
        max_wait = 90000 if self.is_slow_site(url) else 60000
        
        # Optimized Lighthouse CLI command
        cmd = [
            "lighthouse",
            url,
            "--output=json",
            "--quiet",
            "--chrome-flags=--headless --no-sandbox --disable-dev-shm-usage",
            "--only-categories=performance,accessibility,best-practices,seo",
            "--throttling-method=simulate",
            f"--max-wait-for-load={max_wait}",
            "--disable-storage-reset",  # Faster
        ]
        
        # Device-specific settings
        if device == "mobile":
            cmd.extend([
                "--emulated-form-factor=mobile",
                "--throttling.rttMs=150",
                "--throttling.throughputKbps=1638.4",
                "--throttling.cpuSlowdownMultiplier=4"
            ])
        else:
            cmd.extend([
                "--emulated-form-factor=desktop",
                "--throttling.rttMs=40",
                "--throttling.throughputKbps=10240",
                "--throttling.cpuSlowdownMultiplier=1"
            ])
        
        try:
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as tmp_file:
                result = subprocess.run(
                    cmd + [f"--output-path={tmp_file.name}"],
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                
                if result.returncode != 0:
                    logger.error(f"Lighthouse failed for {name} ({url}) on {device}: {result.stderr[:200]}")
                    return None
                
                # Read results
                with open(tmp_file.name, 'r') as f:
                    lighthouse_data = json.load(f)
                
                # Extract metrics
                categories = lighthouse_data.get('categories', {})
                audits = lighthouse_data.get('audits', {})
                
                metrics = {
                    'name': name,
                    'url': url,
                    'device': device,
                    'timestamp': datetime.now().isoformat(),
                    'lighthouse_version': lighthouse_data.get('lighthouseVersion', 'unknown'),
                    'test_type': 'lab',
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
                
                os.unlink(tmp_file.name)
                return metrics
                
        except subprocess.TimeoutExpired:
            logger.error(f"Lighthouse test timed out for {name} ({url}) on {device}")
            return None
        except Exception as e:
            logger.error(f"Error running Lighthouse for {name} ({url}) on {device}: {str(e)}")
            return None
    
    def run_all_tests(self) -> List[Dict[str, Any]]:
        """Run Lighthouse tests for all sites with retry logic"""
        test_tasks = []
        for site in self.sites:
            for device in ['mobile', 'desktop']:
                test_tasks.append((site, device))
        
        total_tests = len(test_tasks)
        logger.info(f"Running {total_tests} tests ({len(self.sites)} sites × 2 devices) with {self.max_workers} workers")
        logger.info(f"Max retries: {self.max_retries}")
        logger.info(f"Estimated time: {(total_tests * 60) / self.max_workers / 60:.1f} minutes")
        
        all_results = []
        failed_tasks = []  # Track failures for retry
        completed = 0
        start_time = datetime.now()
        
        # First pass
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(self.run_lighthouse_test, site, device, 0): (site, device)
                for site, device in test_tasks
            }
            
            for future in concurrent.futures.as_completed(future_to_task):
                site, device = future_to_task[future]
                completed += 1
                
                # Progress stats
                elapsed = (datetime.now() - start_time).total_seconds()
                avg_time = elapsed / completed if completed > 0 else 60
                remaining = total_tests - completed
                eta_minutes = (avg_time * remaining) / 60
                
                try:
                    result = future.result()
                    if result:
                        all_results.append(result)
                        logger.info(f"✅ [{completed}/{total_tests}] {site['name']} ({device}) - ETA: {eta_minutes:.1f}m")
                    else:
                        failed_tasks.append((site, device))
                        logger.warning(f"❌ [{completed}/{total_tests}] {site['name']} ({device}) FAILED - will retry")
                except Exception as e:
                    failed_tasks.append((site, device))
                    logger.error(f"❌ [{completed}/{total_tests}] {site['name']} ({device}): {str(e)} - will retry")
        
        # Retry failed tests
        if failed_tasks and self.max_retries > 0:
            logger.info(f"\n🔄 Retrying {len(failed_tasks)} failed tests...\n")
            
            for retry_num in range(1, self.max_retries + 1):
                if not failed_tasks:
                    break
                    
                logger.info(f"Retry attempt {retry_num}/{self.max_retries} for {len(failed_tasks)} tests")
                retry_results = []
                next_retry = []
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    future_to_task = {
                        executor.submit(self.run_lighthouse_test, site, device, retry_num): (site, device)
                        for site, device in failed_tasks
                    }
                    
                    for future in concurrent.futures.as_completed(future_to_task):
                        site, device = future_to_task[future]
                        
                        try:
                            result = future.result()
                            if result:
                                retry_results.append(result)
                                logger.info(f"✅ Retry success: {site['name']} ({device})")
                            else:
                                next_retry.append((site, device))
                                logger.warning(f"❌ Retry failed: {site['name']} ({device})")
                        except Exception as e:
                            next_retry.append((site, device))
                            logger.error(f"❌ Retry error: {site['name']} ({device}): {str(e)}")
                
                all_results.extend(retry_results)
                failed_tasks = next_retry
                
                if failed_tasks and retry_num < self.max_retries:
                    logger.info(f"Waiting 5 seconds before next retry...")
                    import time
                    time.sleep(5)
        
        # Final stats
        total_time = (datetime.now() - start_time).total_seconds() / 60
        final_failed = len(failed_tasks)
        success_rate = (len(all_results) / total_tests * 100) if total_tests > 0 else 0
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Completed in {total_time:.1f} minutes")
        logger.info(f"✅ Successful: {len(all_results)} ({success_rate:.1f}%)")
        logger.info(f"❌ Failed: {final_failed}")
        logger.info(f"Total: {total_tests}")
        
        if failed_tasks:
            logger.warning(f"\nPermanently failed tests:")
            for site, device in failed_tasks:
                logger.warning(f"  - {site['name']} ({device})")
        
        logger.info(f"{'='*60}\n")
        
        return all_results
    
    def save_results(self, results: List[Dict[str, Any]]):
        """Save results to JSON files"""
        # Daily results file
        results_file = self.output_dir / f"lighthouse_results_{self.today}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {results_file}")
        
        # Latest results
        latest_file = self.output_dir / "lighthouse_results_latest.json"
        with open(latest_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Per-university format
        self.save_per_university_results(results)
    
    def save_per_university_results(self, new_results: List[Dict[str, Any]]):
        """Save results to per-university files"""
        university_results = defaultdict(list)
        for result in new_results:
            uni_name = result.get('name')
            if uni_name:
                university_results[uni_name].append(result)
        
        for uni_name, results in university_results.items():
            slug = slugify(uni_name)
            uni_file = self.results_dir / f"{slug}.json"
            
            # Load existing
            existing_data = {'results': []}
            if uni_file.exists():
                try:
                    with open(uni_file, 'r') as f:
                        existing_data = json.load(f)
                except Exception as e:
                    logger.warning(f"Could not load existing data for {uni_name}: {e}")
            
            # Append and sort
            all_results = existing_data.get('results', []) + results
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
            
            with open(uni_file, 'w') as f:
                json.dump(uni_data, f, indent=2)
            
            logger.info(f"Updated {slug}.json ({len(results)} new, {len(all_results)} total)")
        
        self.update_index_file()
    
    def update_index_file(self):
        """Update index file"""
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


def load_sites_from_json(filename: str = "universities_top50.json") -> List[Dict[str, str]]:
    """Load sites from JSON"""
    try:
        with open(filename, 'r') as f:
            sites = json.load(f)
        
        for site in sites:
            if 'name' not in site or 'url' not in site:
                raise ValueError(f"Invalid site: {site}")
        
        logger.info(f"Loaded {len(sites)} sites from {filename}")
        return sites
        
    except FileNotFoundError:
        logger.error(f"File {filename} not found")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {filename}: {str(e)}")
        raise


def main():
    try:
        sites_to_test = load_sites_from_json()
    except Exception as e:
        logger.error(f"Failed to load sites: {str(e)}")
        return
    
    # Initialize with fewer workers and retries for stability
    monitor = LighthouseMonitor(sites_to_test, max_workers=8, max_retries=1)
    
    logger.info("Starting Lighthouse tests with retry logic...")
    results = monitor.run_all_tests()
    
    if results:
        monitor.save_results(results)
        success_rate = (len(results) / (len(sites_to_test) * 2) * 100)
        logger.info(f"All tasks completed! Success rate: {success_rate:.1f}%")
    else:
        logger.error("No results to save")


if __name__ == "__main__":
    main()

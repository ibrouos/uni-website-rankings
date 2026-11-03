#!/usr/bin/env python3
"""
Lighthouse runner for the universities in config.json "sites_file"
- One test at a time per machine: parallel Chromes compete for CPU and inflate TBT/performance
- Sites are split into shards so several CI machines can share the work (--shard/--shards)
- Shard results are written with --output and combined into results/ with --merge
"""

import argparse
import json
import subprocess
import os
from datetime import datetime
from pathlib import Path
import logging
from typing import Dict, List, Any
import tempfile
import concurrent.futures

import results_store

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('lighthouse_runner.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class LighthouseMonitor:
    def __init__(self, sites: List[Dict[str, str]], max_workers: int = 1, max_retries: int = 2):
        self.sites = sites
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
        
        # Mobile is Lighthouse's default (Moto G Power, 150 ms RTT, 1.6 Mbps, 4x CPU slowdown).
        # Desktop needs the preset: the old --emulated-form-factor flag was removed in Lighthouse 7
        # and is silently ignored, which left "desktop" runs emulating a phone.
        if device == "desktop":
            cmd.append("--preset=desktop")
        
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
                settings = lighthouse_data.get('configSettings', {})
                
                metrics = {
                    'name': name,
                    'url': url,
                    'device': device,
                    'timestamp': datetime.now().isoformat(),
                    'lighthouse_version': lighthouse_data.get('lighthouseVersion', 'unknown'),
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
                    # Only runs from the corrected method record these; the dashboard dates the change by them
                    'form_factor': settings.get('formFactor'),
                    'throttling': {k: settings.get('throttling', {}).get(k) for k in ('rttMs', 'throughputKbps', 'cpuSlowdownMultiplier')},
                    # How fast the test machine was; lets slow-machine runs be spotted later
                    'benchmark_index': lighthouse_data.get('environment', {}).get('benchmarkIndex')
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
        """Append results to each university's file in results/"""
        for slug, count in sorted(results_store.append_results(results).items()):
            logger.info(f"Added {count} tests to {slug}.jsonl")


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


def merge_shards(shard_dir: str):
    """Combine shard outputs (written with --output) into the per-university files"""
    results = []
    for shard_file in sorted(Path(shard_dir).glob("*.json")):
        with open(shard_file, 'r') as f:
            shard_results = json.load(f)
        logger.info(f"Loaded {len(shard_results)} results from {shard_file.name}")
        results.extend(shard_results)

    if not results:
        logger.error(f"No shard results found in {shard_dir}")
        raise SystemExit(1)

    LighthouseMonitor([]).save_results(results)
    logger.info(f"Merged {len(results)} results")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--shard', type=int, default=0, help='Which shard of the site list to test (0-based)')
    parser.add_argument('--shards', type=int, default=1, help='How many shards the site list is split into')
    parser.add_argument('--workers', type=int, default=1, help='Concurrent tests; keep at 1 for stable scores')
    parser.add_argument('--output', help="Write this shard's results to a file instead of updating results/")
    parser.add_argument('--merge', metavar='DIR', help='Merge shard result files from DIR into results/')
    args = parser.parse_args()

    if args.merge:
        merge_shards(args.merge)
        return

    try:
        with open('config.json', 'r') as f:
            sites = load_sites_from_json(json.load(f).get('sites_file', 'universities_top50.json'))
    except Exception as e:
        logger.error(f"Failed to load sites: {str(e)}")
        return

    # Every Nth site, so slow and fast sites spread evenly across shards
    sites_to_test = sites[args.shard::args.shards]
    logger.info(f"Shard {args.shard + 1}/{args.shards}: {len(sites_to_test)} sites")

    monitor = LighthouseMonitor(sites_to_test, max_workers=args.workers, max_retries=1)
    
    logger.info("Starting Lighthouse tests with retry logic...")
    results = monitor.run_all_tests()
    
    if not results:
        logger.error("No results to save")
        raise SystemExit(1)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Shard results saved to {args.output}")
    else:
        monitor.save_results(results)

    success_rate = (len(results) / (len(sites_to_test) * 2) * 100)
    logger.info(f"All tasks completed! Success rate: {success_rate:.1f}%")


if __name__ == "__main__":
    main()

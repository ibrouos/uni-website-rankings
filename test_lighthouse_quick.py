#!/usr/bin/env python3
"""
Quick test script to validate Lighthouse setup with a small sample
"""
import json
import sys
from lighthouse_monitor import LighthouseMonitor, logger

def main():
    # Load just 3 universities for quick testing
    with open('universities.json', 'r') as f:
        all_sites = json.load(f)
    
    # Take first 3 sites
    test_sites = all_sites[:3]
    
    logger.info(f"Testing with {len(test_sites)} universities:")
    for site in test_sites:
        logger.info(f"  - {site['name']}")
    
    # Use moderate parallelism for testing
    monitor = LighthouseMonitor(test_sites, max_workers=6, runs_per_test=2)
    
    # Run tests
    results = monitor.run_all_tests()
    
    if results:
        monitor.save_results(results)
        logger.info("✅ Test successful! Ready to run full suite.")
    else:
        logger.error("❌ Test failed - no results collected")
        sys.exit(1)

if __name__ == "__main__":
    main()

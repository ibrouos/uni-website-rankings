#!/usr/bin/env python3
"""
Fetch Chrome UX Report (CrUX) Field Data
Fetches real user metrics from Chrome User Experience Report API
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CrUXDataFetcher:
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize CrUX data fetcher
        
        Args:
            api_key: Google API key for CrUX API. If not provided, looks for CRUX_API_KEY env var
        """
        self.api_key = api_key or os.environ.get('CRUX_API_KEY')
        self.api_url = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"
        
    def fetch_field_data(self, url: str, form_factor: str = 'PHONE') -> Optional[Dict[str, Any]]:
        """
        Fetch field data (real user metrics) from CrUX API
        
        Args:
            url: Website URL to fetch data for
            form_factor: 'PHONE', 'DESKTOP', or 'TABLET'
            
        Returns:
            Dictionary with field data or None if not available
        """
        if not self.api_key:
            logger.warning("No CrUX API key provided. Set CRUX_API_KEY environment variable.")
            return None
        
        # Prepare request
        params = {'key': self.api_key}
        payload = {
            'url': url,
            'formFactor': form_factor
        }
        
        try:
            response = requests.post(self.api_url, params=params, json=payload, timeout=30)
            
            if response.status_code == 404:
                logger.info(f"No CrUX data available for {url} ({form_factor})")
                return None
            
            if response.status_code != 200:
                logger.error(f"CrUX API error for {url}: {response.status_code} - {response.text}")
                return None
            
            data = response.json()
            return self.parse_crux_response(data, url, form_factor)
            
        except requests.exceptions.Timeout:
            logger.error(f"CrUX API timeout for {url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching CrUX data for {url}: {str(e)}")
            return None
    
    def parse_crux_response(self, data: Dict, url: str, form_factor: str) -> Dict[str, Any]:
        """Parse CrUX API response into structured format"""
        
        metrics = data.get('record', {}).get('metrics', {})
        
        # Extract Core Web Vitals
        field_data = {
            'url': url,
            'form_factor': form_factor.lower(),
            'test_type': 'field',  # Real user data
            'collection_period': data.get('record', {}).get('collectionPeriod', {}),
            'metrics': {}
        }
        
        # Largest Contentful Paint (LCP)
        if 'largest_contentful_paint' in metrics:
            lcp = metrics['largest_contentful_paint']
            field_data['metrics']['lcp'] = {
                'p75': lcp.get('percentiles', {}).get('p75'),
                'good': lcp.get('histogram', [{}])[0].get('density', 0) if lcp.get('histogram') else 0,
                'needs_improvement': lcp.get('histogram', [{}])[1].get('density', 0) if len(lcp.get('histogram', [])) > 1 else 0,
                'poor': lcp.get('histogram', [{}])[2].get('density', 0) if len(lcp.get('histogram', [])) > 2 else 0
            }
        
        # First Contentful Paint (FCP)
        if 'first_contentful_paint' in metrics:
            fcp = metrics['first_contentful_paint']
            field_data['metrics']['fcp'] = {
                'p75': fcp.get('percentiles', {}).get('p75'),
                'good': fcp.get('histogram', [{}])[0].get('density', 0) if fcp.get('histogram') else 0,
                'needs_improvement': fcp.get('histogram', [{}])[1].get('density', 0) if len(fcp.get('histogram', [])) > 1 else 0,
                'poor': fcp.get('histogram', [{}])[2].get('density', 0) if len(fcp.get('histogram', [])) > 2 else 0
            }
        
        # Cumulative Layout Shift (CLS)
        if 'cumulative_layout_shift' in metrics:
            cls = metrics['cumulative_layout_shift']
            field_data['metrics']['cls'] = {
                'p75': cls.get('percentiles', {}).get('p75'),
                'good': cls.get('histogram', [{}])[0].get('density', 0) if cls.get('histogram') else 0,
                'needs_improvement': cls.get('histogram', [{}])[1].get('density', 0) if len(cls.get('histogram', [])) > 1 else 0,
                'poor': cls.get('histogram', [{}])[2].get('density', 0) if len(cls.get('histogram', [])) > 2 else 0
            }
        
        # Interaction to Next Paint (INP)
        if 'interaction_to_next_paint' in metrics:
            inp = metrics['interaction_to_next_paint']
            field_data['metrics']['inp'] = {
                'p75': inp.get('percentiles', {}).get('p75'),
                'good': inp.get('histogram', [{}])[0].get('density', 0) if inp.get('histogram') else 0,
                'needs_improvement': inp.get('histogram', [{}])[1].get('density', 0) if len(inp.get('histogram', [])) > 1 else 0,
                'poor': inp.get('histogram', [{}])[2].get('density', 0) if len(inp.get('histogram', [])) > 2 else 0
            }
        
        # First Input Delay (FID) - deprecated but still available
        if 'first_input_delay' in metrics:
            fid = metrics['first_input_delay']
            field_data['metrics']['fid'] = {
                'p75': fid.get('percentiles', {}).get('p75'),
                'good': fid.get('histogram', [{}])[0].get('density', 0) if fid.get('histogram') else 0,
                'needs_improvement': fid.get('histogram', [{}])[1].get('density', 0) if len(fid.get('histogram', [])) > 1 else 0,
                'poor': fid.get('histogram', [{}])[2].get('density', 0) if len(fid.get('histogram', [])) > 2 else 0
            }
        
        return field_data
    
    def fetch_all_universities(self, universities_file: str = "universities.json") -> Dict[str, Any]:
        """Fetch field data for all universities"""
        
        # Load universities
        with open(universities_file, 'r') as f:
            universities = json.load(f)
        
        results = {}
        total = len(universities)
        
        for idx, uni in enumerate(universities, 1):
            name = uni['name']
            url = uni['url']
            
            logger.info(f"Fetching CrUX data for {name} ({idx}/{total})")
            
            # Fetch for both mobile and desktop
            mobile_data = self.fetch_field_data(url, 'PHONE')
            desktop_data = self.fetch_field_data(url, 'DESKTOP')
            
            results[name] = {
                'url': url,
                'mobile': mobile_data,
                'desktop': desktop_data
            }
        
        return results
    
    def save_field_data(self, output_file: str = "crux_field_data.json"):
        """Fetch and save field data for all universities"""
        
        logger.info("Starting CrUX field data collection...")
        
        results = self.fetch_all_universities()
        
        # Save results
        output_path = Path(output_file)
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"CrUX field data saved to {output_path}")
        
        # Print summary
        mobile_available = sum(1 for r in results.values() if r.get('mobile'))
        desktop_available = sum(1 for r in results.values() if r.get('desktop'))
        
        logger.info(f"Summary: {mobile_available} mobile, {desktop_available} desktop field data records")


def main():
    """Main entry point"""
    
    # Check for API key
    api_key = os.environ.get('CRUX_API_KEY')
    if not api_key:
        print("\n⚠️  No CrUX API key found!")
        print("\nTo use this script, you need a Google API key with CrUX API enabled:")
        print("1. Go to https://console.cloud.google.com/apis/credentials")
        print("2. Create an API key")
        print("3. Enable the 'Chrome UX Report API'")
        print("4. Set the environment variable: export CRUX_API_KEY='your-key-here'")
        print("\nFor now, the system will work without field data (lab data only).\n")
        return
    
    fetcher = CrUXDataFetcher(api_key)
    fetcher.save_field_data()


if __name__ == "__main__":
    main()

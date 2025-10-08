#!/usr/bin/env python3
"""
Data Reorganization Script
Reorganizes historical lighthouse data into per-university files
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def slugify(text: str) -> str:
    """Convert university name to URL-safe slug"""
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and special chars with hyphens
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')


class DataReorganizer:
    def __init__(self, old_dir: Path = Path("lighthouse_results"), 
                 new_dir: Path = Path("results")):
        self.old_dir = old_dir
        self.new_dir = new_dir
        self.new_dir.mkdir(exist_ok=True)
        
    def load_all_historical_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load all historical results and organize by university"""
        university_data = defaultdict(list)
        
        if not self.old_dir.exists():
            logger.warning(f"Data directory {self.old_dir} does not exist")
            return university_data
        
        # Load all daily result files
        result_files = sorted(self.old_dir.glob("lighthouse_results_*.json"))
        logger.info(f"Found {len(result_files)} result files to process")
        
        for result_file in result_files:
            if result_file.name == "lighthouse_results_latest.json":
                continue
                
            try:
                with open(result_file, 'r') as f:
                    daily_results = json.load(f)
                    
                    for result in daily_results:
                        uni_name = result.get('name')
                        if uni_name:
                            university_data[uni_name].append(result)
                    
                    logger.info(f"Processed {result_file.name}: {len(daily_results)} results")
            except Exception as e:
                logger.error(f"Error loading {result_file}: {str(e)}")
        
        logger.info(f"Total universities found: {len(university_data)}")
        return university_data
    
    def save_university_files(self, university_data: Dict[str, List[Dict[str, Any]]]):
        """Save each university's data to its own file"""
        for uni_name, results in university_data.items():
            slug = slugify(uni_name)
            output_file = self.new_dir / f"{slug}.json"
            
            # Sort results by timestamp
            sorted_results = sorted(results, key=lambda x: x.get('timestamp', ''))
            
            # Create university metadata
            uni_file_data = {
                'name': uni_name,
                'slug': slug,
                'url': results[0].get('url', '') if results else '',
                'last_updated': sorted_results[-1].get('timestamp', '') if sorted_results else '',
                'total_tests': len(sorted_results),
                'results': sorted_results
            }
            
            with open(output_file, 'w') as f:
                json.dump(uni_file_data, f, indent=2)
            
            logger.info(f"Saved {uni_name} ({len(sorted_results)} results) to {output_file.name}")
    
    def create_index_file(self, university_data: Dict[str, List[Dict[str, Any]]]):
        """Create an index file with all universities"""
        index_data = []
        
        for uni_name in sorted(university_data.keys()):
            slug = slugify(uni_name)
            results = university_data[uni_name]
            
            if results:
                index_data.append({
                    'name': uni_name,
                    'slug': slug,
                    'url': results[0].get('url', ''),
                    'total_tests': len(results)
                })
        
        index_file = self.new_dir / "index.json"
        with open(index_file, 'w') as f:
            json.dump(index_data, f, indent=2)
        
        logger.info(f"Created index file with {len(index_data)} universities")
    
    def reorganize(self):
        """Main reorganization process"""
        logger.info("Starting data reorganization...")
        
        # Load all historical data
        university_data = self.load_all_historical_data()
        
        if not university_data:
            logger.warning("No data found to reorganize")
            return
        
        # Save per-university files
        self.save_university_files(university_data)
        
        # Create index file
        self.create_index_file(university_data)
        
        logger.info("Data reorganization complete!")


def main():
    reorganizer = DataReorganizer()
    reorganizer.reorganize()


if __name__ == "__main__":
    main()

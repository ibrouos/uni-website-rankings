"""
Results storage shared by the test runner and the dashboard builder.

results/index.json    universities: [{name, slug, url}]
results/<slug>.jsonl  one compact JSON object per test, oldest first, append-only

Appending a line per test (rather than rewriting a whole pretty-printed file every day)
keeps each day's git change to a few hundred bytes per university.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

RESULTS_DIR = Path("results")
INDEX_FILE = "index.json"

SCORE_KEYS = ('performance', 'accessibility', 'best_practices', 'seo')
METRIC_KEYS = ('first_contentful_paint', 'largest_contentful_paint', 'total_blocking_time',
               'cumulative_layout_shift', 'speed_index', 'interactive')


def slugify(text: str) -> str:
    """Convert university name to URL-safe slug"""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')


def _round(key: str, value: Any) -> Any:
    if not isinstance(value, (int, float)):
        return None
    if key == 'cumulative_layout_shift':
        return round(value, 4)
    rounded = round(value, 1) if key in SCORE_KEYS else round(value)
    return int(rounded) if rounded == int(rounded) else rounded


def compact(result: Dict[str, Any]) -> Dict[str, Any]:
    """The stored form of one test: identity lives in index.json, values are rounded"""
    record = {
        'timestamp': result['timestamp'][:19],
        'device': result.get('device'),
        'scores': {k: _round(k, (result.get('scores') or {}).get(k)) for k in SCORE_KEYS},
        'metrics': {k: _round(k, (result.get('metrics') or {}).get(k)) for k in METRIC_KEYS},
    }
    for key in ('lighthouse_version', 'form_factor', 'throttling', 'benchmark_index'):
        if result.get(key) is not None:
            record[key] = result[key]
    return record


def load_index(results_dir: Path = RESULTS_DIR) -> List[Dict[str, str]]:
    try:
        with open(results_dir / INDEX_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def save_index(entries: Iterable[Dict[str, str]], results_dir: Path = RESULTS_DIR):
    entries = sorted(({k: e[k] for k in ('name', 'slug', 'url')} for e in entries), key=lambda e: e['slug'])
    with open(results_dir / INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(entries, f, indent=1)
        f.write('\n')


def read_results(slug: str, results_dir: Path = RESULTS_DIR) -> List[Dict[str, Any]]:
    path = results_dir / f"{slug}.jsonl"
    if not path.exists():
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def append_results(results: List[Dict[str, Any]], results_dir: Path = RESULTS_DIR) -> Dict[str, int]:
    """Append raw runner results (which carry name/url) to each university's file; returns new tests per slug"""
    results_dir.mkdir(parents=True, exist_ok=True)
    index = {e['slug']: e for e in load_index(results_dir)}
    by_slug: Dict[str, List[Dict[str, Any]]] = {}
    for result in results:
        slug = slugify(result['name'])
        index.setdefault(slug, {'name': result['name'], 'slug': slug, 'url': result.get('url', '')})
        by_slug.setdefault(slug, []).append(result)

    for slug, new in by_slug.items():
        with open(results_dir / f"{slug}.jsonl", 'a', encoding='utf-8', newline='\n') as f:
            for result in sorted(new, key=lambda r: r['timestamp']):
                f.write(json.dumps(compact(result), separators=(',', ':')) + '\n')

    save_index(index.values(), results_dir)
    return {slug: len(new) for slug, new in by_slug.items()}

#!/usr/bin/env python3
"""
Real-user data from the Chrome UX Report (CrUX) History API.

For each university homepage and device, fetches up to 40 weekly collection periods (each the 75th
percentile over a rolling 28 days of real Chrome users) and merges them into results/crux/<slug>.json.
Older periods are kept, so history keeps growing beyond the API's 40 weeks.

Uses page-level data for the homepage, falling back to the whole site (origin) when the homepage has
too little traffic. Needs CRUX_API_KEY; without it this does nothing. Only the Python standard library.
"""

import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from results_store import slugify

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_URL = "https://chromeuxreport.googleapis.com/v1/records:queryHistoryRecord"
CRUX_DIR = Path("results") / "crux"
# Each stored row is [last day of the 28-day period, *p75 of METRICS]; build_dashboard_new.py reads this order
METRICS = ('largest_contentful_paint', 'interaction_to_next_paint', 'cumulative_layout_shift',
           'first_contentful_paint', 'experimental_time_to_first_byte')
FORM_FACTORS = {'mobile': 'PHONE', 'desktop': 'DESKTOP'}
PERIODS = 40               # the API maximum (about 10 months)
REQUEST_GAP_SECONDS = 0.45  # stays under the 150 queries/minute quota


class CruxError(Exception):
    pass


def query(api_key: str, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One History API call. None means CrUX has no data for this key (HTTP 404)."""
    request = urllib.request.Request(f"{API_URL}?key={api_key}", data=json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'}, method='POST')
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429 or e.code >= 500:
                time.sleep(5 * 2 ** attempt)
                continue
            # Never include the request URL in errors: it carries the API key
            raise CruxError(f"HTTP {e.code}: {e.read()[:300].decode(errors='replace')}")
        except urllib.error.URLError as e:
            logger.warning(f"Network error ({e.reason}), retrying")
            time.sleep(5 * 2 ** attempt)
    raise CruxError("No response after 4 attempts")


def number(value: Any) -> Optional[float]:
    """p75s are numbers, strings (CLS) or null; histogram gaps are "NaN\""""
    if value is None or value == 'NaN':
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_rows(record: Dict[str, Any]) -> List[list]:
    rows = []
    metrics = record.get('metrics', {})
    for i, period in enumerate(record.get('collectionPeriods', [])):
        last = period['lastDate']
        values = []
        for metric in METRICS:
            p75s = metrics.get(metric, {}).get('percentilesTimeseries', {}).get('p75s', [])
            value = number(p75s[i]) if i < len(p75s) else None
            if value is not None:
                value = round(value, 3) if metric == 'cumulative_layout_shift' else int(round(value))
            values.append(value)
        if any(v is not None for v in values):
            rows.append([f"{last['year']:04d}-{last['month']:02d}-{last['day']:02d}"] + values)
    return rows


def fetch_device(api_key: str, url: str, form_factor: str) -> Optional[Dict[str, Any]]:
    """Homepage data if CrUX has it, otherwise whole-site data, otherwise None"""
    origin = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    for scope, target in (('page', {'url': url}), ('origin', {'origin': origin})):
        time.sleep(REQUEST_GAP_SECONDS)
        data = query(api_key, {**target, 'formFactor': form_factor, 'metrics': list(METRICS),
                                'collectionPeriodCount': PERIODS})
        rows = parse_rows(data['record']) if data else []
        if rows:
            return {'scope': scope, 'rows': rows}
    return None


def merge(existing: Optional[Dict[str, Any]], fetched: Dict[str, Any]) -> Dict[str, Any]:
    """Add new periods and refresh revised ones; keep periods older than the API returns"""
    if not existing or existing.get('scope') != fetched['scope']:
        # Homepage and whole-site figures aren't comparable, so a change of scope starts afresh
        return fetched
    rows = {row[0]: row for row in existing['rows']}
    rows.update({row[0]: row for row in fetched['rows']})
    return {'scope': fetched['scope'], 'rows': [rows[day] for day in sorted(rows)]}


def dumps(data: Dict[str, Any]) -> str:
    """One period per line, so each week's update is a small git diff"""
    parts = []
    for device, entry in data.items():
        rows = ',\n'.join('    ' + json.dumps(row, separators=(',', ':')) for row in entry['rows'])
        parts.append(f'  "{device}": {{"scope": "{entry["scope"]}", "rows": [\n{rows}\n  ]}}')
    return '{\n' + ',\n'.join(parts) + '\n}\n'


def load(slug: str) -> Dict[str, Any]:
    path = CRUX_DIR / f"{slug}.json"
    if not path.exists():
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main() -> int:
    api_key = os.environ.get('CRUX_API_KEY')
    if not api_key:
        logger.warning("CRUX_API_KEY is not set; skipping CrUX")
        return 0

    with open('config.json', 'r') as f:
        sites_file = json.load(f).get('sites_file', 'universities_top50.json')
    with open(sites_file, 'r', encoding='utf-8') as f:
        sites = json.load(f)

    CRUX_DIR.mkdir(parents=True, exist_ok=True)
    counts = {'page': 0, 'origin': 0, 'none': 0, 'updated': 0}
    for n, site in enumerate(sites, 1):
        slug = slugify(site['name'])
        existing = load(slug)
        updated = dict(existing)
        for device, form_factor in FORM_FACTORS.items():
            try:
                fetched = fetch_device(api_key, site['url'], form_factor)
            except CruxError as e:
                logger.error(f"CrUX request failed for {site['name']} ({device}): {e}")
                if n == 1:
                    return 1  # the first call failing usually means a key or API problem; stop early
                continue
            if fetched:
                counts[fetched['scope']] += 1
                updated[device] = merge(existing.get(device), fetched)
            else:
                counts['none'] += 1

        if updated and updated != existing:
            with open(CRUX_DIR / f"{slug}.json", 'w', encoding='utf-8', newline='\n') as f:
                f.write(dumps({d: updated[d] for d in FORM_FACTORS if d in updated}))
            counts['updated'] += 1
        logger.info(f"[{n}/{len(sites)}] {site['name']}: "
                    + ', '.join(f"{d} {updated[d]['scope'] if d in updated else 'no data'}" for d in FORM_FACTORS))

    logger.info(f"Homepage data: {counts['page']}, whole-site data: {counts['origin']}, no data: {counts['none']} "
                f"(site/device pairs); files updated: {counts['updated']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

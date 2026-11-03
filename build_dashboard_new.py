#!/usr/bin/env python3
"""
Dashboard Builder
Builds the rankings list (docs/index.html), the compare page (docs/compare.html),
a detail page per university and per-university daily history (docs/data/<slug>.json)
"""

import html
import json
import logging
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse

import results_store
from crux import CRUX_DIR

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SCORE_KEYS = ('performance', 'accessibility', 'best_practices', 'seo')
VITAL_KEYS = ('first_contentful_paint', 'largest_contentful_paint', 'total_blocking_time', 'cumulative_layout_shift')
# Column order of every daily row: [day, *FIELDS]. Must match FIELDS in COMMON_JS.
FIELDS = SCORE_KEYS + VITAL_KEYS
DEVICES = ('mobile', 'desktop')

SPARK_DAYS = 90     # history shown in the rankings list
SMOOTH_DAYS = 7     # rankings-list lines are a trailing 7-day median, so daily noise doesn't hide the trend
CURRENT_DAYS = 7    # "current" score = median of the latest week of tests
TREND_DAYS = 30     # trend = latest 30 days vs the 30 days before
TREND_MIN_DAYS = 5  # days of data each trend window needs

CHART_JS = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"
CHART_ADAPTER = "https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"


def to_script_json(data: Any) -> str:
    """Serialise data for embedding inside a <script> tag"""
    return json.dumps(data, separators=(',', ':')).replace('</', '<\\/')


def field_value(result: Dict[str, Any], field: str) -> Optional[float]:
    source = result.get('scores', {}) if field in SCORE_KEYS else result.get('metrics', {})
    value = (source or {}).get(field)
    return value if isinstance(value, (int, float)) else None


def round_field(field: str, value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if field == 'cumulative_layout_shift':
        return round(value, 4)
    if field in SCORE_KEYS:
        return round(value, 1) if value % 1 else int(value)
    return int(round(value))


# Shared stylesheet, written to docs/styles.css
STYLES = r"""
:root {
  --bg: oklch(0.985 0.002 230); --surface: oklch(1 0 0); --surface-2: oklch(0.972 0.003 230);
  --home: oklch(0.975 0.04 95); --home-hover: oklch(0.96 0.05 95);
  --hover: oklch(0.977 0.005 205); --line: oklch(0.925 0.004 230); --line-strong: oklch(0.87 0.006 230);
  --ink: oklch(0.22 0.012 240); --ink-2: oklch(0.42 0.012 240); --ink-3: oklch(0.52 0.01 240);
  --accent: oklch(0.5 0.09 200); --accent-ink: oklch(0.43 0.08 200); --accent-soft: oklch(0.5 0.09 200 / 0.12);
  --on-accent: oklch(0.99 0 0);
  --good: #0ca30c; --avg: #c27a00; --poor: #d03b3b;
  --s1: #2a78d6; --s2: #eb6834; --s3: #1baf7a; --s4: #eda100; --s5: #e87ba4; --s6: #008300;
  --grid: oklch(0.935 0.004 230); --axis: oklch(0.85 0.006 230);
  --shadow-pop: 0 1px 2px oklch(0.2 0.02 240 / 0.06), 0 8px 24px oklch(0.2 0.02 240 / 0.1);
  --z-sticky: 10; --z-popover: 20; --z-bar: 30; --z-tip: 40;
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px; --space-5: 24px; --space-6: 32px; --space-7: 48px; --space-8: 64px;
  --t-xs: 0.75rem; --t-sm: 0.8125rem; --t-md: 0.9375rem; --t-lg: 1.125rem; --t-xl: 1.625rem;
  --ease-out: cubic-bezier(0.25, 1, 0.5, 1);
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: oklch(0.165 0.005 240); --surface: oklch(0.195 0.006 240); --surface-2: oklch(0.215 0.006 240);
    --home: oklch(0.255 0.03 95); --home-hover: oklch(0.28 0.036 95);
    --hover: oklch(0.225 0.008 215); --line: oklch(0.27 0.007 240); --line-strong: oklch(0.34 0.008 240);
    --ink: oklch(0.94 0.004 240); --ink-2: oklch(0.78 0.008 240); --ink-3: oklch(0.66 0.008 240);
    --accent: oklch(0.74 0.1 198); --accent-ink: oklch(0.8 0.09 198); --accent-soft: oklch(0.74 0.1 198 / 0.16);
    --on-accent: oklch(0.18 0.02 220);
    --good: #3cb93c; --avg: #e0a339; --poor: #ec6a5e;
    --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #c98500; --s5: #d55181; --s6: #3a9a3a;
    --grid: oklch(0.25 0.006 240); --axis: oklch(0.36 0.008 240);
    --shadow-pop: 0 1px 2px oklch(0 0 0 / 0.3), 0 8px 28px oklch(0 0 0 / 0.45);
    color-scheme: dark;
  }
}

* { box-sizing: border-box; margin: 0; padding: 0; }
[hidden] { display: none !important; }
html { -webkit-text-size-adjust: 100%; }
body {
  font-family: 'Geist', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif;
  font-size: var(--t-md); line-height: 1.5;
  background: var(--bg); color: var(--ink);
  -webkit-font-smoothing: antialiased; font-kerning: normal;
}
a { color: inherit; }
button, input, select { font: inherit; color: inherit; }
ol, ul { list-style: none; }
.num, .mono { font-family: 'Geist Mono', ui-monospace, 'SF Mono', Menlo, monospace; font-variant-numeric: tabular-nums; letter-spacing: -0.01em; }
.muted { color: var(--ink-3); }
.wrap { max-width: 1200px; margin: 0 auto; padding: 0 var(--space-5); }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 4px; }

/* Top bar */
.topbar {
  position: sticky; top: 0; z-index: var(--z-sticky);
  background: color-mix(in oklch, var(--bg) 88%, transparent);
  backdrop-filter: saturate(160%) blur(10px);
  border-bottom: 1px solid var(--line);
}
.topbar .wrap { height: 52px; display: flex; align-items: center; gap: var(--space-5); min-width: 0; }
.brand { display: flex; align-items: center; gap: 9px; font-weight: 600; font-size: var(--t-md); letter-spacing: -0.015em; white-space: nowrap; text-decoration: none; }
.brand svg { color: var(--accent); flex: none; }
.nav { display: flex; gap: var(--space-1); }
.nav a { padding: 5px 10px; border-radius: 6px; font-size: var(--t-sm); font-weight: 500; color: var(--ink-2); text-decoration: none; transition: color .15s, background-color .15s; }
.nav a:hover { color: var(--ink); background: var(--surface-2); }
.nav a[aria-current="page"] { color: var(--ink); background: var(--surface-2); }
.topbar-meta { margin-left: auto; color: var(--ink-3); font-size: var(--t-sm); white-space: nowrap; }

/* Page header */
.page-head { padding: var(--space-7) 0 var(--space-5); }
.page-head h1 { font-size: var(--t-xl); font-weight: 600; letter-spacing: -0.025em; line-height: 1.2; text-wrap: balance; }
.lede { color: var(--ink-2); margin-top: var(--space-2); max-width: 66ch; text-wrap: pretty; }
.facts { margin-top: var(--space-3); color: var(--ink-3); font-size: var(--t-sm); display: flex; flex-wrap: wrap; gap: 4px 14px; }
.facts b { color: var(--ink-2); font-weight: 500; }
.head-row { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: var(--space-4); }
.ext { color: var(--ink-2); text-decoration: none; display: inline-flex; align-items: center; gap: 4px; }
.ext:hover { color: var(--ink); text-decoration: underline; text-underline-offset: 3px; }

.notice {
  display: flex; gap: var(--space-2); align-items: flex-start;
  padding: 10px 14px; margin-bottom: var(--space-5); border-radius: 8px;
  background: color-mix(in srgb, var(--avg) 10%, var(--surface)); border: 1px solid color-mix(in srgb, var(--avg) 30%, var(--line));
  font-size: var(--t-sm); color: var(--ink);
}
.notice svg { flex: none; margin-top: 2px; color: var(--avg); }

/* Controls */
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); margin-bottom: var(--space-3); }
.toolbar .spacer { flex: 1; }
.ctl-label { font-size: var(--t-xs); color: var(--ink-3); margin-right: 2px; }
.field {
  height: 32px; font-size: var(--t-sm); background: var(--surface); border: 1px solid var(--line-strong); border-radius: 8px;
  transition: border-color .15s, box-shadow .15s;
}
.field:hover { border-color: color-mix(in oklch, var(--ink-3) 60%, var(--line-strong)); }
.field:focus, .field:focus-within { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
.search { position: relative; flex: 1 1 220px; max-width: 300px; display: flex; align-items: center; }
.search svg { position: absolute; left: 10px; color: var(--ink-3); pointer-events: none; }
.search input { width: 100%; height: 100%; padding: 0 30px 0 32px; background: transparent; border: 0; outline: none; }
.search input::placeholder { color: var(--ink-3); opacity: 1; }
.kbd { position: absolute; right: 8px; font-size: 11px; line-height: 16px; padding: 0 5px; color: var(--ink-3); border: 1px solid var(--line-strong); border-radius: 4px; }
select.field {
  padding: 0 28px 0 10px; cursor: pointer; appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 16 16' fill='none' stroke='%23808892' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 6l4 4 4-4'/%3E%3C/svg%3E");
  background-repeat: no-repeat; background-position: right 10px center;
}
.seg { display: inline-flex; padding: 2px; gap: 2px; background: var(--surface-2); border: 1px solid var(--line); border-radius: 8px; }
.seg button {
  height: 26px; padding: 0 10px; font-size: var(--t-sm); font-weight: 500; white-space: nowrap;
  border: 0; border-radius: 6px; background: transparent; color: var(--ink-2); cursor: pointer;
  transition: color .15s, background-color .15s, box-shadow .15s;
}
.seg button:hover { color: var(--ink); }
.seg button[aria-pressed="true"] { background: var(--surface); color: var(--ink); box-shadow: 0 1px 2px oklch(0.2 0.02 240 / 0.1), 0 0 0 1px var(--line-strong); }
.seg button:focus-visible { outline-offset: 0; }
.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 6px; height: 32px; padding: 0 12px;
  border-radius: 8px; border: 1px solid var(--line-strong); background: var(--surface); color: var(--ink);
  font-size: var(--t-sm); font-weight: 500; text-decoration: none; cursor: pointer; white-space: nowrap;
  transition: background-color .15s, border-color .15s, color .15s, transform .1s;
}
.btn:hover { background: var(--surface-2); }
.btn:active { transform: translateY(1px); }
.btn.primary { background: var(--accent); border-color: var(--accent); color: var(--on-accent); }
.btn.primary:hover { background: color-mix(in srgb, var(--accent) 88%, var(--ink)); }
.btn.ghost { border-color: transparent; background: transparent; color: var(--ink-2); }
.btn.ghost:hover { color: var(--ink); background: var(--surface-2); }
.btn[aria-disabled="true"] { opacity: .5; pointer-events: none; }

/* Grade glyphs: shape + colour, never colour alone */
.glyph { flex: none; display: inline-block; vertical-align: -1px; }
.glyph.good { color: var(--good); } .glyph.avg { color: var(--avg); } .glyph.poor { color: var(--poor); }
.delta { display: inline-flex; align-items: center; gap: 3px; font-size: var(--t-sm); color: var(--ink-2); white-space: nowrap; }
.delta svg { flex: none; color: var(--ink-3); }
.delta.up svg { color: var(--good); } .delta.down svg { color: var(--poor); }

.swatch { display: inline-block; width: 12px; height: 3px; border-radius: 2px; vertical-align: 3px; margin-right: 6px; background: var(--c); }
.legend { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 16px; font-size: var(--t-sm); color: var(--ink-2); }
.legend .note { color: var(--ink-3); }
.legend .dash { display: inline-block; width: 14px; border-top: 1.5px dashed var(--ink-3); vertical-align: 3px; margin-right: 6px; }
.legend .vline { display: inline-block; height: 11px; border-left: 1.5px dashed var(--ink-2); vertical-align: -1px; margin-right: 6px; }
.hint-btn {
  display: inline-flex; align-items: center; gap: 4px; padding: 0; border: 0; background: none;
  font: inherit; color: inherit; cursor: help; text-decoration: underline dotted; text-underline-offset: 3px;
}
.hint-btn:hover { color: var(--ink); }
.hint-btn svg, .mc-flag svg { flex: none; color: var(--ink-3); }
.mc-flag {
  position: absolute; z-index: 1; display: inline-flex; align-items: center; gap: 4px; height: 20px; padding: 0 6px;
  border: 1px solid var(--line-strong); border-radius: 5px; background: var(--surface); color: var(--ink-2);
  font-size: 11px; font-weight: 500; white-space: nowrap; cursor: help; transition: color .15s, border-color .15s;
}
.mc-flag:hover, .mc-flag:focus-visible { color: var(--ink); border-color: var(--ink-3); }
.tip-hint { max-width: 300px; white-space: normal; line-height: 1.5; color: var(--ink-2); }
.tip-hint ul { margin: 4px 0 6px; padding-left: 14px; list-style: disc; }
.tip-hint li + li { margin-top: 4px; }
.tip-hint p { color: var(--ink-3); }
.tip-foot { margin-top: 4px; padding-top: 4px; border-top: 1px solid var(--line); color: var(--ink-3); }

/* Rankings list */
.list-wrap { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; }
.list-meta { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2) var(--space-4); padding: 10px var(--space-4); border-bottom: 1px solid var(--line); }
.list-meta .count { margin-left: auto; font-size: var(--t-sm); color: var(--ink-3); }
.row {
  position: relative; display: grid; align-items: center; column-gap: var(--space-3);
  grid-template-columns: 20px 26px minmax(170px, 1fr) 62px 64px 70px minmax(150px, 1.15fr) repeat(3, 40px);
  grid-template-areas: "check rank name cur delta cwv spark a11y bp seo";
  padding: 0 var(--space-4); min-height: 58px; border-top: 1px solid var(--line);
  transition: background-color .12s;
}
.list-head { min-height: 34px; border-top: 0; font-size: var(--t-xs); font-weight: 500; color: var(--ink-3); background: var(--surface-2); }
.list-head span:nth-child(n+4) { text-align: right; }
.list-head .spark-h { text-align: left !important; }
li.row:hover { background: var(--hover); }
li.row.home { background: var(--home); }
li.row.home:hover { background: var(--home-hover); }
li.row.selected { background: color-mix(in srgb, var(--accent) 6%, var(--surface)); }
.check { grid-area: check; position: relative; z-index: 1; display: grid; place-items: center; width: 32px; height: 32px; margin: -6px; cursor: pointer; }
.check input { appearance: none; width: 16px; height: 16px; margin: 0; border: 1.5px solid var(--line-strong); border-radius: 4px; background: var(--surface); cursor: pointer; display: grid; place-items: center; transition: background-color .12s, border-color .12s; }
.check input:hover { border-color: var(--ink-3); }
.check input:checked { background: var(--accent); border-color: var(--accent); }
.check input:checked::after { content: ''; width: 8px; height: 4px; border: solid var(--on-accent); border-width: 0 0 2px 2px; transform: translateY(-1px) rotate(-45deg); }
.check input:disabled { opacity: .4; cursor: not-allowed; }
.rank { grid-area: rank; color: var(--ink-3); font-size: var(--t-sm); text-align: right; }
.name { grid-area: name; min-width: 0; padding: 9px 0; }
.name a { display: flex; align-items: center; gap: 7px; min-width: 0; font-weight: 500; text-decoration: none; }
.name a .nm { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tag {
  flex: none; display: inline-flex; align-items: center; height: 17px; padding: 0 5px;
  border: 1px solid var(--line-strong); border-radius: 4px; background: var(--surface-2);
  font-size: 10.5px; font-weight: 500; letter-spacing: 0.02em; line-height: 1; color: var(--ink-2);
}
h1 .tag { height: 20px; font-size: 12px; vertical-align: 5px; margin-left: 8px; }
.name a::after { content: ''; position: absolute; inset: 0; }
.name a:focus-visible { outline: none; }
.name a:focus-visible::after { outline: 2px solid var(--accent); outline-offset: -2px; border-radius: 2px; }
.name .sub { display: block; font-size: var(--t-xs); color: var(--ink-3); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-top: 1px; }
.cur { grid-area: cur; display: flex; align-items: center; justify-content: flex-end; gap: 7px; font-size: 1.0625rem; font-weight: 500; }
.row > .delta { grid-area: delta; justify-content: flex-end; }
.spark { grid-area: spark; position: relative; z-index: 1; height: 44px; display: block; cursor: crosshair; }
.spark svg { display: block; width: 100%; height: 100%; overflow: visible; }
.spark .guide { stroke: var(--ink-3); stroke-width: 1; opacity: 0; }
.spark:hover .guide { opacity: .6; }
.mini { text-align: right; font-size: var(--t-sm); color: var(--ink-2); }
.mini.a11y { grid-area: a11y; } .mini.bp { grid-area: bp; } .mini.seo { grid-area: seo; }
.cwv { display: inline-flex; align-items: center; gap: 5px; font-size: var(--t-sm); color: var(--ink-2); white-space: nowrap; }
.row > .cwv-cell { grid-area: cwv; display: flex; justify-content: flex-end; }
.sub-cwv { display: none; }
.empty { padding: var(--space-7) var(--space-4); text-align: center; color: var(--ink-3); }
.empty b { display: block; color: var(--ink); font-weight: 500; margin-bottom: 4px; }

/* Tooltip */
.tip {
  position: fixed; z-index: var(--z-tip); pointer-events: none; min-width: 168px;
  padding: 8px 10px; border-radius: 8px; background: var(--surface); border: 1px solid var(--line-strong);
  box-shadow: var(--shadow-pop); font-size: var(--t-xs); color: var(--ink-2);
}
.tip-title { color: var(--ink); font-weight: 500; margin-bottom: 4px; }
.tip-row { display: flex; align-items: center; gap: 6px; line-height: 1.7; }
.tip-row .v { margin-left: auto; padding-left: 12px; color: var(--ink); }

/* Compare tray */
.tray {
  position: fixed; left: 50%; bottom: var(--space-5); z-index: var(--z-bar);
  display: flex; align-items: center; gap: var(--space-2); max-width: calc(100vw - 32px);
  padding: 6px 6px 6px 14px; border-radius: 12px; background: var(--surface); border: 1px solid var(--line-strong); box-shadow: var(--shadow-pop);
  transform: translate(-50%, 12px); opacity: 0; visibility: hidden;
  transition: transform .22s var(--ease-out), opacity .22s var(--ease-out), visibility 0s .22s;
}
.tray.open { transform: translate(-50%, 0); opacity: 1; visibility: visible; transition: transform .22s var(--ease-out), opacity .22s var(--ease-out); }
.tray-label { font-size: var(--t-sm); color: var(--ink-2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
.tray-label b { color: var(--ink); font-weight: 500; }

/* Panels */
.panel { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; margin-top: var(--space-4); }
.panel-head { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2) var(--space-4); padding: 12px var(--space-4); border-bottom: 1px solid var(--line); }
.panel-title { font-weight: 600; font-size: var(--t-md); letter-spacing: -0.01em; }
.panel-head .end { margin-left: auto; }
.chart-box { position: relative; height: 320px; padding: var(--space-4) var(--space-2) var(--space-2) var(--space-2); }
.chart-box.sm { height: 200px; }

/* Summary strips (detail + compare) */
.strip { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); background: var(--surface); border: 1px solid var(--line); border-radius: 10px; }
.strip + .strip { margin-top: var(--space-3); }
.strip > div { padding: 14px var(--space-4); border-left: 1px solid var(--line); min-width: 0; }
.strip > div:first-child { border-left: 0; }
.strip-label { font-size: var(--t-sm); color: var(--ink-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.strip-value { display: flex; align-items: center; gap: 8px; margin-top: 4px; font-size: 1.5rem; font-weight: 500; letter-spacing: -0.02em; line-height: 1.2; }
.strip-sub { display: flex; flex-wrap: wrap; gap: 2px 10px; margin-top: 4px; font-size: var(--t-xs); color: var(--ink-3); }
.strip.vitals .strip-value, .strip.five .strip-value { font-size: 1.1875rem; }
.strip.five { grid-template-columns: repeat(5, minmax(0, 1fr)); }
.strip.flat { border: 0; border-radius: 0; border-bottom: 1px solid var(--line); background: transparent; }
.panel-head .cwv { font-size: var(--t-sm); }
tr.group td { padding-top: 14px; font-size: var(--t-xs); font-weight: 500; color: var(--ink-3); background: var(--surface-2); }

.multiples { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
.multiples > div { border-top: 1px solid var(--line); border-left: 1px solid var(--line); padding: var(--space-3) var(--space-4) var(--space-2); min-width: 0; }
.multiples > div:nth-child(-n+2) { border-top: 0; }
.multiples > div:nth-child(odd) { border-left: 0; }
.mult-head { display: flex; align-items: baseline; gap: var(--space-2); font-size: var(--t-sm); }
.mult-head b { font-weight: 500; }
.mult-head span { color: var(--ink-3); font-size: var(--t-xs); }

/* Tables */
.table-scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: var(--t-sm); }
th { font-size: var(--t-xs); font-weight: 500; color: var(--ink-3); text-align: right; padding: 8px var(--space-4); background: var(--surface-2); border-bottom: 1px solid var(--line); white-space: nowrap; }
td { padding: 9px var(--space-4); text-align: right; border-top: 1px solid var(--line); white-space: nowrap; }
th:first-child, td:first-child { text-align: left; }
tbody tr:first-child td { border-top: 0; }
tbody tr:hover td { background: var(--hover); }
td .cell { display: inline-flex; align-items: center; gap: 6px; }
td.best { font-weight: 600; color: var(--ink); }
.best-tag { font-family: 'Geist', sans-serif; font-size: 10.5px; font-weight: 500; letter-spacing: 0.01em; color: var(--accent-ink); background: var(--accent-soft); border-radius: 4px; padding: 0 5px; line-height: 17px; }
.more { display: block; width: 100%; height: 40px; border: 0; border-top: 1px solid var(--line); background: transparent; color: var(--ink-2); font-size: var(--t-sm); cursor: pointer; border-radius: 0 0 10px 10px; }
.more:hover { color: var(--ink); background: var(--hover); }

/* Compare page */
.picker { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); }
.chip {
  display: inline-flex; align-items: center; gap: 8px; height: 32px; padding: 0 4px 0 10px;
  border: 1px solid var(--line-strong); border-radius: 8px; background: var(--surface); font-size: var(--t-sm); font-weight: 500;
  animation: chip-in .2s var(--ease-out);
}
.chip .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--c); flex: none; }
.chip button { display: grid; place-items: center; width: 24px; height: 24px; border: 0; border-radius: 5px; background: transparent; color: var(--ink-3); cursor: pointer; }
.chip button:hover { color: var(--ink); background: var(--surface-2); }
@keyframes chip-in { from { opacity: 0; transform: scale(.96); } }
.combo { position: relative; flex: 0 1 280px; }
.combo .search { max-width: none; width: 100%; }
.listbox {
  position: absolute; top: calc(100% + 6px); left: 0; z-index: var(--z-popover); width: max(100%, 320px); max-height: 320px; overflow-y: auto;
  padding: 4px; background: var(--surface); border: 1px solid var(--line-strong); border-radius: 10px; box-shadow: var(--shadow-pop);
}
.opt { display: flex; align-items: center; gap: 8px; padding: 7px 8px; border-radius: 6px; font-size: var(--t-sm); cursor: pointer; }
.opt .num { margin-left: auto; color: var(--ink-3); display: inline-flex; align-items: center; gap: 6px; }
.opt[aria-selected="true"] { background: var(--surface-2); }
.opt[aria-disabled="true"] { color: var(--ink-3); cursor: default; }
.opt-empty { padding: 10px 8px; font-size: var(--t-sm); color: var(--ink-3); }
.suggest { display: flex; flex-wrap: wrap; justify-content: center; gap: var(--space-2); margin-top: var(--space-4); }
.compare-table th:not(:first-child) { min-width: 120px; }
.compare-table th .cell { justify-content: flex-end; }
.compare-table td:first-child { color: var(--ink-2); }
.skeleton { position: absolute; inset: var(--space-4); border-radius: 8px; background: linear-gradient(90deg, var(--surface-2), var(--hover), var(--surface-2)); background-size: 200% 100%; animation: shimmer 1.4s linear infinite; }
@keyframes shimmer { to { background-position: -200% 0; } }

.foot { padding: var(--space-6) 0 var(--space-8); color: var(--ink-3); font-size: var(--t-sm); max-width: 76ch; text-wrap: pretty; }
.foot p + p { margin-top: var(--space-2); }

@media (max-width: 1000px) {
  .row { grid-template-columns: 20px 26px minmax(150px, 1fr) 58px 60px 64px minmax(120px, 1fr); grid-template-areas: "check rank name cur delta cwv spark"; }
  .mini, .list-head .hide-md { display: none; }
}
@media (max-width: 640px) {
  .wrap { padding: 0 var(--space-4); }
  .topbar .wrap { gap: var(--space-3); }
  .brand span { display: none; }
  .page-head { padding: var(--space-6) 0 var(--space-4); }
  .page-head h1 { font-size: 1.375rem; }
  .toolbar .spacer { display: none; }
  .search { max-width: none; flex-basis: 100%; }
  .kbd { display: none; }
  .list-head { display: none; }
  .row {
    grid-template-columns: 20px minmax(0, 1fr) auto auto; grid-template-areas: "check name cur delta" ". spark spark spark";
    padding: 4px var(--space-3) 10px; row-gap: 2px; column-gap: var(--space-3);
  }
  .rank { display: none; }
  .row > .cwv-cell { display: none; }
  .sub-cwv { display: inline; }
  .strip.five > div:nth-child(odd) { border-left: 0; }
  .spark { height: 34px; }
  .list-meta .count { margin-left: 0; width: 100%; }
  .strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .strip > div:nth-child(3) { border-left: 0; }
  .strip > div:nth-child(n+3) { border-top: 1px solid var(--line); }
  .multiples { grid-template-columns: 1fr; }
  .multiples > div { border-left: 0 !important; }
  .multiples > div:nth-child(2) { border-top: 1px solid var(--line); }
  .chart-box { height: 260px; }
  .tray { left: var(--space-4); right: var(--space-4); bottom: var(--space-3); transform: translateY(12px); }
  .tray.open { transform: none; }
  .tray-label { flex: 1; }
  .combo { flex: 1 1 100%; }
  .panel-head .seg.end { margin-left: 0; max-width: 100%; overflow-x: auto; scrollbar-width: none; }
  .compare-table th:first-child, .compare-table td:first-child { position: sticky; left: 0; z-index: 1; background: var(--surface); white-space: normal; min-width: 116px; }
  .compare-table th:first-child { background: var(--surface-2); }
  .compare-table th:not(:first-child) { min-width: 104px; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0s !important; transition-duration: 0s !important; }
  .skeleton { animation: none; }
}
"""

# Shared client helpers, inlined into every page
COMMON_JS = r"""
const FIELDS = ['performance', 'accessibility', 'best_practices', 'seo', 'first_contentful_paint', 'largest_contentful_paint', 'total_blocking_time', 'cumulative_layout_shift'];
const COL = Object.fromEntries(FIELDS.map((f, i) => [f, i + 1]));  // daily rows are [day, ...FIELDS]
const SCORE_KEYS = FIELDS.slice(0, 4);
const VITAL_KEYS = ['largest_contentful_paint', 'first_contentful_paint', 'total_blocking_time', 'cumulative_layout_shift'];
const META = {
  performance: { label: 'Performance', short: 'Perf.', kind: 'score' },
  accessibility: { label: 'Accessibility', short: 'A11y', kind: 'score' },
  best_practices: { label: 'Best practices', short: 'BP', kind: 'score' },
  seo: { label: 'SEO', short: 'SEO', kind: 'score' },
  largest_contentful_paint: { label: 'Largest contentful paint', short: 'LCP', kind: 'ms', good: 2500, poor: 4000 },
  first_contentful_paint: { label: 'First contentful paint', short: 'FCP', kind: 'ms', good: 1800, poor: 3000 },
  total_blocking_time: { label: 'Total blocking time', short: 'TBT', kind: 'ms', good: 200, poor: 600 },
  cumulative_layout_shift: { label: 'Cumulative layout shift', short: 'CLS', kind: 'cls', good: 0.1, poor: 0.25 },
  interaction_to_next_paint: { label: 'Interaction to next paint', short: 'INP', kind: 'ms', good: 200, poor: 500 },
  experimental_time_to_first_byte: { label: 'Time to first byte', short: 'TTFB', kind: 'ms', good: 800, poor: 1800 },
};
// Series colour per metric (fixed so a metric keeps its colour on every chart)
const SERIES = {
  performance: '--s1', accessibility: '--s2', best_practices: '--s3', seo: '--s4',
  largest_contentful_paint: '--s1', first_contentful_paint: '--s2', total_blocking_time: '--s3', cumulative_layout_shift: '--s4',
  interaction_to_next_paint: '--s5', experimental_time_to_first_byte: '--s6',
};
// Real-user (CrUX) rows are [last day of the 28-day period, ...CRUX_KEYS p75s]; crux.py writes this order
const CRUX_KEYS = ['largest_contentful_paint', 'interaction_to_next_paint', 'cumulative_layout_shift', 'first_contentful_paint', 'experimental_time_to_first_byte'];
const CWV_KEYS = CRUX_KEYS.slice(0, 3);
// Google's assessment: LCP, INP and CLS all good at the 75th percentile (INP may be missing on quiet sites)
function cwvPass(v) {
  const [lcp, inp, cls] = v;
  if (!has(lcp) || !has(cls)) return null;
  return lcp <= META.largest_contentful_paint.good && cls <= META.cumulative_layout_shift.good && (!has(inp) || inp <= META.interaction_to_next_paint.good);
}

const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const has = v => v != null && Number.isFinite(v);
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const median = xs => { const s = xs.filter(has).sort((a, b) => a - b); if (!s.length) return null; const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const avg = xs => { const s = xs.filter(has); return s.length ? s.reduce((a, b) => a + b, 0) / s.length : null; };
const lowerIsBetter = key => META[key].kind !== 'score';

const dayDate = d => new Date(d + 'T00:00:00Z');
const addDays = (d, n) => new Date(dayDate(d).getTime() + n * 864e5).toISOString().slice(0, 10);
const fmtDay = (d, opts = { day: 'numeric', month: 'short', year: 'numeric' }) => dayDate(d).toLocaleDateString('en-GB', { ...opts, timeZone: 'UTC' });
const daysAgo = d => Math.floor((Date.now() - dayDate(d).getTime()) / 864e5);

function fmt(key, v) {
  if (!has(v)) return '–';
  const kind = META[key].kind;
  if (kind === 'score') return String(Math.round(v));
  if (kind === 'cls') return v.toFixed(3);
  return v < 1000 ? `${Math.round(v)} ms` : `${(v / 1000).toFixed(v < 10000 ? 2 : 1)} s`;
}
function gradeOf(key, v) {
  if (!has(v)) return null;
  const m = META[key];
  if (m.kind === 'score') return v >= 89.5 ? 'good' : v >= 49.5 ? 'avg' : 'poor';
  return v <= m.good ? 'good' : v <= m.poor ? 'avg' : 'poor';
}
const GRADE_LABEL = { good: 'Good', avg: 'Needs improvement', poor: 'Poor' };
const GLYPH_SHAPE = {
  good: '<circle cx="5" cy="5" r="4" fill="currentColor"/>',
  avg: '<rect x="1.25" y="1.25" width="7.5" height="7.5" rx="1" fill="currentColor"/>',
  poor: '<path d="M5 .9l4.4 8.1H.6z" fill="currentColor"/>',
};
const glyph = (g, size = 10) => g ? `<svg class="glyph ${g}" width="${size}" height="${size}" viewBox="0 0 10 10" role="img" aria-label="${GRADE_LABEL[g]}"><title>${GRADE_LABEL[g]}</title>${GLYPH_SHAPE[g]}</svg>` : '';
const graded = (key, v, size) => `${glyph(gradeOf(key, v), size)}<span>${fmt(key, v)}</span>`;
const thresholdText = key => { const m = META[key]; return m.kind === 'score' ? '90+ is good' : `Good ≤ ${fmt(key, m.good)}`; };

const ARROW = {
  up: '<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 13V3M3.5 7.5L8 3l4.5 4.5"/></svg>',
  down: '<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 3v10M3.5 8.5L8 13l4.5-4.5"/></svg>',
  flat: '<svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M3.5 8h9"/></svg>',
};
// Score change; for timings pass lowerBetter so a drop reads as an improvement
function deltaHtml(d, { lowerBetter = false, unit = '', label = 'over 30 days', format = v => Math.round(Math.abs(v)), flatBelow = 1 } = {}) {
  if (!has(d)) return '<span class="delta muted" title="Not enough comparable data">–</span>';
  if (Math.abs(d) < flatBelow) return `<span class="delta flat" title="No change ${label}">${ARROW.flat}<span class="num">0</span></span>`;
  const better = lowerBetter ? d < 0 : d > 0;
  const dir = better ? 'up' : 'down';
  const sign = d > 0 ? '+' : '−';
  return `<span class="delta ${dir}" title="${better ? 'Better' : 'Worse'} by ${format(d)}${unit} ${label}">${d > 0 ? ARROW.up : ARROW.down}<span class="num">${sign}${format(d)}${unit}</span></span>`;
}

// Segmented controls: <div class="seg" data-key="x"><button data-value="...">
function bindSeg(state, onChange, root = document) {
  root.querySelectorAll('.seg[data-key]').forEach(seg => {
    const key = seg.dataset.key;
    const sync = () => seg.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', b.dataset.value === String(state[key])));
    seg.addEventListener('click', e => {
      const btn = e.target.closest('button');
      if (!btn || btn.dataset.value === String(state[key])) return;
      state[key] = btn.dataset.value;
      sync();
      onChange(key);
    });
    sync();
  });
}

const tip = (() => {
  const el = document.createElement('div');
  el.className = 'tip'; el.hidden = true; el.setAttribute('role', 'tooltip');
  document.body.append(el);
  return {
    show(htmlStr, x, y) {
      el.innerHTML = htmlStr; el.hidden = false;
      const r = el.getBoundingClientRect(), pad = 12;
      let left = x + 14, top = y - r.height - 10;
      if (left + r.width > innerWidth - pad) left = x - r.width - 14;
      if (top < pad) top = y + 18;
      el.style.left = `${Math.max(pad, left)}px`; el.style.top = `${top}px`;
    },
    hide() { el.hidden = true; },
  };
})();
const tipRow = (color, label, value) => `<div class="tip-row"><span class="swatch" style="--c:${color}"></span>${esc(label)}<span class="v num">${value}</span></div>`;

// Trailing rolling median per column over `days` calendar days (rows are [day, ...FIELDS]).
// Days on or after `floor` (the method change) never include days before it.
function smooth(rows, days = 7, floor = null) {
  let lo = 0;
  return rows.map((r, hi) => {
    let cutoff = addDays(r[0], -(days - 1));
    if (floor && r[0] >= floor && cutoff < floor) cutoff = floor;
    while (rows[lo][0] < cutoff) lo++;
    const win = rows.slice(lo, hi + 1);
    return [r[0], ...FIELDS.map((_, i) => median(win.map(w => w[i + 1])))];
  });
}
const DISPLAY_KEYS = [...SCORE_KEYS, ...VITAL_KEYS];

const storage = {
  get(k, fallback) { try { const v = sessionStorage.getItem(k); return v ? JSON.parse(v) : fallback; } catch { return fallback; } },
  set(k, v) { try { sessionStorage.setItem(k, JSON.stringify(v)); } catch {} },
};
const MAX_COMPARE = 6;

// c = { day, v: [...CRUX_KEYS], scope: 'page' | 'origin' }
function cwvBadge(c, { word = true } = {}) {
  const pass = c ? cwvPass(c.v) : null;
  if (pass == null) return '<span class="cwv muted" title="Not enough real-user data from Chrome">–</span>';
  const title = `Core Web Vitals for real Chrome users, 28 days to ${fmtDay(c.day)}${c.scope === 'origin' ? ' (whole site)' : ''}: ` +
    CWV_KEYS.map((k, i) => `${META[k].short} ${fmt(k, c.v[i])}`).join(', ');
  return `<span class="cwv" title="${esc(title)}">${glyph(pass ? 'good' : 'poor', 9)}${word ? `<span>${pass ? 'Pass' : 'Fail'}</span>` : ''}</span>`;
}

// University groups from the sites file, shown as small tags beside the name
const GROUPS = { 'Russell Group': { short: 'RG', title: 'Russell Group member' } };
const groupTags = groups => (groups || []).map(g => `<span class="tag" title="${esc(GROUPS[g]?.title || g)}"><span aria-hidden="true">${esc(GROUPS[g]?.short || g)}</span><span class="sr-only">${esc(g)}</span></span>`).join('');

// First day of the corrected test method (desktop preset, one test per machine); null until it has run
const INFO_ICON = '<svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true"><circle cx="8" cy="8" r="6.25"/><path d="M8 7.25v4M8 4.75v.01"/></svg>';
const methodLegend = day => `<span class="note"><span class="vline"></span><button type="button" class="hint-btn" data-method-hint="${day}">methodology changed${INFO_ICON}</button></span>`;
const methodHint = day => `<div class="tip-hint"><div class="tip-title">Methodology changed · ${fmtDay(day)}</div>
  From this date:<ul>
  <li>Desktop tests use Lighthouse's real desktop setup. Before, they emulated a phone on a faster connection.</li>
  <li>Each test runs on its own machine, one at a time. Before, several ran at once, which inflated blocking time and lowered performance scores.</li></ul>
  <p>Results either side of the line aren't directly comparable, so change figures that span it are hidden.</p></div>`;

// Any [data-method-hint] element explains the change on hover, focus or tap
(() => {
  let pinned = null;
  const show = el => { const r = el.getBoundingClientRect(); tip.show(methodHint(el.dataset.methodHint), r.left, r.top); };
  const target = e => e.target.closest?.('[data-method-hint]');
  document.addEventListener('pointerover', e => { const t = target(e); if (t) show(t); });
  document.addEventListener('pointerout', e => { if (target(e) && !e.relatedTarget?.closest?.('[data-method-hint]') && !pinned) tip.hide(); });
  document.addEventListener('focusin', e => { const t = target(e); if (t) show(t); });
  document.addEventListener('focusout', e => { if (target(e)) { pinned = null; tip.hide(); } });
  document.addEventListener('click', e => {
    const t = target(e);
    if (t) { pinned = pinned === t ? null : t; pinned ? show(t) : tip.hide(); }
    else if (pinned) { pinned = null; tip.hide(); }
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && document.activeElement?.matches?.('[data-method-hint]')) { pinned = null; tip.hide(); } });
})();
function methodNote(day) {
  const el = $('#methodNote');
  if (!el || !day) return;
  el.hidden = false;
  el.innerHTML = `The dashed vertical line marks <b>${fmtDay(day)}</b>, when the testing methodology changed. Desktop tests now use Lighthouse's real desktop setup
    (before then they mistakenly emulated a phone on a faster connection), and each test runs on its own machine instead of several at once, which had inflated
    total blocking time and lowered performance scores. Results either side of the line aren't directly comparable.`;
}
const inWindow = (day, from, to) => !!day && (!from || day >= from) && (!to || day <= to);
// Summary figures only use results from one method: when [from, to] crosses the change, start at the change
const methodFloor = (day, from, to) => day && (!from || from < day) && day <= to ? day : from;
// True when comparing [prevFrom, to] would mix results from before and after the method change
const spansChange = (day, prevFrom, to) => !!day && !!prevFrom && prevFrom < day && day <= to;
"""

# Chart.js helpers, inlined into pages that draw full charts
CHART_HELPERS_JS = r"""
Chart.defaults.font.family = "'Geist', ui-sans-serif, system-ui, sans-serif";
Chart.defaults.font.size = 11.5;

// Horizontal reference lines (Web Vitals thresholds), drawn under the data
const thresholdPlugin = {
  id: 'thresholds',
  beforeDatasetsDraw(chart, _, opts) {
    const lines = opts?.lines || [];
    const { ctx, chartArea: a, scales: { y } } = chart;
    ctx.save();
    ctx.font = `11px ${Chart.defaults.font.family}`;
    ctx.textBaseline = 'bottom';
    lines.forEach(l => {
      if (l.value < y.min || l.value > y.max) return;
      const py = Math.round(y.getPixelForValue(l.value)) + 0.5;
      ctx.strokeStyle = css('--ink-3'); ctx.globalAlpha = 0.55; ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.moveTo(a.left, py); ctx.lineTo(a.right, py); ctx.stroke();
      ctx.globalAlpha = 1; ctx.setLineDash([]); ctx.fillStyle = css('--ink-3'); ctx.textAlign = 'right';
      ctx.fillText(l.label, a.right - 2, py - 3);
    });
    ctx.restore();
  },
};

// Direct labels at the end of each line, nudged apart so they never overlap
const endLabelPlugin = {
  id: 'endLabels',
  afterDatasetsDraw(chart, _, opts) {
    if (!opts?.enabled) return;
    const { ctx, chartArea: a } = chart;
    const items = chart.data.datasets.map((ds, i) => {
      const meta = chart.getDatasetMeta(i);
      const pts = meta.data.filter(p => !p.skip && has(p.y));
      return pts.length && !meta.hidden ? { label: ds.label, color: ds.borderColor, y: pts[pts.length - 1].y } : null;
    }).filter(Boolean).sort((p, q) => p.y - q.y);
    const gap = 14;
    for (let i = 1; i < items.length; i++) items[i].y = Math.max(items[i].y, items[i - 1].y + gap);
    const overflow = items.length ? items[items.length - 1].y - (a.bottom + 4) : 0;
    if (overflow > 0) items.forEach(it => { it.y -= overflow; });
    ctx.save();
    ctx.font = `500 11.5px ${Chart.defaults.font.family}`;
    ctx.textBaseline = 'middle';
    items.forEach(it => {
      ctx.fillStyle = it.color; ctx.beginPath(); ctx.arc(a.right + 8, it.y, 3, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = css('--ink-2'); ctx.fillText(it.label, a.right + 15, it.y);
    });
    ctx.restore();
  },
};
// Vertical marker for the test-method change
const methodPlugin = {
  id: 'methodChange',
  afterDatasetsDraw(chart, _, opts) {
    if (!opts?.at) return;
    const { ctx, chartArea: a, scales: { x } } = chart;
    if (opts.at < x.min || opts.at > x.max) return;
    const px = Math.round(x.getPixelForValue(opts.at)) + 0.5;
    ctx.save();
    ctx.strokeStyle = css('--ink-2'); ctx.globalAlpha = 0.7; ctx.lineWidth = 1.25; ctx.setLineDash([4, 3]);
    ctx.beginPath(); ctx.moveTo(px, a.top - 14); ctx.lineTo(px, a.bottom); ctx.stroke();
    ctx.restore();
    // The label is a real button (hover, focus or tap explains the change), placed in the strip above the plot
    const flag = chart.canvas.parentElement.querySelector('.mc-flag');
    if (!flag) return;
    flag.hidden = false;
    const cx = chart.canvas.offsetLeft, cy = chart.canvas.offsetTop;
    const w = flag.offsetWidth;
    const left = px + 4 + w > a.right ? px - 4 - w : px + 4;
    flag.style.left = `${cx + left}px`; flag.style.top = `${cy + a.top - 21}px`;
  },
  beforeDraw(chart, _, opts) {
    const flag = chart.canvas.parentElement.querySelector('.mc-flag');
    if (flag && (!opts?.at || opts.at < chart.scales.x.min || opts.at > chart.scales.x.max)) flag.hidden = true;
  },
};
Chart.register(thresholdPlugin, endLabelPlugin, methodPlugin);

function axisTicks(key) {
  const kind = META[key].kind;
  if (kind === 'score') return v => v;
  if (kind === 'cls') return v => v.toFixed(2);
  return v => v === 0 ? '0' : v >= 1000 ? `${+(v / 1000).toFixed(1)} s` : `${v} ms`;
}

// Base line-chart config. series: [{ label, color, data: [{x, y}], width }]
function lineChart(canvas, { series, key, endLabels = false, rightPad = 0, yMax, tooltipLabel, methodChange = null, gapDays = 3 }) {
  const grid = css('--grid'), axis = css('--axis'), muted = css('--ink-3');
  const kind = META[key].kind;
  const box = canvas.parentElement;
  if (methodChange && !box.querySelector('.mc-flag')) {
    box.insertAdjacentHTML('beforeend', `<button type="button" class="mc-flag" data-method-hint="${methodChange}" hidden>Methodology changed${INFO_ICON}</button>`);
  }
  const thresholds = kind === 'score' ? [] : [{ value: META[key].good, label: 'Good' }, { value: META[key].poor, label: 'Poor' }];
  return new Chart(canvas, {
    type: 'line',
    data: {
      datasets: series.map(s => ({
        label: s.label, data: s.data, borderColor: s.color, backgroundColor: s.color,
        borderWidth: s.width || 2, pointHoverRadius: 4, pointHoverBorderWidth: 2,
        pointRadius: c => {
          const d = c.dataset.data, i = c.dataIndex, gap = gapDays * 864e5;
          return (i === 0 || d[i].x - d[i - 1].x > gap) && (i === d.length - 1 || d[i + 1].x - d[i].x > gap) ? 2.5 : 0;
        },
        pointHoverBorderColor: css('--surface'), tension: 0.25, spanGaps: gapDays * 864e5,
      })),
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false, normalized: true,
      layout: { padding: { right: rightPad, top: methodChange ? 24 : 0 } },
      interaction: { mode: 'index', axis: 'x', intersect: false },
      plugins: {
        legend: { display: false },
        thresholds: { lines: thresholds },
        endLabels: { enabled: endLabels },
        methodChange: { at: methodChange ? dayDate(methodChange).getTime() : null },
        tooltip: {
          backgroundColor: css('--surface'), borderColor: css('--line-strong'), borderWidth: 1,
          titleColor: css('--ink'), bodyColor: css('--ink-2'), padding: 10, cornerRadius: 8,
          boxWidth: 8, boxHeight: 8, boxPadding: 4, usePointStyle: true,
          titleFont: { weight: '500' }, bodyFont: { family: "'Geist Mono', ui-monospace, monospace", size: 11.5 },
          callbacks: {
            title: items => new Date(items[0].parsed.x).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }),
            label: tooltipLabel || (i => ` ${i.dataset.label}  ${fmt(key, i.parsed.y)}`),
            labelPointStyle: () => ({ pointStyle: 'circle', rotation: 0 }),
          },
        },
      },
      scales: {
        x: { type: 'time', time: { tooltipFormat: 'd MMM yyyy' }, grid: { display: false }, border: { color: axis },
             ticks: { color: muted, maxTicksLimit: 7, maxRotation: 0, autoSkipPadding: 16 } },
        y: { min: 0, max: kind === 'score' ? 100 : yMax, grace: kind === 'score' ? 0 : '8%',
             grid: { color: grid }, border: { display: false },
             ticks: { color: muted, maxTicksLimit: 5, callback: axisTicks(key), ...(kind === 'score' ? { stepSize: 25 } : {}) } },
      },
    },
  });
}
"""

ICON_SEARCH = ('<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" '
               'stroke-linecap="round" aria-hidden="true"><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/></svg>')
BRAND_MARK = ('<svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="2" '
              'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 13.5l4.5-5 3.5 3 6-7.5"/>'
              '<path d="M2 16.5h14" opacity=".35"/></svg>')


def page_head(title: str, description: str, extra: str = '') -> str:
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description)}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 18 18'%3E%3Crect width='18' height='18' rx='4' fill='%23146a75'/%3E%3Cpath d='M3.5 12.5l3.5-4 3 2.5 4-5' fill='none' stroke='white' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="styles.css">
{extra}
</head>'''


def topbar(current: str, crumb: str = '') -> str:
    def link(href, label, key):
        aria = ' aria-current="page"' if key == current else ''
        return f'<a href="{href}"{aria}>{label}</a>'
    return f'''<header class="topbar">
  <div class="wrap">
    <a class="brand" href="index.html">{BRAND_MARK}<span>University Web Rankings</span></a>
    <nav class="nav" aria-label="Main">{link("index.html", "Rankings", "index")}{link("compare.html", "Compare", "compare")}</nav>
    <span class="topbar-meta" id="lastRun">{crumb}</span>
  </div>
</header>'''


STALE_NOTICE = r"""
function staleNotice(lastDay) {
  const el = $('#staleNotice');
  if (!el || !lastDay || daysAgo(lastDay) <= 2) return;
  el.hidden = false;
  el.innerHTML = `<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="8" cy="8" r="6.25"/><path d="M8 4.75V8.5l2.25 1.5"/></svg>
    <span>No new tests since <b>${fmtDay(lastDay)}</b> (${daysAgo(lastDay)} days ago). Scores below are from the most recent tests available.</span>`;
}
"""

INDEX_TEMPLATE = r"""
<body>
__TOPBAR__

<main class="wrap">
  <section class="page-head">
    <h1>How fast are UK university homepages?</h1>
    <p class="lede">Google Lighthouse tests the homepage of each university every day, on mobile and desktop.
      Scores are the median of each site's latest week of tests. Tick universities to compare them side by side.</p>
    <p class="facts" id="facts"></p>
  </section>

  <div class="notice" id="staleNotice" role="status" hidden></div>

  <div class="toolbar">
    <label class="search field">
      __ICON_SEARCH__
      <input type="search" id="search" placeholder="Find a university" aria-label="Find a university" autocomplete="off">
      <span class="kbd" aria-hidden="true">/</span>
    </label>
    <span class="spacer"></span>
    <div class="seg" data-key="device" role="group" aria-label="Device">
      <button data-value="mobile">Mobile</button><button data-value="desktop">Desktop</button>
    </div>
    <select class="field" id="sort" aria-label="Sort by">
      <option value="performance">Sort: Performance</option>
      <option value="trend">Sort: Biggest improvers</option>
      <option value="largest_contentful_paint">Sort: Fastest LCP</option>
      <option value="cwv">Sort: Real users (Core Web Vitals)</option>
      <option value="accessibility">Sort: Accessibility</option>
      <option value="best_practices">Sort: Best practices</option>
      <option value="seo">Sort: SEO</option>
      <option value="name">Sort: Name</option>
    </select>
  </div>

  <section class="list-wrap" aria-label="Rankings">
    <div class="list-meta">
      <div class="seg" data-key="chart" role="group" aria-label="Trend lines show">
        <button data-value="vitals">Web Vitals</button><button data-value="scores">Lighthouse scores</button>
      </div>
      <div class="legend" id="legend"></div>
      <span class="count" id="count"></span>
    </div>
    <div class="row list-head" aria-hidden="true">
      <span></span><span class="rank">#</span><span>University</span><span id="curHead">Perf.</span><span>30 days</span><span title="Core Web Vitals for real Chrome users over 28 days">Real users</span>
      <span class="spark-h">Last 90 days</span><span class="hide-md">A11y</span><span class="hide-md">BP</span><span class="hide-md">SEO</span>
    </div>
    <ol class="list" id="list"></ol>
  </section>

  <footer class="foot">
    <p>Scores are Google Lighthouse lab results (0–100): 90 or more is good, 50–89 needs improvement, under 50 is poor.
      The 30-day change compares the mean performance score of the latest 30 days of tests with the 30 days before.
      <span class="tag" aria-hidden="true">RG</span> marks members of the Russell Group.</p>
    <p>"Real users" is Google's Core Web Vitals assessment from the Chrome UX Report: how the homepage performed for real
      Chrome users over the latest 28 days. It passes when LCP, INP and CLS are all good for at least 75% of visits.
      Where the homepage gets too little traffic, figures for the whole site are used. "–" means Chrome has too little data.</p>
    <p>Web Vitals lines are each divided by Google's "good" threshold (LCP 2.5 s, FCP 1.8 s, TBT 200 ms, CLS 0.1),
      so anything under the dashed line is good and lower is better. The scale is logarithmic, from a quarter of the threshold to 16×.
      Lines in this list are 7-day rolling medians to smooth out day-to-day noise; detail pages show every day.</p>
    <p id="methodNote" hidden></p>
  </footer>
</main>

<div class="tray" id="tray" role="region" aria-label="Compare selection">
  <span class="tray-label" id="trayLabel" aria-live="polite"></span>
  <button class="btn ghost" id="trayClear" type="button">Clear</button>
  <a class="btn primary" id="trayGo" href="compare.html">Compare</a>
</div>

<script>
__COMMON__
__STALE__
const DATA = __DATA__;
const UNIS = DATA.universities;
const SPAN = DATA.spark_days;
const START = addDays(DATA.end, -(SPAN - 1));
const state = { device: 'mobile', chart: 'vitals', sort: 'performance', q: '' };
let selected = storage.get('compare', []).filter(s => UNIS.some(u => u.slug === s));

const dev = u => u.devices[state.device];
// The headline column shows performance, or LCP when sorting by it
const shownKey = () => state.sort === 'largest_contentful_paint' ? state.sort : 'performance';
const cur = (u, key) => dev(u)?.current?.[COL[key] - 1];

function sortValue(u) {
  const d = dev(u);
  if (!d) return null;
  if (state.sort === 'trend') return d.delta;
  if (state.sort === 'cwv') {
    // Passing sites first, then by real-user LCP (lower is better)
    const c = u.crux?.[state.device], pass = c ? cwvPass(c.v) : null;
    return pass == null ? null : (pass ? 1e6 : 0) - (c.v[0] ?? 1e6);
  }
  const v = cur(u, state.sort);
  return has(v) && lowerIsBetter(state.sort) ? -v : v;
}

// ---- Sparklines (hand-drawn SVG; one per row) ----
const W = 300, H = 44, PAD = 3;
const sparkKeys = () => state.chart === 'vitals' ? VITAL_KEYS : SCORE_KEYS;
// Vitals: ratio to the "good" threshold on a log2 axis from 1/4x to 16x (threshold sits at 1/3 height)
const LOG_MIN = -2, LOG_MAX = 4;
function sparkY(key, v) {
  const frac = state.chart === 'vitals'
    ? (Math.min(LOG_MAX, Math.max(LOG_MIN, Math.log2(Math.max(v, 1e-6) / META[key].good))) - LOG_MIN) / (LOG_MAX - LOG_MIN)
    : v / 100;
  return (H - PAD - frac * (H - 2 * PAD)).toFixed(1);
}
function sparkPath(rows, key) {
  const segments = [];
  let prev = null;
  for (const r of rows) {
    const v = r[COL[key]];
    if (!has(v)) { prev = null; continue; }
    if (prev == null || r[0] - prev > 3) segments.push([]);
    segments.at(-1).push(`${(r[0] / (SPAN - 1) * W).toFixed(1)} ${sparkY(key, v)}`);
    prev = r[0];
  }
  // A lone point becomes a dot (a tiny stroke with round caps)
  return segments.map(seg => `M${seg.join('L')}${seg.length === 1 ? 'l0.01 0' : ''}`).join('');
}
function sparkline(u) {
  const rows = dev(u)?.spark || [];
  if (!rows.length) return '<svg aria-hidden="true"></svg>';
  const ref = state.chart === 'vitals'
    ? `<line x1="0" x2="${W}" y1="${sparkY('largest_contentful_paint', META.largest_contentful_paint.good)}" y2="${sparkY('largest_contentful_paint', META.largest_contentful_paint.good)}" stroke="var(--ink-3)" stroke-width="1" stroke-dasharray="3 3" opacity=".6" vector-effect="non-scaling-stroke"/>`
    : `<line x1="0" x2="${W}" y1="${sparkY('performance', 90)}" y2="${sparkY('performance', 90)}" stroke="var(--grid)" stroke-width="1" vector-effect="non-scaling-stroke"/>`;
  const mOff = DATA.method_change ? Math.round((dayDate(DATA.method_change) - dayDate(START)) / 864e5) : -1;
  const mx = (mOff / (SPAN - 1) * W).toFixed(1);
  const marker = mOff >= 0 && mOff < SPAN
    ? `<line x1="${mx}" x2="${mx}" y1="0" y2="${H}" stroke="var(--ink-2)" stroke-width="1.25" stroke-dasharray="3 2" opacity=".7" vector-effect="non-scaling-stroke"/>` : '';
  const paths = sparkKeys().map(k => `<path d="${sparkPath(rows, k)}" fill="none" stroke="var(${SERIES[k]})" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>`).join('');
  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">${ref}${marker}${paths}<line class="guide" x1="0" x2="0" y1="0" y2="${H}" vector-effect="non-scaling-stroke"/></svg>`;
}

function renderLegend() {
  const keys = sparkKeys();
  $('#legend').innerHTML = keys.map(k => `<span><span class="swatch" style="--c:var(${SERIES[k]})"></span>${META[k].short}</span>`).join('') +
    (state.chart === 'vitals' ? '<span class="note"><span class="dash"></span>good threshold · lower is better</span>' : '<span class="note">0–100 · higher is better</span>') +
    (inWindow(DATA.method_change, START, DATA.end) ? methodLegend(DATA.method_change) : '');
}

function row(u, i) {
  const d = dev(u);
  const perf = cur(u, 'performance');
  const isSel = selected.includes(u.slug);
  const full = selected.length >= MAX_COMPARE && !isSel;
  const stale = d && daysAgo(d.last) > 2 && d.last < DATA.end;
  const v = cur(u, shownKey());
  return `<li class="row${isSel ? ' selected' : ''}${u.highlight ? ' home' : ''}" data-slug="${esc(u.slug)}">
    <label class="check" title="${full ? `You can compare up to ${MAX_COMPARE}` : 'Select to compare'}"><input type="checkbox" ${isSel ? 'checked' : ''} ${full ? 'disabled' : ''} aria-label="Compare ${esc(u.name)}"></label>
    <span class="rank num">${i + 1}</span>
    <span class="name"><a href="${esc(u.slug)}.html"><span class="nm">${esc(u.name)}</span>${groupTags(u.groups)}</a><span class="sub">${esc(u.domain)}${stale ? ` · last tested ${fmtDay(d.last, { day: 'numeric', month: 'short' })}` : ''}<span class="sub-cwv"> · Real users ${cwvBadge(u.crux?.[state.device])}</span></span></span>
    <span class="cur num" aria-label="${META[shownKey()].label} ${fmt(shownKey(), v)}">${graded(shownKey(), v)}</span>
    ${deltaHtml(d?.delta)}
    <span class="cwv-cell">${cwvBadge(u.crux?.[state.device])}</span>
    <span class="spark" data-slug="${esc(u.slug)}">${sparkline(u)}</span>
    ${['accessibility', 'best_practices', 'seo'].map((k, j) => `<span class="mini num ${['a11y', 'bp', 'seo'][j]}" title="${META[k].label}">${fmt(k, cur(u, k))}</span>`).join('')}
  </li>`;
}

function renderList() {
  const q = state.q.trim().toLowerCase();
  const unis = UNIS.filter(u => !q || u.name.toLowerCase().includes(q) || u.domain.includes(q));
  unis.sort((a, b) => {
    if (state.sort === 'name') return a.name.localeCompare(b.name);
    const av = sortValue(a), bv = sortValue(b);
    return (has(bv) ? bv : -Infinity) - (has(av) ? av : -Infinity) || a.name.localeCompare(b.name);
  });
  $('#curHead').textContent = META[shownKey()].short;
  $('#count').textContent = q ? `${unis.length} of ${UNIS.length}` : `${UNIS.length} universities`;
  $('#list').innerHTML = unis.length ? unis.map(row).join('')
    : `<li class="empty"><b>No universities match “${esc(state.q)}”</b>Try part of the name, or the web address.</li>`;
}

function renderTray() {
  const tray = $('#tray');
  const n = selected.length;
  tray.classList.toggle('open', n > 0);
  const names = selected.map(s => UNIS.find(u => u.slug === s)?.name).filter(Boolean);
  $('#trayLabel').innerHTML = n ? `<b>${n} selected</b> · ${esc(names.join(', '))}` : '';
  const go = $('#trayGo');
  go.href = `compare.html?u=${selected.join(',')}`;
  go.textContent = n < 2 ? 'Select one more' : `Compare ${n}`;
  go.setAttribute('aria-disabled', n < 2);
}

function render() { renderLegend(); renderList(); renderTray(); }

// Selection
$('#list').addEventListener('change', e => {
  if (!e.target.matches('.check input')) return;
  const slug = e.target.closest('.row').dataset.slug;
  selected = e.target.checked ? [...selected, slug].slice(0, MAX_COMPARE) : selected.filter(s => s !== slug);
  storage.set('compare', selected);
  const focusSlug = slug;
  renderList(); renderTray();
  $(`.row[data-slug="${CSS.escape(focusSlug)}"] .check input`)?.focus();
});
$('#trayClear').addEventListener('click', () => { selected = []; storage.set('compare', selected); renderList(); renderTray(); });

// Sparkline hover: nearest day, values in real units
$('#list').addEventListener('pointermove', e => {
  const box = e.target.closest('.spark');
  if (!box) return;
  const u = UNIS.find(x => x.slug === box.dataset.slug);
  const rows = dev(u)?.spark || [];
  if (!rows.length) return;
  const rect = box.getBoundingClientRect();
  const off = Math.round((e.clientX - rect.left) / rect.width * (SPAN - 1));
  const r = rows.reduce((best, x) => Math.abs(x[0] - off) < Math.abs(best[0] - off) ? x : best, rows[0]);
  const guide = box.querySelector('.guide');
  const gx = (r[0] / (SPAN - 1) * W).toFixed(1);
  guide.setAttribute('x1', gx); guide.setAttribute('x2', gx);
  const day = addDays(START, r[0]);
  tip.show(`<div class="tip-title">${esc(u.name)} · ${fmtDay(day, { weekday: 'short', day: 'numeric', month: 'short' })}</div>` +
    sparkKeys().map(k => tipRow(`var(${SERIES[k]})`, META[k].short, `${glyph(gradeOf(k, r[COL[k]]), 8)} ${fmt(k, r[COL[k]])}`)).join('') +
    (DATA.method_change && day < DATA.method_change ? '<div class="tip-foot">Before the methodology change</div>' : ''), e.clientX, e.clientY);
});
$('#list').addEventListener('pointerleave', () => tip.hide(), true);
$('#list').addEventListener('pointerout', e => { if (e.target.closest('.spark') && !e.relatedTarget?.closest?.('.spark')) tip.hide(); });

// Header facts
const tests = UNIS.reduce((n, u) => n + (u.total_tests || 0), 0);
$('#facts').innerHTML = `<span><b>${UNIS.length}</b> universities</span><span><b>${tests.toLocaleString('en-GB')}</b> tests</span>` +
  `<span>Daily since <b>${fmtDay(DATA.start)}</b></span><span>Latest tests <b>${fmtDay(DATA.end)}</b></span>`;
staleNotice(DATA.end);
methodNote(DATA.method_change);

bindSeg(state, render);
$('#sort').addEventListener('change', e => { state.sort = e.target.value; renderList(); });
$('#search').addEventListener('input', e => { state.q = e.target.value; renderList(); });
document.addEventListener('keydown', e => {
  if (e.key === '/' && !['INPUT', 'SELECT'].includes(document.activeElement.tagName)) { e.preventDefault(); $('#search').focus(); }
  if (e.key === 'Escape' && document.activeElement === $('#search')) { $('#search').value = ''; state.q = ''; renderList(); $('#search').blur(); }
});
render();
</script>
</body>
</html>
"""

COMPARE_TEMPLATE = r"""
<body>
__TOPBAR__

<main class="wrap">
  <section class="page-head">
    <h1>Compare universities</h1>
    <p class="lede">Line up to six homepages. Values are medians over the selected period; the best in each row is marked.</p>
  </section>

  <div class="notice" id="staleNotice" role="status" hidden></div>

  <div class="toolbar">
    <div class="picker" id="picker">
      <div class="combo" id="combo">
        <label class="search field">
          __ICON_SEARCH__
          <input type="text" id="pick" role="combobox" aria-expanded="false" aria-controls="options" aria-autocomplete="list"
                 placeholder="Add a university" aria-label="Add a university" autocomplete="off">
        </label>
        <div class="listbox" id="options" role="listbox" aria-label="Universities" hidden></div>
      </div>
    </div>
  </div>

  <div class="toolbar" id="filters">
    <div class="seg" data-key="device" role="group" aria-label="Device">
      <button data-value="mobile">Mobile</button><button data-value="desktop">Desktop</button>
    </div>
    <div class="seg" data-key="range" role="group" aria-label="Period">
      <button data-value="30">30D</button><button data-value="90">90D</button><button data-value="365">1Y</button><button data-value="all">All</button>
    </div>
    <div class="seg" data-key="smooth" role="group" aria-label="Line smoothing">
      <button data-value="7" title="Each point is the median of the previous 7 days">7-day median</button><button data-value="1">Daily</button>
    </div>
  </div>

  <div id="content"></div>

  <footer class="foot">
    <p>Each line is one university's daily median. Web Vitals charts show Google's "good" and "poor" thresholds as dashed lines.
      Real-user figures come from the Chrome UX Report and don't follow the period filter.
      Change compares the selected period with the one before it. With "7-day median" on, each point is the median of that day and the six before it.</p>
    <p id="methodNote" hidden></p>
  </footer>
</main>

<script src="__CHART_JS__"></script>
<script src="__CHART_ADAPTER__"></script>
<script>
__COMMON__
__CHART_HELPERS__
__STALE__
const DATA = __DATA__;
const UNIS = DATA.universities;
const bySlug = Object.fromEntries(UNIS.map(u => [u.slug, u]));
const params = new URLSearchParams(location.search);
const fromUrl = (params.get('u') || '').split(',').filter(s => bySlug[s]);
const state = {
  sel: [...new Set(fromUrl.length ? fromUrl : storage.get('compare', []).filter(s => bySlug[s]))].slice(0, MAX_COMPARE),
  device: params.get('device') === 'desktop' ? 'desktop' : 'mobile',
  range: ['30', '90', '365', 'all'].includes(params.get('range')) ? params.get('range') : '90',
  metric: FIELDS.includes(params.get('metric')) ? params.get('metric') : 'performance',
  smooth: params.get('smooth') === '1' ? '1' : '7',
};
// Colour follows the university, not its position: keep slots stable as others are removed
const slots = {};
const slotOf = slug => {
  if (!(slug in slots)) { const used = new Set(Object.values(slots)); let s = 1; while (used.has(s)) s++; slots[slug] = s; }
  return slots[slug];
};
state.sel.forEach(slotOf);
const colorOf = slug => css(`--s${slotOf(slug)}`);
const shortName = n => n.replace(/^The /, '').replace(/^University of /, '').replace(/ University( of London)?$/, '').replace(/, University of London$/, '').replace(/ and Political Science$/, '');

const cache = {};
const failed = new Set();
async function load(slug) {
  if (cache[slug]) return cache[slug];
  const res = await fetch(`data/${slug}.json`);
  if (!res.ok) throw new Error(res.status);
  return (cache[slug] = await res.json());
}

function syncUrl() {
  const p = new URLSearchParams();
  if (state.sel.length) p.set('u', state.sel.join(','));
  if (state.device !== 'mobile') p.set('device', state.device);
  if (state.range !== '90') p.set('range', state.range);
  if (state.metric !== 'performance') p.set('metric', state.metric);
  if (state.smooth !== '7') p.set('smooth', state.smooth);
  history.replaceState(null, '', p.toString() ? `?${p}` : location.pathname);
  storage.set('compare', state.sel);
}

// Rows for a university in the selected window; the window ends at the newest test across the selection
function windowEnd() {
  const ends = state.sel.map(s => cache[s]?.daily?.[state.device]?.at(-1)?.[0]).filter(Boolean).sort();
  return ends.at(-1) || DATA.end;
}
function rowsIn(slug, from, to) {
  return (cache[slug]?.daily?.[state.device] || []).filter(r => (!from || r[0] >= from) && r[0] <= to);
}
function periods() {
  const end = windowEnd();
  if (state.range === 'all') return { from: null, to: end, prevFrom: null, prevTo: null };
  const n = Number(state.range);
  const from = addDays(end, -(n - 1));
  return { from, to: end, prevFrom: addDays(from, -n), prevTo: addDays(from, -1) };
}

// ---- Picker ----
const pick = $('#pick'), listbox = $('#options');
let active = -1, matches = [];
function renderChips() {
  $('#picker').querySelectorAll('.chip').forEach(c => c.remove());
  const combo = $('#combo');
  state.sel.forEach(slug => {
    const u = bySlug[slug];
    combo.insertAdjacentHTML('beforebegin', `<span class="chip" data-slug="${esc(slug)}"><span class="dot" style="--c:var(--s${slotOf(slug)})"></span>${esc(u.name)}<button type="button" aria-label="Remove ${esc(u.name)}"><svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg></button></span>`);
  });
  combo.hidden = state.sel.length >= MAX_COMPARE;
  pick.placeholder = state.sel.length ? 'Add another' : 'Add a university';
}
function renderOptions() {
  const q = pick.value.trim().toLowerCase();
  matches = UNIS.filter(u => !q || u.name.toLowerCase().includes(q) || u.domain.includes(q));
  if (active >= matches.length) active = matches.length - 1;
  listbox.innerHTML = matches.length ? matches.map((u, i) => {
    const on = state.sel.includes(u.slug);
    const p = u.current[state.device];
    return `<div class="opt" role="option" id="opt-${i}" data-slug="${esc(u.slug)}" aria-selected="${i === active}" aria-disabled="${on}">
      ${esc(u.name)}${groupTags(u.groups)}<span class="num">${on ? 'Added' : graded('performance', p)}</span></div>`;
  }).join('') : '<div class="opt-empty">No universities match</div>';
  pick.setAttribute('aria-activedescendant', active >= 0 ? `opt-${active}` : '');
  listbox.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: 'nearest' });
}
function openList(open) {
  listbox.hidden = !open; pick.setAttribute('aria-expanded', open);
  if (open) renderOptions();
}
function add(slug) {
  if (!slug || state.sel.includes(slug) || state.sel.length >= MAX_COMPARE) return;
  state.sel.push(slug); slotOf(slug);
  pick.value = ''; active = -1;
  update();
  if (state.sel.length < MAX_COMPARE) { pick.focus(); renderOptions(); } else openList(false);
}
function remove(slug) {
  state.sel = state.sel.filter(s => s !== slug); delete slots[slug];
  update();
}
pick.addEventListener('focus', () => openList(true));
pick.addEventListener('input', () => { active = 0; openList(true); });
pick.addEventListener('keydown', e => {
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault(); if (listbox.hidden) openList(true);
    const step = e.key === 'ArrowDown' ? 1 : -1;
    active = Math.max(0, Math.min(matches.length - 1, active + step)); renderOptions();
  } else if (e.key === 'Enter') {
    e.preventDefault(); const u = matches[active] || (matches.length === 1 && matches[0]); if (u) add(u.slug);
  } else if (e.key === 'Escape') { openList(false); }
  else if (e.key === 'Backspace' && !pick.value && state.sel.length) { remove(state.sel.at(-1)); }
});
listbox.addEventListener('pointerdown', e => { e.preventDefault(); const o = e.target.closest('.opt'); if (o && o.getAttribute('aria-disabled') !== 'true') add(o.dataset.slug); });
document.addEventListener('pointerdown', e => { if (!e.target.closest('#combo')) openList(false); });
$('#picker').addEventListener('click', e => { const b = e.target.closest('.chip button'); if (b) remove(b.closest('.chip').dataset.slug); });

// ---- Content ----
const METRIC_TABS = DISPLAY_KEYS;
let chart;

function emptyState() {
  const top = [...UNIS].sort((a, b) => (b.current[state.device] ?? -1) - (a.current[state.device] ?? -1)).slice(0, 5).map(u => u.slug);
  const improvers = [...UNIS].filter(u => has(u.delta[state.device])).sort((a, b) => b.delta[state.device] - a.delta[state.device]).slice(0, 5).map(u => u.slug);
  const one = state.sel.length === 1;
  $('#content').innerHTML = `<div class="panel"><div class="empty">
      <b>${one ? `Add at least one more university to compare with ${esc(bySlug[state.sel[0]].name)}` : 'Choose universities to compare'}</b>
      Search above, tick rows on the rankings page, or start from a preset.
      <div class="suggest">
        <button class="btn" type="button" data-preset="${top.join(',')}">Top 5 on ${state.device}</button>
        <button class="btn" type="button" data-preset="${improvers.join(',')}">Biggest improvers</button>
        <a class="btn ghost" href="index.html">Browse rankings</a>
      </div></div></div>`;
}
$('#content').addEventListener('click', e => {
  const b = e.target.closest('[data-preset]');
  if (b) { const keep = state.sel.slice(0, 1); state.sel = [...new Set([...keep, ...b.dataset.preset.split(',')])].slice(0, MAX_COMPARE); state.sel.forEach(slotOf); update(); return; }
  const t = e.target.closest('[data-metric]');
  if (t) { state.metric = t.dataset.metric; syncUrl(); renderChart(); syncMetricTabs(); }
  const r = e.target.closest('[data-retry]');
  if (r) { failed.clear(); update(); }
});

function shell() {
  $('#content').innerHTML = `
    <section class="panel" aria-labelledby="chartTitle">
      <div class="panel-head">
        <span class="panel-title" id="chartTitle">Over time</span>
        <div class="seg end" id="metricTabs" role="group" aria-label="Metric">
          ${METRIC_TABS.map(k => `<button type="button" data-metric="${k}" title="${META[k].label}">${META[k].short}</button>`).join('')}
        </div>
      </div>
      <div class="legend" id="cLegend" style="padding: 10px 16px 0"></div>
      <div class="chart-box"><div class="skeleton" id="sk"></div><canvas id="chart" role="img" aria-label="Chart comparing the selected universities over time"></canvas></div>
    </section>
    <section class="panel" aria-labelledby="tableTitle">
      <div class="panel-head"><span class="panel-title" id="tableTitle">Side by side</span><span class="muted end" id="period" style="font-size:var(--t-sm)"></span></div>
      <div class="table-scroll"><table class="compare-table" id="table"></table></div>
    </section>`;
}
function syncMetricTabs() { document.querySelectorAll('#metricTabs button').forEach(b => b.setAttribute('aria-pressed', b.dataset.metric === state.metric)); }

function renderChart() {
  const { from, to } = periods();
  const key = state.metric;
  const narrow = innerWidth < 640;
  const ready = state.sel.filter(s => cache[s]);
  const series = ready.map(slug => ({
    label: shortName(bySlug[slug].name), color: colorOf(slug),
    data: (state.smooth === '7' ? smooth(rowsIn(slug, null, to), 7, DATA.method_change).filter(r => !from || r[0] >= from) : rowsIn(slug, from, to)).filter(r => has(r[COL[key]])).map(r => ({ x: dayDate(r[0]).getTime(), y: r[COL[key]] })),
  }));
  $('#chartTitle').textContent = `${META[key].label} over time`;
  $('#cLegend').innerHTML = ready.map(s => `<span><span class="swatch" style="--c:var(--s${slotOf(s)})"></span>${esc(bySlug[s].name)}</span>`).join('') +
    (META[key].kind === 'score' ? '<span class="note">higher is better</span>' : '<span class="note"><span class="dash"></span>good / poor thresholds · lower is better</span>') +
    (inWindow(DATA.method_change, from, to) ? methodLegend(DATA.method_change) : '');
  if (chart) chart.destroy();
  const vals = series.flatMap(s => s.data.map(p => p.y));
  const yMax = META[key].kind === 'score' ? 100 : Math.max(META[key].poor * 1.1, ...vals);
  chart = lineChart($('#chart'), {
    series, key, yMax,
    endLabels: !narrow && series.length <= 4, rightPad: !narrow && series.length <= 4 ? 120 : 0, methodChange: DATA.method_change,
    tooltipLabel: i => ` ${bySlug[ready[i.datasetIndex]].name}  ${fmt(key, i.parsed.y)}`,
  });
}

function renderTable() {
  const { from: rangeFrom, to, prevFrom, prevTo } = periods();
  const from = methodFloor(DATA.method_change, rangeFrom, to);
  const sel = state.sel;
  const stat = (slug, key, a, b) => median(rowsIn(slug, a, b).map(r => r[COL[key]]));
  const metricRow = (label, key, vals) => {
    const rounded = v => key === 'cumulative_layout_shift' ? +v.toFixed(3) : Math.round(v);
    const ok = vals.filter(has);
    // Only mark a winner when there is one: a row where everyone ties gets no tag
    const best = ok.length > 1 && new Set(ok.map(rounded)).size > 1 ? (lowerIsBetter(key) ? Math.min(...ok) : Math.max(...ok)) : null;
    const cells = vals.map(v => {
      const isBest = has(v) && has(best) && rounded(v) === rounded(best);
      return `<td class="num${isBest ? ' best' : ''}"><span class="cell">${isBest ? '<span class="best-tag">Best</span>' : ''}${graded(key, v, 9)}</span></td>`;
    }).join('');
    return `<tr><td>${label}</td>${cells}</tr>`;
  };
  const group = label => `<tr class="group"><td colspan="${sel.length + 1}">${label}</td></tr>`;
  const rows = [group('Lab tests (Lighthouse)'), ...DISPLAY_KEYS.map(key => metricRow(META[key].label, key, sel.map(s => cache[s] ? stat(s, key, from, to) : null)))];
  const cruxOf = s => bySlug[s].crux?.[state.device];
  const realUsers = [
    group('Real users (Chrome UX Report, latest 28 days)'),
    `<tr><td>Core Web Vitals</td>${sel.map(s => `<td class="num">${cwvBadge(cruxOf(s))}</td>`).join('')}</tr>`,
    ...CRUX_KEYS.map((key, i) => metricRow(META[key].label, key, sel.map(s => cruxOf(s)?.v?.[i] ?? null))),
  ];
  const change = sel.map(s => {
    if (!cache[s] || !prevFrom || spansChange(DATA.method_change, prevFrom, to)) return '<td class="num muted" title="Not comparable across the test-method change">–</td>';
    const now = avg(rowsIn(s, from, to).map(r => r[COL.performance]));
    const before = avg(rowsIn(s, prevFrom, prevTo).map(r => r[COL.performance]));
    return `<td class="num">${deltaHtml(has(now) && has(before) ? now - before : null, { label: 'vs previous period' })}</td>`;
  }).join('');
  const days = sel.map(s => `<td class="num muted">${cache[s] ? rowsIn(s, from, to).length : '–'}</td>`).join('');
  const last = sel.map(s => { const l = cache[s]?.daily?.[state.device]?.at(-1)?.[0]; return `<td class="muted">${l ? fmtDay(l, { day: 'numeric', month: 'short' }) : '–'}</td>`; }).join('');
  $('#table').innerHTML = `<thead><tr><th>Metric</th>${sel.map(s => `<th scope="col"><span class="cell"><span class="swatch" style="--c:var(--s${slotOf(s)})"></span><a href="${esc(s)}.html" style="color:var(--ink);text-decoration:none">${esc(shortName(bySlug[s].name))}</a></span></th>`).join('')}</tr></thead>
    <tbody>${rows.join('')}<tr><td>Performance change</td>${change}</tr><tr><td>Days tested</td>${days}</tr><tr><td>Latest test</td>${last}</tr>${realUsers.join('')}</tbody>`;
  $('#period').textContent = from !== rangeFrom ? `Since the methodology change: ${fmtDay(from)} – ${fmtDay(to)}`
    : state.range === 'all' ? `All tests to ${fmtDay(to)}` : `${fmtDay(from)} – ${fmtDay(to)}`;
}

let ticket = 0;
async function update() {
  syncUrl();
  renderChips();
  if (state.sel.length < 2) { if (chart) { chart.destroy(); chart = null; } emptyState(); return; }
  if (!$('#chart')) shell();
  syncMetricTabs();
  const mine = ++ticket;
  const missing = state.sel.filter(s => !cache[s]);
  if (missing.length) {
    $('#sk').hidden = false;
    const results = await Promise.allSettled(missing.map(load));
    if (mine !== ticket) return;
    results.forEach((r, i) => { if (r.status === 'rejected') failed.add(missing[i]); });
  }
  $('#sk').hidden = true;
  const bad = state.sel.filter(s => failed.has(s));
  $('#staleNotice').hidden = true;
  if (bad.length) {
    const n = $('#staleNotice'); n.hidden = false;
    n.innerHTML = `<span>Couldn't load data for ${esc(bad.map(s => bySlug[s].name).join(', '))}. <button class="btn ghost" data-retry style="height:24px">Try again</button></span>`;
    n.onclick = e => { if (e.target.closest('[data-retry]')) { bad.forEach(s => failed.delete(s)); update(); } };
  } else staleNotice(windowEnd());
  renderChart(); renderTable();
}

methodNote(DATA.method_change);
bindSeg(state, () => update(), $('#filters'));
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => state.sel.length >= 2 && renderChart());
let resizeTimer;
addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => chart && renderChart(), 150); });
update();
</script>
</body>
</html>
"""

DETAIL_TEMPLATE = r"""
<body>
__TOPBAR__

<main class="wrap">
  <section class="page-head head-row">
    <div>
      <h1>__NAME__<span id="groups"></span></h1>
      <p class="facts"><a class="ext" href="__URL__" target="_blank" rel="noopener">__DOMAIN__
        <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 3H3v10h10v-3M9 3h4v4M13 3L7 9"/></svg></a>
        <span id="meta" style="display:contents"></span></p>
    </div>
    <a class="btn" id="compareLink" href="compare.html">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true"><path d="M8 3v10M3 8h10"/></svg>
      Compare with others</a>
  </section>

  <div class="notice" id="staleNotice" role="status" hidden></div>

  <div class="toolbar" id="filters">
    <div class="seg" data-key="device" role="group" aria-label="Device">
      <button data-value="mobile">Mobile</button><button data-value="desktop">Desktop</button>
    </div>
    <div class="seg" data-key="range" role="group" aria-label="Period">
      <button data-value="30">30D</button><button data-value="90">90D</button><button data-value="365">1Y</button><button data-value="all">All</button>
    </div>
    <div class="seg" data-key="smooth" role="group" aria-label="Line smoothing">
      <button data-value="7" title="Each point is the median of the previous 7 days">7-day median</button><button data-value="1">Daily</button>
    </div>
    <span class="muted" id="period" style="font-size:var(--t-sm); margin-left:4px"></span>
  </div>

  <section class="strip" id="scores" aria-label="Lighthouse scores"></section>
  <section class="strip vitals" id="vitals" aria-label="Web Vitals"></section>

  <section class="panel" aria-labelledby="scoresTitle">
    <div class="panel-head"><span class="panel-title" id="scoresTitle">Lighthouse scores over time</span><span class="legend end" id="sLegend"></span></div>
    <div class="chart-box"><canvas id="scoreChart" role="img" aria-label="Lighthouse scores over time"></canvas></div>
  </section>

  <section class="panel" aria-labelledby="vitalsTitle">
    <div class="panel-head"><span class="panel-title" id="vitalsTitle">Web Vitals over time</span>
      <span class="legend end"><span class="note"><span class="dash"></span>good / poor thresholds · lower is better</span></span></div>
    <div class="multiples" id="multiples"></div>
  </section>

  <section class="panel" aria-labelledby="cruxTitle">
    <div class="panel-head"><span class="panel-title" id="cruxTitle">Real users</span><span id="cruxVerdict"></span>
      <span class="muted end" id="cruxMeta" style="font-size:var(--t-sm)"></span></div>
    <div class="strip five flat" id="cruxStrip"></div>
    <div class="multiples" id="cruxCharts"></div>
  </section>

  <section class="panel" aria-labelledby="runsTitle">
    <div class="panel-head"><span class="panel-title" id="runsTitle">Test runs</span><span class="muted end" id="runCount" style="font-size:var(--t-sm)"></span></div>
    <div class="table-scroll">
      <table>
        <thead><tr><th>Date</th><th>Perf.</th><th>A11y</th><th>BP</th><th>SEO</th><th>LCP</th><th>FCP</th><th>TBT</th><th>CLS</th></tr></thead>
        <tbody id="runs"></tbody>
      </table>
    </div>
    <button class="more" id="more" type="button" hidden></button>
  </section>

  <footer class="foot">
    <p>Scores are Google Lighthouse lab results. The figures at the top are medians over the selected period; the change compares it with the period before.
      LCP is when the main content appears, FCP is when anything first appears, TBT is how long the page is unresponsive to input, and CLS is how much the layout jumps.</p>
    <p id="methodNote" hidden></p>
  </footer>
</main>

<script src="__CHART_JS__"></script>
<script src="__CHART_ADAPTER__"></script>
<script>
__COMMON__
__CHART_HELPERS__
__STALE__
const UNI = __DATA__;
const state = { device: 'mobile', range: '90', smooth: '7', limit: 20 };
const PAGE = 20;
const daily = () => UNI.daily[state.device] || [];
const lastDay = () => daily().at(-1)?.[0];

function periods() {
  const end = lastDay();
  if (!end || state.range === 'all') return { from: null, to: end, prevFrom: null, prevTo: null };
  const n = Number(state.range);
  const from = addDays(end, -(n - 1));
  return { from, to: end, prevFrom: addDays(from, -n), prevTo: addDays(from, -1) };
}
const rowsIn = (a, b) => daily().filter(r => (!a || r[0] >= a) && r[0] <= b);

function renderStrips() {
  const { from: rangeFrom, to, prevFrom, prevTo } = periods();
  const from = methodFloor(UNI.method_change, rangeFrom, to);
  const now = rowsIn(from, to), before = prevFrom ? rowsIn(prevFrom, prevTo) : [];
  const cell = key => {
    const v = median(now.map(r => r[COL[key]]));
    const p = median(before.map(r => r[COL[key]]));
    const lower = lowerIsBetter(key);
    const d = has(v) && has(p) && !spansChange(UNI.method_change, prevFrom, to) ? v - p : null;
    const opts = META[key].kind === 'score' ? { label: 'vs previous period' }
      : { lowerBetter: true, label: 'vs previous period', format: x => fmt(key, Math.abs(x)), flatBelow: META[key].good * 0.02 };
    return `<div><div class="strip-label">${META[key].label}</div>
      <div class="strip-value num">${graded(key, v, 11)}</div>
      <div class="strip-sub">${prevFrom ? deltaHtml(d, opts) : ''}<span>${thresholdText(key)}</span></div></div>`;
  };
  $('#scores').innerHTML = SCORE_KEYS.map(cell).join('');
  $('#vitals').innerHTML = VITAL_KEYS.map(cell).join('');
  $('#period').textContent = !to ? '' : from !== rangeFrom ? `Figures since the methodology change (${fmtDay(from)}); charts show the full period`
    : from ? `${fmtDay(from)} – ${fmtDay(to)}` : `All tests to ${fmtDay(to)}`;
}

let charts = [];
function renderCharts() {
  charts.forEach(c => c.destroy()); charts = [];
  const { from, to } = periods();
  const rows = !to ? [] : state.smooth === '7' ? smooth(rowsIn(null, to), 7, UNI.method_change).filter(r => !from || r[0] >= from) : rowsIn(from, to);
  const pts = key => rows.filter(r => has(r[COL[key]])).map(r => ({ x: dayDate(r[0]).getTime(), y: r[COL[key]] }));
  const narrow = innerWidth < 640;
  charts.push(lineChart($('#scoreChart'), {
    key: 'performance', endLabels: !narrow, rightPad: narrow ? 0 : 56, methodChange: UNI.method_change,
    series: SCORE_KEYS.map(k => ({ label: META[k].short, color: css(SERIES[k]), data: pts(k) })),
    tooltipLabel: i => ` ${META[SCORE_KEYS[i.datasetIndex]].label}  ${Math.round(i.parsed.y)}`,
  }));
  $('#sLegend').innerHTML = SCORE_KEYS.map(k => `<span><span class="swatch" style="--c:var(${SERIES[k]})"></span>${META[k].label}</span>`).join('') +
    (inWindow(UNI.method_change, from, to) ? methodLegend(UNI.method_change) : '');
  $('#multiples').innerHTML = VITAL_KEYS.map(k => `<div><div class="mult-head"><span class="swatch" style="--c:var(${SERIES[k]})"></span><b>${META[k].label}</b><span>${META[k].short} · ${thresholdText(k)}</span></div>
    <div class="chart-box sm"><canvas id="c-${k}" role="img" aria-label="${META[k].label} over time"></canvas></div></div>`).join('');
  VITAL_KEYS.forEach(k => {
    const data = pts(k);
    const yMax = Math.max(META[k].poor * 1.1, ...data.map(p => p.y));
    charts.push(lineChart($(`#c-${k}`), { key: k, yMax, methodChange: UNI.method_change, series: [{ label: META[k].short, color: css(SERIES[k]), data }] }));
  });
  renderCrux();
}

// Real-user data is weekly (each point covers the 28 days before it) and ignores the period filter
const CRUX_CHART_KEYS = ['largest_contentful_paint', 'interaction_to_next_paint', 'cumulative_layout_shift', 'experimental_time_to_first_byte'];
function renderCrux() {
  const entry = UNI.crux?.[state.device];
  const rows = entry?.rows || [];
  if (!rows.length) {
    $('#cruxVerdict').innerHTML = ''; $('#cruxMeta').textContent = ''; $('#cruxCharts').innerHTML = '';
    $('#cruxStrip').innerHTML = `<div class="empty" style="grid-column: 1 / -1">Chrome doesn't have enough real-user data for this site on ${state.device}.</div>`;
    return;
  }
  const last = rows.at(-1);
  const latest = { day: last[0], v: last.slice(1), scope: entry.scope };
  $('#cruxVerdict').innerHTML = `<span class="muted" style="font-size:var(--t-sm)">Core Web Vitals</span> ${cwvBadge(latest)}`;
  $('#cruxMeta').textContent = `28 days to ${fmtDay(latest.day)} · ${entry.scope === 'origin' ? 'whole site (homepage has too little traffic)' : 'homepage'} · weekly since ${fmtDay(rows[0][0])}`;
  $('#cruxStrip').innerHTML = CRUX_KEYS.map((key, i) => `<div><div class="strip-label">${META[key].label}</div>
    <div class="strip-value num">${graded(key, latest.v[i], 11)}</div>
    <div class="strip-sub"><span>${META[key].short} · ${thresholdText(key)}</span></div></div>`).join('');
  $('#cruxCharts').innerHTML = CRUX_CHART_KEYS.map(k => `<div><div class="mult-head"><span class="swatch" style="--c:var(${SERIES[k]})"></span><b>${META[k].label}</b><span>${META[k].short} · 75th percentile</span></div>
    <div class="chart-box sm"><canvas id="cx-${k}" role="img" aria-label="Real-user ${META[k].label} over time"></canvas></div></div>`).join('');
  CRUX_CHART_KEYS.forEach(k => {
    const i = CRUX_KEYS.indexOf(k);
    const data = rows.filter(r => has(r[i + 1])).map(r => ({ x: dayDate(r[0]).getTime(), y: r[i + 1] }));
    const yMax = Math.max(META[k].poor * 1.1, ...data.map(p => p.y));
    charts.push(lineChart($(`#cx-${k}`), { key: k, yMax, gapDays: 10, series: [{ label: META[k].short, color: css(SERIES[k]), data }] }));
  });
}

function renderRuns() {
  const { from, to } = periods();
  const all = UNI.runs.filter(r => r[1] === state.device && (!from || r[0].slice(0, 10) >= from) && (!to || r[0].slice(0, 10) <= to)).reverse();
  const shown = all.slice(0, state.limit);
  $('#runCount').textContent = all.length ? `${all.length.toLocaleString('en-GB')} on ${state.device}` : '';
  $('#runs').innerHTML = shown.length ? shown.map(r => `<tr>
      <td>${new Date(r[0]).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</td>
      ${FIELDS.slice(0, 4).map((k, i) => `<td class="num"><span class="cell">${graded(k, r[i + 2], 8)}</span></td>`).join('')}
      ${['largest_contentful_paint', 'first_contentful_paint', 'total_blocking_time', 'cumulative_layout_shift'].map(k => `<td class="num">${fmt(k, r[2 + FIELDS.indexOf(k)])}</td>`).join('')}
    </tr>`).join('')
    : `<tr><td colspan="9" class="empty">No ${state.device} tests in this period</td></tr>`;
  const left = all.length - shown.length;
  $('#more').hidden = left <= 0;
  $('#more').textContent = `Show ${Math.min(left, PAGE * 5)} more`;
}

function render() { renderStrips(); renderCharts(); renderRuns(); }

const first = [UNI.daily.mobile?.[0]?.[0], UNI.daily.desktop?.[0]?.[0]].filter(Boolean).sort()[0];
const last = [UNI.daily.mobile?.at(-1)?.[0], UNI.daily.desktop?.at(-1)?.[0]].filter(Boolean).sort().at(-1);
$('#meta').innerHTML = `<span><b>${UNI.total_tests.toLocaleString('en-GB')}</b> tests</span>` +
  (first ? `<span>Daily since <b>${fmtDay(first)}</b></span><span>Latest test <b>${fmtDay(last)}</b></span>` : '');
staleNotice(last);
methodNote(UNI.method_change);
$('#groups').innerHTML = groupTags(UNI.groups);
// Carry this university into the compare page, alongside anything already selected
const carry = [UNI.slug, ...storage.get('compare', []).filter(s => s !== UNI.slug)].slice(0, MAX_COMPARE);
$('#compareLink').href = `compare.html?u=${carry.join(',')}`;

bindSeg(state, key => { if (key === 'smooth') return renderCharts(); state.limit = PAGE; render(); }, $('#filters'));
$('#more').addEventListener('click', () => { state.limit += PAGE * 5; renderRuns(); });
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', renderCharts);
let resizeTimer;
addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(renderCharts, 150); });
render();
</script>
</body>
</html>
"""


class UniversityDashboard:
    def __init__(self, results_dir: Path = Path("results"), docs_dir: Path = Path("docs")):
        self.results_dir = results_dir
        self.docs_dir = docs_dir
        self.data_dir = docs_dir / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.method_change: Optional[str] = None

        # Load configuration
        self.config = self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from config.json"""
        try:
            with open("config.json", 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning("config.json not found, using defaults")
            return {"display_settings": {"hidden_universities": []}}

    @staticmethod
    def daily_medians(results: List[Dict[str, Any]]) -> Dict[str, List[list]]:
        """Collapse raw runs into one row per device per day: [day, *FIELDS] (medians)"""
        groups = {device: defaultdict(lambda: [[] for _ in FIELDS]) for device in DEVICES}
        for result in results:
            device, ts = result.get('device'), result.get('timestamp')
            if device not in groups or not ts:
                continue
            day = groups[device][ts[:10]]
            for i, field in enumerate(FIELDS):
                value = field_value(result, field)
                if value is not None:
                    day[i].append(value)
        return {
            device: [[day] + [round_field(f, median(v)) if v else None for f, v in zip(FIELDS, values)]
                     for day, values in sorted(days.items())]
            for device, days in groups.items()
        }

    @staticmethod
    def rolling_median(rows: List[list], days: int = SMOOTH_DAYS, floor: Optional[str] = None) -> List[list]:
        """Each daily row replaced by the median of the trailing `days` days, never reaching back past `floor`"""
        dates = [date.fromisoformat(r[0]) for r in rows]
        floor_day = date.fromisoformat(floor) if floor else None
        smoothed, lo = [], 0
        for hi, day in enumerate(dates):
            while dates[lo] <= day - timedelta(days=days) or (floor_day and day >= floor_day > dates[lo]):
                lo += 1
            window = rows[lo:hi + 1]
            smoothed.append([rows[hi][0]] + [
                round_field(f, median(vals)) if (vals := [r[i + 1] for r in window if r[i + 1] is not None]) else None
                for i, f in enumerate(FIELDS)])
        return smoothed

    @staticmethod
    def summarise(rows: List[list], spark_start: date, method_change: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Current medians, 30-day performance change and the sparkline window for one device"""
        if not rows:
            return None
        last = date.fromisoformat(rows[-1][0])
        recent = [r for r in rows if date.fromisoformat(r[0]) > last - timedelta(days=CURRENT_DAYS)]
        current = [round_field(f, median(vals)) if (vals := [r[i + 1] for r in recent if r[i + 1] is not None]) else None
                   for i, f in enumerate(FIELDS)]

        def perf_between(newest: date, days: int) -> List[float]:
            return [r[1] for r in rows if r[1] is not None
                    and newest - timedelta(days=days) < date.fromisoformat(r[0]) <= newest]

        latest_window = perf_between(last, TREND_DAYS)
        previous_window = perf_between(last - timedelta(days=TREND_DAYS), TREND_DAYS)
        delta = None
        # A comparison that straddles the test-method change would measure the method, not the site
        straddles = method_change and last - timedelta(days=2 * TREND_DAYS) < date.fromisoformat(method_change) <= last
        if not straddles and len(latest_window) >= TREND_MIN_DAYS and len(previous_window) >= TREND_MIN_DAYS:
            delta = round(mean(latest_window) - mean(previous_window), 1)

        spark = [[(date.fromisoformat(r[0]) - spark_start).days] + r[1:]
                 for r in UniversityDashboard.rolling_median(rows, floor=method_change) if date.fromisoformat(r[0]) >= spark_start]
        return {'last': rows[-1][0], 'current': current, 'delta': delta, 'spark': spark}

    def load_crux(self, slug: str) -> Dict[str, Any]:
        """Real-user history written by crux.py: {device: {scope, rows}}"""
        path = self.results_dir / CRUX_DIR.name / f"{slug}.json"
        if not path.exists():
            return {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading CrUX data for {slug}: {e}")
            return {}

    @staticmethod
    def crux_latest(crux: Dict[str, Any]) -> Dict[str, Any]:
        """Latest real-user period per device, for the rankings and compare pages"""
        return {device: {'day': entry['rows'][-1][0], 'v': entry['rows'][-1][1:], 'scope': entry['scope']}
                for device, entry in crux.items() if entry.get('rows')}

    @staticmethod
    def find_method_change(universities: List[Dict[str, Any]]) -> Optional[str]:
        """First day of the corrected test method. Only runs from the fixed runner record a form factor."""
        days = [r['timestamp'][:10] for u in universities for r in u['results']
                if r.get('form_factor')]
        return min(days) if days else None

    def load_university_data(self) -> List[Dict[str, Any]]:
        """Load results for the universities in the configured site list (config.json "sites_file")"""
        universities = []
        hidden = self.config.get('display_settings', {}).get('hidden_universities', [])
        sites_file = self.config.get('sites_file', 'universities_top50.json')
        with open(sites_file, 'r', encoding='utf-8') as f:
            sites = json.load(f)

        for site in sites:
            # Skip hidden universities
            if site['name'] in hidden:
                continue

            slug = results_store.slugify(site['name'])
            try:
                results = [r for r in results_store.read_results(slug, self.results_dir) if r.get('timestamp')]
            except Exception as e:
                logger.error(f"Error loading {slug}.jsonl: {e}")
                continue
            if not results:
                logger.warning(f"No results yet for {site['name']}")
                continue

            results.sort(key=lambda r: r['timestamp'])
            url = site.get('url') or ''
            universities.append({
                'name': site['name'],
                'slug': slug,
                'groups': site.get('groups', []),
                'crux': self.load_crux(slug),
                'url': url,
                'domain': urlparse(url).netloc.removeprefix('www.') or url,
                'total_tests': len(results),
                'results': results,
                'daily': self.daily_medians(results),
            })

        return sorted(universities, key=lambda u: u['slug'])

    def create_stylesheet(self):
        with open(self.docs_dir / "styles.css", 'w', encoding='utf-8') as f:
            f.write(STYLES.lstrip())

    @staticmethod
    def fill(template: str, **values: str) -> str:
        for key, value in values.items():
            template = template.replace(f'__{key}__', value)
        return template

    def create_main_dashboard(self, universities: List[Dict[str, Any]], start: str, end: str):
        """Create the rankings page. Embeds 90 days of daily medians; full history lives in docs/data/."""
        spark_start = date.fromisoformat(end) - timedelta(days=SPARK_DAYS - 1)
        summaries = [{
            'name': u['name'],
            'slug': u['slug'],
            'domain': u['domain'],
            'groups': u['groups'],
            'crux': self.crux_latest(u['crux']),
            'total_tests': u['total_tests'],
            'highlight': u['name'] in self.config.get('display_settings', {}).get('highlight_universities', []),
            'devices': {device: self.summarise(u['daily'][device], spark_start, self.method_change) for device in DEVICES},
        } for u in universities]
        data = {'start': start, 'end': end, 'spark_days': SPARK_DAYS, 'method_change': self.method_change,
                'universities': summaries}

        html_content = page_head(
            "University Web Rankings",
            "Daily Google Lighthouse rankings of UK university homepages, with Web Vitals trends.",
        ) + self.fill(INDEX_TEMPLATE, TOPBAR=topbar('index'), ICON_SEARCH=ICON_SEARCH,
                      COMMON=COMMON_JS, STALE=STALE_NOTICE, DATA=to_script_json(data))

        with open(self.docs_dir / "index.html", 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"Created main dashboard with {len(universities)} universities")
        return summaries

    def create_compare_page(self, summaries: List[Dict[str, Any]], end: str):
        """Create the compare page; it fetches docs/data/<slug>.json for the chosen universities"""
        unis = [{
            'name': s['name'],
            'slug': s['slug'],
            'domain': s['domain'],
            'groups': s['groups'],
            'crux': s['crux'],
            'current': {d: (s['devices'][d] or {}).get('current', [None])[0] for d in DEVICES},
            'delta': {d: (s['devices'][d] or {}).get('delta') for d in DEVICES},
        } for s in summaries]

        html_content = page_head(
            "Compare · University Web Rankings",
            "Compare Lighthouse scores and Web Vitals for UK university homepages side by side.",
        ) + self.fill(COMPARE_TEMPLATE, TOPBAR=topbar('compare'), ICON_SEARCH=ICON_SEARCH,
                      CHART_JS=CHART_JS, CHART_ADAPTER=CHART_ADAPTER, COMMON=COMMON_JS,
                      CHART_HELPERS=CHART_HELPERS_JS, STALE=STALE_NOTICE,
                      DATA=to_script_json({'end': end, 'method_change': self.method_change, 'universities': unis}))

        with open(self.docs_dir / "compare.html", 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info("Created compare page")

    def create_data_file(self, university: Dict[str, Any]):
        data = {k: university[k] for k in ('name', 'slug', 'domain', 'url', 'total_tests', 'daily')}
        with open(self.data_dir / f"{university['slug']}.json", 'w', encoding='utf-8') as f:
            f.write(json.dumps(data, separators=(',', ':')))

    def create_detail_page(self, university: Dict[str, Any]):
        """Create a detail page for a specific university"""
        runs = [[r['timestamp'], r.get('device')] + [round_field(f, field_value(r, f)) for f in FIELDS]
                for r in university['results']]
        data = {k: university[k] for k in ('name', 'slug', 'groups', 'total_tests', 'daily', 'crux')}
        data['runs'] = runs
        data['method_change'] = self.method_change

        html_content = page_head(
            f"{university['name']} · University Web Rankings",
            f"Daily Lighthouse scores and Web Vitals for the {university['name']} homepage.",
        ) + self.fill(DETAIL_TEMPLATE,
                      TOPBAR=topbar('detail', html.escape(university['domain'])),
                      NAME=html.escape(university['name']),
                      URL=html.escape(university['url']),
                      DOMAIN=html.escape(university['domain']),
                      CHART_JS=CHART_JS, CHART_ADAPTER=CHART_ADAPTER, COMMON=COMMON_JS,
                      CHART_HELPERS=CHART_HELPERS_JS, STALE=STALE_NOTICE,
                      DATA=to_script_json(data))

        with open(self.docs_dir / f"{university['slug']}.html", 'w', encoding='utf-8') as f:
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

        days = [rows[i][0] for u in universities for rows in u['daily'].values() if rows for i in (0, -1)]
        start, end = min(days), max(days)
        self.method_change = self.find_method_change(universities)
        if self.method_change:
            logger.info(f"Test method changed on {self.method_change}")

        self.create_stylesheet()
        summaries = self.create_main_dashboard(universities, start, end)  # needs self.method_change
        self.create_compare_page(summaries, end)

        # Create detail pages and history files for each university
        for university in universities:
            self.create_detail_page(university)
            self.create_data_file(university)

        logger.info(f"Dashboard complete with {len(universities)} universities")


def main():
    dashboard = UniversityDashboard()
    dashboard.create_dashboard()


if __name__ == "__main__":
    main()

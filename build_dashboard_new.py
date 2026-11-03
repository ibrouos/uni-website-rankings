#!/usr/bin/env python3
"""
Dashboard Builder
Builds the rankings list (docs/index.html) and a detail page per university
"""

import html
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from statistics import mean
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SCORE_KEYS = ('performance', 'accessibility', 'best_practices', 'seo')
METRIC_KEYS = ('first_contentful_paint', 'largest_contentful_paint', 'total_blocking_time',
               'cumulative_layout_shift', 'speed_index')

CHART_JS = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"
CHART_ADAPTER = "https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"


def parse_timestamp(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace('Z', '').split('+')[0])


def to_script_json(data: Any) -> str:
    """Serialise data for embedding inside a <script> tag"""
    return json.dumps(data, separators=(',', ':')).replace('</', '<\\/')


# Shared stylesheet, written to docs/styles.css
STYLES = r"""
:root {
  --bg: #fbfbfc; --panel: #ffffff; --panel-2: #f6f6f8; --hover: #f8f8fa; --seg-active: #ffffff;
  --border: #e8e8ec; --border-strong: #dadae0;
  --text: #18181b; --text-2: #5f6170; --text-3: #8e909c;
  --accent: #5e6ad2; --accent-soft: rgba(94, 106, 210, .14);
  --good: #26a269; --avg: #c58712; --poor: #d93f3f; --track: #ededf1;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0e0f11; --panel: #141518; --panel-2: #191a1e; --hover: #18191d; --seg-active: #2a2b31;
    --border: #232429; --border-strong: #303238;
    --text: #ececef; --text-2: #a1a3ad; --text-3: #6c6f79;
    --accent: #7d87f2; --accent-soft: rgba(125, 135, 242, .18);
    --good: #4cb782; --avg: #e0a339; --poor: #ec6a5e; --track: #26272c;
    color-scheme: dark;
  }
}

* { box-sizing: border-box; margin: 0; padding: 0; }
html { -webkit-text-size-adjust: 100%; }
body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 14px; line-height: 1.5;
  background: var(--bg); color: var(--text);
  -webkit-font-smoothing: antialiased;
}
a { color: inherit; text-decoration: none; }
button { font: inherit; }
.num { font-variant-numeric: tabular-nums; }
.muted { color: var(--text-3); }
.wrap { max-width: 1040px; margin: 0 auto; padding: 0 24px; }

/* Top bar */
.topbar {
  position: sticky; top: 0; z-index: 10;
  background: color-mix(in srgb, var(--bg) 85%, transparent);
  backdrop-filter: saturate(180%) blur(12px);
  border-bottom: 1px solid var(--border);
}
.topbar .wrap { height: 52px; display: flex; align-items: center; gap: 10px; min-width: 0; }
.brand { display: flex; align-items: center; gap: 10px; font-weight: 600; letter-spacing: -.01em; white-space: nowrap; }
.brand-mark {
  width: 22px; height: 22px; border-radius: 6px; color: #fff;
  background: linear-gradient(135deg, var(--accent), #a06cf0);
  display: grid; place-items: center;
}
.crumb-sep { color: var(--text-3); }
.crumb { color: var(--text-2); font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.topbar-meta { margin-left: auto; color: var(--text-3); font-size: 12.5px; white-space: nowrap; }

/* Page header */
.page-head { padding: 40px 0 24px; }
.page-head h1 { font-size: 24px; font-weight: 600; letter-spacing: -.022em; line-height: 1.25; }
.page-head p { color: var(--text-2); margin-top: 6px; max-width: 62ch; }
.ext { display: inline-flex; align-items: center; gap: 4px; color: var(--text-2); }
.ext:hover { color: var(--text); }

/* Stat tiles */
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 28px; }
.stat { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }
.stat-label { font-size: 12.5px; color: var(--text-3); }
.stat-value { font-size: 22px; font-weight: 600; letter-spacing: -.02em; margin-top: 2px; }
.stat-sub { font-size: 12.5px; color: var(--text-3); font-weight: 400; letter-spacing: 0; margin-left: 4px; }
.stat .bar { max-width: none; margin-top: 10px; }

/* Toolbar and controls */
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 12px; }
.toolbar .spacer { flex: 1; }
input, select {
  font: inherit; font-size: 13px; color: var(--text);
  background: var(--panel); border: 1px solid var(--border); border-radius: 8px;
  outline: none; transition: border-color .15s, box-shadow .15s;
}
input:focus, select:focus, .seg button:focus-visible, a.row:focus-visible {
  border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); outline: none;
}
.search { position: relative; flex: 1 1 220px; max-width: 320px; }
.search svg { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: var(--text-3); pointer-events: none; }
.search input { width: 100%; height: 32px; padding: 0 32px; }
.search input::placeholder { color: var(--text-3); }
.kbd {
  position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
  font-size: 11px; line-height: 16px; padding: 0 5px; color: var(--text-3);
  border: 1px solid var(--border-strong); border-radius: 4px;
}
select {
  height: 32px; padding: 0 28px 0 10px; cursor: pointer; appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 16 16' fill='none' stroke='%238e909c' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 6l4 4 4-4'/%3E%3C/svg%3E");
  background-repeat: no-repeat; background-position: right 10px center;
}
.seg { display: inline-flex; padding: 2px; gap: 2px; background: var(--panel-2); border: 1px solid var(--border); border-radius: 8px; }
.seg button {
  height: 26px; padding: 0 10px; font-size: 13px; font-weight: 500;
  border: 0; border-radius: 6px; background: transparent; color: var(--text-2);
  cursor: pointer; transition: color .15s, background .15s;
}
.seg button:hover { color: var(--text); }
.seg button[aria-pressed="true"] { background: var(--seg-active); color: var(--text); box-shadow: 0 1px 2px rgba(0,0,0,.08), 0 0 0 1px var(--border); }

/* Score marks */
.g { --c: var(--good); } .a { --c: var(--avg); } .p { --c: var(--poor); }
.dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: var(--c, var(--text-3)); margin-right: 7px; vertical-align: 1px; }
.bar { display: block; flex: 1; max-width: 88px; height: 4px; border-radius: 2px; background: var(--track); overflow: hidden; }
.bar i { display: block; height: 100%; border-radius: 2px; background: var(--c); }

/* Rankings list */
.list { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
.row {
  display: grid; align-items: center; gap: 12px; padding: 0 16px;
  grid-template-columns: 28px minmax(0, 1fr) 150px 64px 64px 64px 24px;
  min-height: 54px; border-top: 1px solid var(--border);
}
.row:first-child { border-top: 0; }
.list-head { min-height: 36px; font-size: 12px; font-weight: 500; color: var(--text-3); background: var(--panel-2); }
.list-head .r, .score { text-align: right; }
a.row { transition: background .1s; }
a.row:hover { background: var(--hover); }
.rank { color: var(--text-3); font-size: 12.5px; }
.name { min-width: 0; padding: 8px 0; }
.name b { display: block; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.name span { display: block; font-size: 12.5px; color: var(--text-3); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.stale { color: var(--avg) !important; display: inline !important; }
.perf { display: flex; align-items: center; justify-content: flex-end; gap: 10px; }
.perf .score { min-width: 24px; font-weight: 500; }
.trend { display: grid; place-items: center; color: var(--text-3); }
.trend.up { color: var(--good); } .trend.down { color: var(--poor); }
.empty { padding: 48px 16px; text-align: center; color: var(--text-3); }

/* Detail page */
.tiles { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.vitals { display: grid; grid-template-columns: repeat(4, 1fr); margin-top: 12px; background: var(--panel); border: 1px solid var(--border); border-radius: 10px; }
.vital { padding: 12px 16px; border-left: 1px solid var(--border); }
.vital:first-child { border-left: 0; }
.vital-value { font-size: 15px; font-weight: 500; margin-top: 2px; }
.panel { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; margin-top: 24px; overflow: hidden; }
.panel-head { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; padding: 10px 12px 10px 16px; border-bottom: 1px solid var(--border); }
.panel-title { font-weight: 600; font-size: 13.5px; }
.panel-head .seg { margin-left: auto; }
.legend { display: flex; gap: 14px; font-size: 12.5px; color: var(--text-2); }
.legend i { display: inline-block; width: 12px; height: 2px; border-radius: 1px; margin-right: 6px; vertical-align: 3px; }
.chart-box { position: relative; height: 280px; padding: 16px 12px 8px 8px; }
.table-scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { font-size: 12px; font-weight: 500; color: var(--text-3); text-align: right; padding: 8px 16px; background: var(--panel-2); border-bottom: 1px solid var(--border); white-space: nowrap; }
td { padding: 9px 16px; text-align: right; border-top: 1px solid var(--border); white-space: nowrap; }
th:first-child, td:first-child { text-align: left; }
tbody tr:first-child td { border-top: 0; }
tbody tr:hover td { background: var(--hover); }
.more { display: block; width: 100%; height: 40px; border: 0; border-top: 1px solid var(--border); background: transparent; color: var(--text-2); font-size: 13px; cursor: pointer; }
.more:hover { color: var(--text); background: var(--hover); }

.foot { padding: 28px 0 48px; color: var(--text-3); font-size: 12.5px; max-width: 72ch; }

@media (max-width: 720px) {
  .wrap { padding: 0 16px; }
  .page-head { padding: 28px 0 20px; }
  .row { grid-template-columns: 22px minmax(0, 1fr) 100px 20px; gap: 10px; padding: 0 12px; }
  .hide-sm { display: none; }
  .stats { grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .stat { padding: 12px; }
  .stat-value { font-size: 18px; }
  .stat-sub { display: block; margin-left: 0; }
  .toolbar .spacer { display: none; }
  .toolbar > * { flex: 1 1 auto; }
  .seg button { flex: 1; }
  .search { max-width: none; flex-basis: 100%; }
  .kbd { display: none; }
  .tiles, .vitals { grid-template-columns: repeat(2, 1fr); }
  .vital:nth-child(3) { border-left: 0; }
  .vital:nth-child(n+3) { border-top: 1px solid var(--border); }
  .panel-head .seg { margin-left: 0; }
}
"""

ICONS_JS = r"""
const ICONS = {
  up: '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 10l4-4 4 4"/></svg>',
  down: '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6l4 4 4-4"/></svg>',
  stable: '<svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M4.5 8h7"/></svg>'
};
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const has = v => v != null && isFinite(v);
const grade = v => v >= 90 ? 'g' : v >= 50 ? 'a' : 'p';
const fmtDate = ts => new Date(ts).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
const dotScore = v => has(v) ? `<span class="dot ${grade(v)}"></span>${Math.round(v)}` : '<span class="muted">–</span>';
const bar = v => has(v) ? `<span class="bar ${grade(v)}"><i style="width:${Math.max(2, Math.round(v))}%"></i></span>` : '<span class="bar"></span>';

// Segmented controls: <div class="seg" data-key="x"><button data-value="...">
function bindSeg(state, onChange) {
  document.querySelectorAll('.seg[data-key]').forEach(seg => {
    const key = seg.dataset.key;
    const sync = () => seg.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', b.dataset.value === String(state[key])));
    seg.addEventListener('click', e => {
      const btn = e.target.closest('button');
      if (!btn) return;
      state[key] = btn.dataset.value;
      sync();
      onChange();
    });
    sync();
  });
}
"""

BRAND_MARK = ('<span class="brand-mark"><svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" '
              'stroke-width="2.2" stroke-linecap="round"><path d="M3 13V9M8 13V3M13 13V6"/></svg></span>')


def page_head(title: str, extra: str = '') -> str:
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' rx='4' fill='%235e6ad2'/%3E%3Cpath d='M4 12V9M8 12V4M12 12V7' stroke='white' stroke-width='1.8' stroke-linecap='round'/%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap">
<link rel="stylesheet" href="styles.css">
{extra}
</head>'''


INDEX_TEMPLATE = r"""
<body>
<header class="topbar">
  <div class="wrap">
    <a class="brand" href="index.html">__BRAND__ University Web Rankings</a>
    <span class="topbar-meta" id="lastRun"></span>
  </div>
</header>

<main class="wrap">
  <section class="page-head">
    <h1>How fast are UK university websites?</h1>
    <p>Daily Lighthouse tests of the homepages of leading UK universities, ranked by performance.</p>
  </section>

  <section class="stats" id="stats"></section>

  <div class="toolbar">
    <label class="search">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/></svg>
      <input type="search" id="search" placeholder="Search universities" aria-label="Search universities" autocomplete="off">
      <span class="kbd">/</span>
    </label>
    <span class="spacer"></span>
    <div class="seg" data-key="device" role="group" aria-label="Device">
      <button data-value="mobile">Mobile</button><button data-value="desktop">Desktop</button>
    </div>
    <div class="seg" data-key="period" role="group" aria-label="Period">
      <button data-value="week">7 days</button><button data-value="month">30 days</button>
    </div>
    <select id="sort" aria-label="Sort by">
      <option value="performance">Performance</option>
      <option value="accessibility">Accessibility</option>
      <option value="best_practices">Best practices</option>
      <option value="seo">SEO</option>
      <option value="name">Name</option>
    </select>
  </div>

  <div class="list" id="list"></div>

  <p class="foot">Scores are lab results from Google Lighthouse (0–100), averaged over the selected period.
  90+ is good, 50–89 needs improvement. The arrow compares the latest week of runs with the week before.</p>
</main>

<script>
__ICONS__
const UNIS = __DATA__;
const state = { device: 'mobile', period: 'week', sort: 'performance', q: '' };

const scoresOf = u => (u[state.period] || {})[state.device] || {};
const median = xs => { const s = [...xs].sort((a, b) => a - b); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const TREND_LABEL = { up: 'Improving', down: 'Getting worse', stable: 'Steady' };

function renderStats() {
  const perf = UNIS.map(u => scoresOf(u).performance).filter(has);
  const med = perf.length ? median(perf) : null;
  const good = perf.filter(v => v >= 90).length;
  const tests = UNIS.reduce((n, u) => n + (u.total_tests || 0), 0);
  $('#stats').innerHTML = `
    <div class="stat"><div class="stat-label">Median performance</div>
      <div class="stat-value num">${has(med) ? Math.round(med) : '–'}<span class="stat-sub">/ 100</span></div>${bar(med)}</div>
    <div class="stat"><div class="stat-label">Scoring 90 or more</div>
      <div class="stat-value num">${good}<span class="stat-sub">of ${UNIS.length}</span></div></div>
    <div class="stat"><div class="stat-label">Tests run</div>
      <div class="stat-value num">${tests.toLocaleString('en-GB')}</div></div>`;
}

function row(u, i) {
  const s = scoresOf(u);
  const trend = (u.trend || {})[state.device] || 'stable';
  const stale = (Date.now() - new Date(u.last_updated)) / 864e5 > 14;
  return `<a class="row" href="${esc(u.slug)}.html">
    <span class="rank num">${i + 1}</span>
    <span class="name"><b>${esc(u.name)}</b><span>${esc(u.domain)}${stale ? ` · <span class="stale">last tested ${fmtDate(u.last_updated)}</span>` : ''}</span></span>
    <span class="perf">${bar(s.performance)}<span class="score num">${has(s.performance) ? Math.round(s.performance) : '–'}</span></span>
    <span class="score num hide-sm">${dotScore(s.accessibility)}</span>
    <span class="score num hide-sm">${dotScore(s.best_practices)}</span>
    <span class="score num hide-sm">${dotScore(s.seo)}</span>
    <span class="trend ${trend}" title="${TREND_LABEL[trend]}" aria-label="${TREND_LABEL[trend]}">${ICONS[trend]}</span>
  </a>`;
}

function renderList() {
  const q = state.q.trim().toLowerCase();
  const unis = UNIS.filter(u => !q || u.name.toLowerCase().includes(q) || u.domain.includes(q));
  unis.sort((a, b) => {
    if (state.sort === 'name') return a.name.localeCompare(b.name);
    const av = scoresOf(a)[state.sort], bv = scoresOf(b)[state.sort];
    return (has(bv) ? bv : -1) - (has(av) ? av : -1) || a.name.localeCompare(b.name);
  });
  const head = `<div class="row list-head">
    <span>#</span><span>University</span><span class="r">Performance</span>
    <span class="r hide-sm">Access.</span><span class="r hide-sm">Best pr.</span><span class="r hide-sm">SEO</span><span></span>
  </div>`;
  $('#list').innerHTML = head + (unis.length ? unis.map(row).join('') : `<div class="empty">No universities match “${esc(state.q)}”</div>`);
}

function render() { renderStats(); renderList(); }

const latest = UNIS.map(u => u.last_updated).filter(Boolean).sort().pop();
if (latest) $('#lastRun').textContent = `Last run ${fmtDate(latest)}`;

bindSeg(state, render);
$('#sort').addEventListener('change', e => { state.sort = e.target.value; renderList(); });
$('#search').addEventListener('input', e => { state.q = e.target.value; renderList(); });
document.addEventListener('keydown', e => {
  if (e.key === '/' && document.activeElement !== $('#search')) { e.preventDefault(); $('#search').focus(); }
  if (e.key === 'Escape' && document.activeElement === $('#search')) { $('#search').value = ''; state.q = ''; renderList(); $('#search').blur(); }
});
render();
</script>
</body>
</html>
"""

DETAIL_TEMPLATE = r"""
<body>
<header class="topbar">
  <div class="wrap">
    <a class="brand" href="index.html">__BRAND__ <span class="hide-sm">University Web Rankings</span></a>
    <span class="crumb-sep">/</span>
    <span class="crumb">__NAME__</span>
  </div>
</header>

<main class="wrap">
  <section class="page-head">
    <h1>__NAME__</h1>
    <p><a class="ext" href="__URL__" target="_blank" rel="noopener">__DOMAIN__
      <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3H3v10h10v-3M9 3h4v4M13 3L7 9"/></svg></a>
      <span class="muted" id="meta"></span></p>
  </section>

  <div class="toolbar">
    <div class="seg" data-key="device" role="group" aria-label="Device">
      <button data-value="mobile">Mobile</button><button data-value="desktop">Desktop</button>
    </div>
    <div class="seg" data-key="range" role="group" aria-label="Time range">
      <button data-value="7">7D</button><button data-value="30">30D</button><button data-value="365">1Y</button><button data-value="all">All</button>
    </div>
  </div>

  <section class="tiles" id="tiles"></section>
  <section class="vitals" id="vitals"></section>

  <section class="panel">
    <div class="panel-head">
      <span class="panel-title">Over time</span>
      <span class="legend"><span><i style="background:var(--accent)"></i>Mobile</span><span><i style="background:var(--text-3)"></i>Desktop</span></span>
      <div class="seg" data-key="metric" role="group" aria-label="Score">
        <button data-value="performance">Perf.</button><button data-value="accessibility">Access.</button><button data-value="best_practices">Best pr.</button><button data-value="seo">SEO</button>
      </div>
    </div>
    <div class="chart-box"><canvas id="chart" aria-label="Score over time"></canvas></div>
  </section>

  <section class="panel">
    <div class="panel-head"><span class="panel-title">Test runs</span><span class="muted" id="runCount"></span></div>
    <div class="table-scroll">
      <table>
        <thead><tr><th>Date</th><th>Perf.</th><th>Access.</th><th>Best pr.</th><th>SEO</th><th>LCP</th><th>TBT</th><th>CLS</th></tr></thead>
        <tbody id="runs"></tbody>
      </table>
    </div>
    <button class="more" id="more" hidden></button>
  </section>

  <p class="foot">Scores are Google Lighthouse lab results. Tiles show the average over the selected range;
  page-load timings are medians. LCP is the time until the main content shows, TBT is time the page is unresponsive,
  CLS is how much the layout jumps around.</p>
</main>

<script>
__ICONS__
const UNI = __DATA__;
const RUNS = UNI.runs.map(r => ({ ...r, date: new Date(r.timestamp) })).sort((a, b) => a.date - b.date);
const state = { device: 'mobile', range: '30', metric: 'performance', limit: 20 };
const PAGE = 20;

const SCORES = [['performance', 'Performance'], ['accessibility', 'Accessibility'], ['best_practices', 'Best practices'], ['seo', 'SEO']];
// [key, label, good-at-or-below, poor-above, formatter]
const fmtMs = v => v < 1000 ? `${Math.round(v)} ms` : `${(v / 1000).toFixed(1)} s`;
const VITALS = [
  ['largest_contentful_paint', 'Largest contentful paint', 2500, 4000, fmtMs],
  ['first_contentful_paint', 'First contentful paint', 1800, 3000, fmtMs],
  ['total_blocking_time', 'Total blocking time', 200, 600, fmtMs],
  ['cumulative_layout_shift', 'Cumulative layout shift', 0.1, 0.25, v => v.toFixed(3)],
];

const avg = xs => xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;
const median = xs => { if (!xs.length) return null; const s = [...xs].sort((a, b) => a - b); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

function inRange(runs) {
  if (state.range === 'all') return runs;
  const cutoff = Date.now() - Number(state.range) * 864e5;
  return runs.filter(r => r.date >= cutoff);
}

function renderTiles(runs) {
  $('#tiles').innerHTML = SCORES.map(([key, label]) => {
    const v = avg(runs.map(r => r.scores?.[key]).filter(has));
    return `<div class="stat"><div class="stat-label">${label}</div>
      <div class="stat-value num">${has(v) ? Math.round(v) : '–'}</div>${bar(v)}</div>`;
  }).join('');
  $('#vitals').innerHTML = VITALS.map(([key, label, good, poor, fmt]) => {
    const v = median(runs.map(r => r.metrics?.[key]).filter(has));
    const g = !has(v) ? '' : v <= good ? 'g' : v <= poor ? 'a' : 'p';
    return `<div class="vital"><div class="stat-label">${label}</div>
      <div class="vital-value num">${has(v) ? `<span class="dot ${g}"></span>${fmt(v)}` : '<span class="muted">–</span>'}</div></div>`;
  }).join('');
}

let chart;
function renderChart(runs) {
  const series = device => runs
    .filter(r => r.device === device && has(r.scores?.[state.metric]))
    .map(r => ({ x: r.date, y: r.scores[state.metric] }));
  const line = (device, color) => ({
    label: device[0].toUpperCase() + device.slice(1), data: series(device),
    borderColor: color, backgroundColor: color,
    borderWidth: device === state.device ? 2 : 1.25,
    pointRadius: 0, pointHoverRadius: 3, tension: 0.3,
  });
  const grid = css('--border'), muted = css('--text-3');
  if (chart) chart.destroy();
  chart = new Chart($('#chart'), {
    type: 'line',
    data: { datasets: [line('mobile', css('--accent')), line('desktop', muted)] },
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: { mode: 'nearest', axis: 'x', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: css('--panel'), borderColor: css('--border-strong'), borderWidth: 1,
          titleColor: css('--text'), bodyColor: css('--text-2'), padding: 10, cornerRadius: 8,
          boxWidth: 8, boxHeight: 8, usePointStyle: true,
          callbacks: { title: items => fmtDate(items[0].parsed.x), label: i => ` ${i.dataset.label}: ${Math.round(i.parsed.y)}` },
        },
      },
      scales: {
        x: { type: 'time', grid: { display: false }, border: { color: grid }, ticks: { color: muted, maxTicksLimit: 6, maxRotation: 0 } },
        y: { min: 0, max: 100, grid: { color: grid }, border: { display: false }, ticks: { color: muted, stepSize: 25 } },
      },
    },
  });
}

function renderRuns(runs) {
  const rows = runs.filter(r => r.device === state.device).reverse();
  const shown = rows.slice(0, state.limit);
  const m = (r, k, f) => has(r.metrics?.[k]) ? f(r.metrics[k]) : '–';
  $('#runCount').textContent = rows.length ? `${rows.length} on ${state.device}` : '';
  $('#runs').innerHTML = shown.length ? shown.map(r => `<tr>
      <td>${r.date.toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</td>
      ${SCORES.map(([k]) => `<td class="num">${dotScore(r.scores?.[k])}</td>`).join('')}
      <td class="num">${m(r, 'largest_contentful_paint', fmtMs)}</td>
      <td class="num">${m(r, 'total_blocking_time', fmtMs)}</td>
      <td class="num">${m(r, 'cumulative_layout_shift', v => v.toFixed(3))}</td>
    </tr>`).join('')
    : `<tr><td colspan="8" class="empty">No ${state.device} runs in this range${RUNS.length ? ` · last run ${fmtDate(RUNS[RUNS.length - 1].date)}` : ''}</td></tr>`;
  const left = rows.length - shown.length;
  $('#more').hidden = left <= 0;
  $('#more').textContent = `Show ${Math.min(left, PAGE * 5)} more`;
}

function render() {
  const runs = inRange(RUNS);
  renderTiles(runs.filter(r => r.device === state.device));
  renderChart(runs);
  renderRuns(runs);
}

if (RUNS.length) $('#meta').textContent = ` · ${UNI.total_tests.toLocaleString('en-GB')} tests · last tested ${fmtDate(RUNS[RUNS.length - 1].date)}`;
Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
Chart.defaults.font.size = 11.5;
bindSeg(state, () => { state.limit = PAGE; render(); });
$('#more').addEventListener('click', () => { state.limit += PAGE * 5; renderRuns(inRange(RUNS)); });
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', render);
render();
</script>
</body>
</html>
"""


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
            if parse_timestamp(result.get('timestamp', '')) >= cutoff_date
        ]

        # If no results in the time range, use the most recent results instead
        if not recent_results:
            # Sort by timestamp descending and take last 4 results (2 devices * 2 tests)
            sorted_results = sorted(results, key=lambda x: x.get('timestamp', ''), reverse=True)
            recent_results = sorted_results[:min(4, len(sorted_results))]

        def calc_device_averages(device_results):
            scores = {}
            for metric in SCORE_KEYS:
                values = [r['scores'][metric] for r in device_results if metric in r.get('scores', {})]
                if values:
                    scores[metric] = mean(values)
            return scores

        return {
            'mobile': calc_device_averages([r for r in recent_results if r.get('device') == 'mobile']),
            'desktop': calc_device_averages([r for r in recent_results if r.get('device') == 'desktop']),
            'total_tests': len(recent_results)
        }

    def calculate_trend(self, results: List[Dict[str, Any]], device: str, days: int = 7) -> str:
        """Compare mean performance in the latest N days with the N days before (up/down/stable)"""
        runs = [r for r in results if r.get('device') == device and 'performance' in r.get('scores', {})]
        if len(runs) < 2:
            return "stable"

        # Measure from the latest run so a stalled monitor still shows a meaningful trend
        latest = max(parse_timestamp(r['timestamp']) for r in runs)
        window = timedelta(days=days)
        current = [r['scores']['performance'] for r in runs if parse_timestamp(r['timestamp']) > latest - window]
        previous = [r['scores']['performance'] for r in runs
                    if latest - 2 * window < parse_timestamp(r['timestamp']) <= latest - window]

        if not current or not previous:
            return "stable"

        diff = mean(current) - mean(previous)
        if diff > 3:
            return "up"
        elif diff < -3:
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

                results = uni_data.get('results', [])
                url = uni_data.get('url') or ''

                universities.append({
                    'name': uni_data.get('name'),
                    'slug': uni_data.get('slug'),
                    'url': url,
                    'domain': urlparse(url).netloc.removeprefix('www.') or url,
                    'total_tests': uni_data.get('total_tests', 0),
                    'last_updated': uni_data.get('last_updated'),
                    'week_averages': self.calculate_averages(results, 7),
                    'month_averages': self.calculate_averages(results, 30),
                    'trend': {device: self.calculate_trend(results, device) for device in ('mobile', 'desktop')},
                    'results': results
                })

            except Exception as e:
                logger.error(f"Error loading {uni_file.name}: {e}")

        return universities

    def create_stylesheet(self):
        with open(self.docs_dir / "styles.css", 'w') as f:
            f.write(STYLES.lstrip())

    def create_main_dashboard(self, universities: List[Dict[str, Any]]):
        """Create the rankings page. Embeds summaries only; full history lives on the detail pages."""
        summaries = [{
            'name': u['name'],
            'slug': u['slug'],
            'domain': u['domain'],
            'total_tests': u['total_tests'],
            'last_updated': u['last_updated'],
            'trend': u['trend'],
            'week': u['week_averages'],
            'month': u['month_averages'],
        } for u in universities]

        html_content = page_head("University Web Rankings") + (INDEX_TEMPLATE
            .replace('__BRAND__', BRAND_MARK)
            .replace('__ICONS__', ICONS_JS)
            .replace('__DATA__', to_script_json(summaries)))

        with open(self.docs_dir / "index.html", 'w') as f:
            f.write(html_content)

        logger.info(f"Created main dashboard with {len(universities)} universities")

    def create_detail_page(self, university: Dict[str, Any]):
        """Create a detail page for a specific university"""
        runs = [{
            'timestamp': r['timestamp'],
            'device': r.get('device'),
            'scores': r.get('scores', {}),
            'metrics': {k: r.get('metrics', {}).get(k) for k in METRIC_KEYS},
        } for r in university['results'] if r.get('timestamp')]

        data = {'name': university['name'], 'total_tests': university['total_tests'], 'runs': runs}
        scripts = f'<script src="{CHART_JS}"></script>\n<script src="{CHART_ADAPTER}"></script>'

        html_content = page_head(f"{university['name']} · University Web Rankings", scripts) + (DETAIL_TEMPLATE
            .replace('__BRAND__', BRAND_MARK)
            .replace('__NAME__', html.escape(university['name']))
            .replace('__URL__', html.escape(university['url']))
            .replace('__DOMAIN__', html.escape(university['domain']))
            .replace('__ICONS__', ICONS_JS)
            .replace('__DATA__', to_script_json(data)))

        with open(self.docs_dir / f"{university['slug']}.html", 'w') as f:
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

        self.create_stylesheet()
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

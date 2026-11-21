#!/usr/bin/env python3
"""
Zero-dependency Python 3 static site generator for WattWise Payback.
Generates:
  - dist/index.html (ZIP lookup + national overview + state directory)
  - dist/states/<state>/index.html (state hub pages)
  - dist/utility/<slug>/index.html (utility EV & solar payback calculator pages)
  - dist/assets/style.css & dist/assets/calculator.js
  - dist/sitemap.xml & dist/robots.txt
"""

from __future__ import annotations

import collections
import html
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DIST_DIR = ROOT / "dist"
ASSETS_DIR = DIST_DIR / "assets"

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}

STYLE_CSS = """
:root {
  --bg: #0b1020;
  --surface: #131b31;
  --surface-2: #1b2542;
  --text: #eef2ff;
  --muted: #9aa7c7;
  --accent: #38bdf8;
  --accent-2: #22c55e;
  --warn: #f59e0b;
  --danger: #ef4444;
  --border: #263357;
  --radius: 12px;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.container { max-width: 1020px; margin: 0 auto; padding: 0 20px; }
header {
  border-bottom: 1px solid var(--border);
  background: rgba(11, 16, 32, 0.92);
  position: sticky;
  top: 0;
  z-index: 20;
}
.nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 0;
}
.brand { font-weight: 800; font-size: 1.15rem; color: var(--text); letter-spacing: -0.02em; }
.brand span { color: var(--accent-2); }
.nav-links { display: flex; gap: 18px; font-size: 0.92rem; }
.hero { padding: 48px 0 32px; }
.hero h1 { font-size: clamp(1.8rem, 3.8vw, 2.6rem); line-height: 1.18; margin: 0 0 12px; }
.hero p { color: var(--muted); max-width: 680px; margin: 0 0 24px; font-size: 1.05rem; }
.badge {
  display: inline-block;
  font-size: 0.78rem;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(56, 189, 248, 0.14);
  color: var(--accent);
  margin-bottom: 12px;
}
.search-box {
  display: flex;
  gap: 10px;
  max-width: 520px;
  margin-top: 16px;
}
.search-box input {
  flex: 1;
  padding: 13px 16px;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font-size: 1rem;
}
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 12px 20px;
  border-radius: var(--radius);
  border: none;
  background: var(--accent);
  color: #06101f;
  font-weight: 700;
  font-size: 0.96rem;
  cursor: pointer;
}
.btn:hover { opacity: 0.92; text-decoration: none; }
.btn-green { background: var(--accent-2); color: #051b0c; }
.btn-outline {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text);
}
.grid-4 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 14px;
  margin: 24px 0;
}
.grid-3 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
  margin: 20px 0;
}
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
}
.kpi-label { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); }
.kpi-val { font-size: 1.75rem; font-weight: 800; margin: 4px 0; color: var(--text); }
.kpi-sub { font-size: 0.85rem; color: var(--muted); }
.calc-tabs { display: flex; gap: 10px; margin-bottom: 18px; }
.tab-btn {
  padding: 10px 18px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  color: var(--muted);
  font-weight: 700;
  cursor: pointer;
}
.tab-btn.active {
  background: var(--accent);
  color: #06101f;
  border-color: var(--accent);
}
.slider-row { margin-bottom: 16px; }
.slider-row label { display: flex; justify-content: space-between; font-size: 0.92rem; margin-bottom: 6px; }
.slider-row input[type="range"] { width: 100%; accent-color: var(--accent); }
.result-banner {
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.35);
  border-radius: var(--radius);
  padding: 18px;
  margin-top: 16px;
}
.cta-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px 20px;
  margin-top: 18px;
}
.tou-grid {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 6px;
  margin-top: 12px;
}
@media (max-width: 640px) {
  .tou-grid { grid-template-columns: repeat(6, 1fr); }
}
.tou-cell {
  text-align: center;
  padding: 8px 4px;
  border-radius: 6px;
  font-size: 0.78rem;
  font-weight: 600;
}
.tou-off { background: rgba(34, 197, 94, 0.18); color: #86efac; border: 1px solid rgba(34, 197, 94, 0.3); }
.tou-peak { background: rgba(239, 68, 68, 0.22); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.4); }
table { width: 100%; border-collapse: collapse; margin-top: 12px; }
th, td { text-align: left; padding: 12px 10px; border-bottom: 1px solid var(--border); font-size: 0.94rem; }
th { color: var(--muted); font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.04em; }
.zip-results { margin-top: 14px; }
footer {
  border-top: 1px solid var(--border);
  margin-top: 56px;
  padding: 28px 0 44px;
  color: var(--muted);
  font-size: 0.86rem;
}
.hidden { display: none; }
""".strip() + "\n"

CALCULATOR_JS = """
(function () {
  const zipForm = document.getElementById("zip-search-form");
  if (zipForm) {
    let zipMapCache = null;
    let searchIndexCache = null;
    zipForm.addEventListener("submit", async function (e) {
      e.preventDefault();
      const input = document.getElementById("zip-input");
      const out = document.getElementById("zip-results");
      const query = (input.value || "").trim();
      if (!query) {
        out.innerHTML = '<div class="card">Enter a 5-digit ZIP code (e.g., 36467, 94103) or utility/state name (e.g., Alabama, Texas, PG&amp;E).</div>';
        return;
      }
      try {
        if (!zipMapCache) {
          const [zRes, sRes] = await Promise.all([
            fetch("./zip-map.json"),
            fetch("./search-index.json")
          ]);
          zipMapCache = await zRes.json();
          searchIndexCache = await sRes.json();
        }
        let matches = [];
        if (/^\\d{5}$/.test(query)) {
          matches = zipMapCache[query] || [];
        }
        if (matches.length === 0) {
          const qLower = query.toLowerCase();
          matches = (searchIndexCache || []).filter(function (item) {
            return item.name.toLowerCase().includes(qLower) || item.state.toLowerCase() === qLower;
          }).slice(0, 8);
        }
        if (matches.length === 0) {
          out.innerHTML = '<div class="card">No exact match for "' + query + '". Try searching by your electric company name or browse states below.</div>';
          return;
        }
        const links = matches.map(function (m) {
          return '<a class="btn btn-green" href="./utility/' + m.slug + '/index.html">' +
            m.name + ' (' + m.state + ' &bull; ' + (m.rate * 100).toFixed(1) + '&cent;/kWh) &rarr;</a>';
        }).join(" ");
        out.innerHTML = '<div class="card"><strong>Matching utilities for "' + query + '":</strong><div style="margin-top:10px;display:flex;gap:10px;flex-wrap:wrap;">' + links + '</div></div>';
      } catch (err) {
        out.innerHTML = '<div class="card">Browse utilities by state below.</div>';
      }
    });
  }

  const calcRoot = document.getElementById("payback-calculator");
  if (!calcRoot) return;

  const blended = parseFloat(calcRoot.dataset.blended);
  const offPeak = parseFloat(calcRoot.dataset.offpeak);
  const dgFactor = parseFloat(calcRoot.dataset.dgfactor);

  const tabEv = document.getElementById("tab-ev");
  const tabSolar = document.getElementById("tab-solar");
  const panelEv = document.getElementById("panel-ev");
  const panelSolar = document.getElementById("panel-solar");

  function setTab(which) {
    const isEv = which === "ev";
    tabEv.classList.toggle("active", isEv);
    tabSolar.classList.toggle("active", !isEv);
    panelEv.classList.toggle("hidden", !isEv);
    panelSolar.classList.toggle("hidden", isEv);
  }
  tabEv.addEventListener("click", function () { setTab("ev"); });
  tabSolar.addEventListener("click", function () { setTab("solar"); });

  const milesSlider = document.getElementById("ev-miles");
  const gasSlider = document.getElementById("gas-price");
  const mpgSlider = document.getElementById("gas-mpg");

  function updateEv() {
    const miles = parseFloat(milesSlider.value);
    const gasPrice = parseFloat(gasSlider.value);
    const mpg = parseFloat(mpgSlider.value);
    document.getElementById("ev-miles-val").textContent = miles.toLocaleString() + " mi/yr";
    document.getElementById("gas-price-val").textContent = "$" + gasPrice.toFixed(2) + "/gal";
    document.getElementById("gas-mpg-val").textContent = mpg + " MPG";

    const annualKwh = (miles / 100) * 28.0;
    const evStd = annualKwh * blended;
    const evOff = annualKwh * offPeak;
    const gasCost = (miles / mpg) * gasPrice;
    const savings = gasCost - evOff;

    document.getElementById("ev-annual-offpeak").textContent = "$" + Math.round(evOff).toLocaleString() + "/yr";
    document.getElementById("ev-annual-std").textContent = "$" + Math.round(evStd).toLocaleString() + "/yr";
    document.getElementById("ev-annual-savings").textContent =
      (savings >= 0 ? "$" + Math.round(savings).toLocaleString() + "/yr saved" : "-$" + Math.abs(Math.round(savings)).toLocaleString() + "/yr");
  }

  [milesSlider, gasSlider, mpgSlider].forEach(function (el) {
    el.addEventListener("input", updateEv);
  });

  const kwSlider = document.getElementById("solar-kw");
  const costSlider = document.getElementById("solar-cost");
  const sunSlider = document.getElementById("solar-sun");

  function updateSolar() {
    const kw = parseFloat(kwSlider.value);
    const costPerWatt = parseFloat(costSlider.value);
    const sunKwhPerKw = parseFloat(sunSlider.value);
    document.getElementById("solar-kw-val").textContent = kw.toFixed(1) + " kW";
    document.getElementById("solar-cost-val").textContent = "$" + costPerWatt.toFixed(2) + "/W";
    document.getElementById("solar-sun-val").textContent = sunKwhPerKw.toLocaleString() + " kWh/kW/yr";

    const grossCost = kw * 1000 * costPerWatt;
    const annualProd = kw * sunKwhPerKw;
    const annualSavings = annualProd * blended * dgFactor;
    const payback = grossCost / Math.max(annualSavings, 1);
    const net25Yr = (annualSavings * 25) - grossCost;

    document.getElementById("solar-install-cost").textContent = "$" + Math.round(grossCost).toLocaleString();
    document.getElementById("solar-yr-savings").textContent = "$" + Math.round(annualSavings).toLocaleString() + "/yr";
    document.getElementById("solar-payback").textContent = payback.toFixed(1) + " years";
    document.getElementById("solar-25yr").textContent = "$" + Math.round(net25Yr).toLocaleString();
  }

  [kwSlider, costSlider, sunSlider].forEach(function (el) {
    el.addEventListener("input", updateSolar);
  });

  updateEv();
  updateSolar();
})();
""".strip() + "\n"


def esc(val: object) -> str:
    return html.escape(str(val), quote=True)


def render_shell(title: str, description: str, depth: int, body_html: str, config: dict) -> str:
    prefix = "./" if depth == 0 else "../" * depth
    site_name = esc(config["site_name"])
    gsc_token = (config.get("google_site_verification") or "").strip()
    gsc_tag = f'\n  <meta name="google-site-verification" content="{esc(gsc_token)}" />' if gsc_token else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />{gsc_tag}
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}" />
  <link rel="stylesheet" href="{prefix}assets/style.css" />
</head>
<body>
  <header>
    <div class="container nav">
      <a class="brand" href="{prefix}index.html">{site_name}<span>.</span></a>
      <nav class="nav-links">
        <a href="{prefix}index.html">ZIP Lookup</a>
        <a href="{prefix}index.html#states">Browse States</a>
      </nav>
    </div>
  </header>
  <main class="container">
    {body_html}
  </main>
  <footer>
    <div class="container">
      <p>Data sourced from the <a href="https://data.openei.org/submissions/5" target="_blank" rel="noopener">OpenEI Utility Rate Database (URDB)</a>. Estimates are for planning purposes; verify current tariff riders with your utility.</p>
    </div>
  </footer>
  <script src="{prefix}assets/calculator.js"></script>
</body>
</html>
"""


def render_home(utilities: list, states_map: dict, config: dict) -> str:
    avg_rate = sum(u["default_tariff"]["blended_kwh_rate"] for u in utilities) / max(len(utilities), 1)
    avg_offpeak = sum(u["default_tariff"]["off_peak_kwh_rate"] for u in utilities) / max(len(utilities), 1)
    avg_payback = sum(u["precomputed"]["solar_est_payback_years"] for u in utilities) / max(len(utilities), 1)

    state_cards = []
    for st in sorted(states_map.keys()):
        st_utils = states_map[st]
        st_avg = sum(u["default_tariff"]["blended_kwh_rate"] for u in st_utils) / len(st_utils)
        st_name = STATE_NAMES.get(st, st)
        state_cards.append(
            f'<a class="card" href="./states/{st.lower()}/index.html" style="display:block;">'
            f'<div class="kpi-label">{esc(st)} &bull; {len(st_utils)} utilities</div>'
            f'<div style="font-size:1.15rem;font-weight:700;margin:4px 0;color:var(--text);">{esc(st_name)}</div>'
            f'<div class="kpi-sub">Avg {st_avg*100:.1f}&cent;/kWh</div>'
            f'</a>'
        )

    featured_rows = []
    for u in utilities[:10]:
        t = u["default_tariff"]
        p = u["precomputed"]
        featured_rows.append(
            f'<tr>'
            f'<td><a href="./utility/{esc(u["slug"])}/index.html"><strong>{esc(u["utility_name"])}</strong></a></td>'
            f'<td>{esc(u["state"])}</td>'
            f'<td>{t["blended_kwh_rate"]*100:.1f}&cent;/kWh</td>'
            f'<td>{t["off_peak_kwh_rate"]*100:.1f}&cent;/kWh</td>'
            f'<td>${p["ev_cost_per_1000_mi_offpeak"]:.2f}</td>'
            f'<td>{p["solar_est_payback_years"]} yrs</td>'
            f'</tr>'
        )

    body = f"""
    <section class="hero">
      <span class="badge">Auto-Updated from OpenEI URDB</span>
      <h1>Local Electricity Rates, EV Charging &amp; Solar Payback</h1>
      <p>Enter your ZIP code or select your utility to calculate exact off-peak EV home charging costs and rooftop solar payback windows using real tariff data.</p>
      <form id="zip-search-form" class="search-box">
        <input id="zip-input" type="text" maxlength="40" placeholder="Enter ZIP (36467, 94103) or utility/state name" />
        <button class="btn" type="submit">Find My Rate</button>
      </form>
      <div id="zip-results" class="zip-results"></div>
    </section>

    <section class="grid-4">
      <div class="card">
        <div class="kpi-label">Utilities Tracked</div>
        <div class="kpi-val">{len(utilities):,}</div>
        <div class="kpi-sub">Across {len(states_map)} states</div>
      </div>
      <div class="card">
        <div class="kpi-label">Avg Blended Rate</div>
        <div class="kpi-val">{avg_rate*100:.1f}&cent;</div>
        <div class="kpi-sub">Per kWh residential</div>
      </div>
      <div class="card">
        <div class="kpi-label">Avg Off-Peak EV Rate</div>
        <div class="kpi-val">{avg_offpeak*100:.1f}&cent;</div>
        <div class="kpi-sub">Per kWh overnight</div>
      </div>
      <div class="card">
        <div class="kpi-label">Avg Solar Payback</div>
        <div class="kpi-val">{avg_payback:.1f} yrs</div>
        <div class="kpi-sub">7 kW baseline system</div>
      </div>
    </section>

    <section style="margin-top:32px;">
      <h2>Popular Utility Calculators</h2>
      <div class="card" style="overflow-x:auto;">
        <table>
          <thead>
            <tr>
              <th>Utility</th>
              <th>State</th>
              <th>Blended Rate</th>
              <th>Off-Peak EV</th>
              <th>EV / 1,000 mi</th>
              <th>Solar Payback</th>
            </tr>
          </thead>
          <tbody>
            {"".join(featured_rows)}
          </tbody>
        </table>
      </div>
    </section>

    <section id="states" style="margin-top:40px;">
      <h2>Browse by State</h2>
      <div class="grid-4">
        {"".join(state_cards)}
      </div>
    </section>
    """
    return render_shell(
        title=f'{config["site_name"]} — {config["site_tagline"]}',
        description=config["site_tagline"],
        depth=0,
        body_html=body,
        config=config,
    )


def render_state_page(state: str, st_utils: list, config: dict) -> str:
    st_name = STATE_NAMES.get(state, state)
    avg_rate = sum(u["default_tariff"]["blended_kwh_rate"] for u in st_utils) / len(st_utils)
    rows = []
    for u in st_utils:
        t = u["default_tariff"]
        p = u["precomputed"]
        rows.append(
            f'<tr>'
            f'<td><a href="../../utility/{esc(u["slug"])}/index.html"><strong>{esc(u["utility_name"])}</strong></a></td>'
            f'<td>{esc(t["rate_name"])}</td>'
            f'<td>{t["blended_kwh_rate"]*100:.1f}&cent;/kWh</td>'
            f'<td>{t["off_peak_kwh_rate"]*100:.1f}&cent;/kWh</td>'
            f'<td>${t["fixed_monthly_charge"]:.2f}/mo</td>'
            f'<td>{p["solar_est_payback_years"]} yrs</td>'
            f'</tr>'
        )
    body = f"""
    <section class="hero">
      <a href="../../index.html">&larr; All States</a>
      <h1 style="margin-top:10px;">{esc(st_name)} Electricity Rates &amp; EV/Solar Calculators</h1>
      <p>Average tracked residential rate in {esc(st_name)}: <strong>{avg_rate*100:.1f}&cent;/kWh</strong> across {len(st_utils)} utilities.</p>
    </section>
    <div class="card" style="overflow-x:auto;">
      <table>
        <thead>
          <tr>
            <th>Utility</th>
            <th>Tariff</th>
            <th>Blended</th>
            <th>Off-Peak</th>
            <th>Fixed Fee</th>
            <th>Solar Payback</th>
          </tr>
        </thead>
        <tbody>{"".join(rows)}</tbody>
      </table>
    </div>
    """
    return render_shell(
        title=f'{st_name} Electricity Rates, EV Charging & Solar Payback | {config["site_name"]}',
        description=f'Compare {st_name} utility rates, off-peak EV charging costs, and solar payback timelines.',
        depth=2,
        body_html=body,
        config=config,
    )


def render_utility_page(u: dict, peers: list, sponsors: list, config: dict) -> str:
    t = u["default_tariff"]
    p = u["precomputed"]
    pl = config["partner_links"]
    st_name = STATE_NAMES.get(u["state"], u["state"])
    dg_factor = 0.95 if "net metering" in str(t.get("dg_compensation", "")).lower() else 0.78

    peak_set = set(t.get("weekday_peak_hours") or [])
    tou_cells = []
    for hour in range(24):
        label = f"{hour % 12 or 12}{'a' if hour < 12 else 'p'}"
        is_peak = hour in peak_set
        cls = "tou-peak" if is_peak else "tou-off"
        tag = "Peak" if is_peak else "Off"
        tou_cells.append(f'<div class="tou-cell {cls}">{label}<br><small>{tag}</small></div>')

    solar_url = (pl.get("solar_quote_url") or "").strip()
    ev_url = (pl.get("ev_charger_url") or "").strip()
    listing_url = (pl.get("featured_listing_url") or "").strip()

    ev_cta_html = (
        f'<div class="cta-strip">'
        f'<div><strong>Schedule overnight charging automatically</strong>'
        f'<div class="kpi-sub">Smart Level-2 chargers lock in {t["off_peak_kwh_rate"]*100:.1f}&cent;/kWh off-peak windows.</div></div>'
        f'<a class="btn btn-green" href="{esc(ev_url)}" target="_blank" rel="noopener sponsored">{esc(pl["ev_charger_cta_text"])} &rarr;</a>'
        f'</div>'
    ) if ev_url else ""

    solar_cta_html = (
        f'<div class="cta-strip">'
        f'<div><strong>Lock in your exact roof production &amp; installer bids</strong>'
        f'<div class="kpi-sub">Compare vetted {esc(st_name)} installers competing on your tariff.</div></div>'
        f'<a class="btn btn-green" href="{esc(solar_url)}" target="_blank" rel="noopener sponsored">{esc(pl["solar_cta_text"])} &rarr;</a>'
        f'</div>'
    ) if solar_url else ""

    active_sponsors = [
        s for s in sponsors
        if (s.get("utility_slug") == u["slug"] or s.get("state") == u["state"])
    ]
    if active_sponsors:
        s = active_sponsors[0]
        sponsor_html = (
            f'<div class="cta-strip" style="border-color:rgba(56,189,248,0.45);">'
            f'<div><span class="badge">Featured Local Partner</span>'
            f'<div style="font-weight:700;font-size:1.05rem;">{esc(s["company_name"])}</div>'
            f'<div class="kpi-sub">{esc(s.get("tagline", ""))}</div></div>'
            f'<a class="btn" href="{esc(s["url"])}" target="_blank" rel="noopener sponsored">Get Quote &rarr;</a>'
            f'</div>'
        )
    elif listing_url:
        sponsor_html = (
            f'<div class="cta-strip">'
            f'<div><strong>Local solar or EV-charger installer in {esc(st_name)}?</strong>'
            f'<div class="kpi-sub">Feature your business on this utility page automatically ({esc(pl.get("featured_price_label", "$49/mo"))}).</div></div>'
            f'<a class="btn btn-outline" href="{esc(listing_url)}" target="_blank" rel="noopener">Claim Featured Slot &rarr;</a>'
            f'</div>'
        )
    else:
        sponsor_html = ""

    peer_links = "".join(
        f'<li><a href="../{esc(peer["slug"])}/index.html">{esc(peer["utility_name"])} ({peer["default_tariff"]["blended_kwh_rate"]*100:.1f}&cent;/kWh)</a></li>'
        for peer in peers[:6]
        if peer["slug"] != u["slug"]
    )
    peers_section = (
        f'<section class="card" style="margin-top:24px;"><h3>Other Utilities in {esc(st_name)}</h3><ul>{peer_links}</ul></section>'
        if peer_links else ""
    )

    body = f"""
    <section class="hero">
      <a href="../../states/{u['state'].lower()}/index.html">&larr; {esc(st_name)} Utilities</a>
      <h1 style="margin-top:10px;">{esc(u["utility_name"])} EV Charging &amp; Solar Payback Calculator</h1>
      <p>Tariff: <strong>{esc(t["rate_name"])}</strong> &bull; Compensation: <strong>{esc(t["dg_compensation"])}</strong> &bull; Updated {esc(u["last_updated"])}</p>
    </section>

    <section class="grid-4">
      <div class="card">
        <div class="kpi-label">Blended Rate</div>
        <div class="kpi-val">{t["blended_kwh_rate"]*100:.1f}&cent;</div>
        <div class="kpi-sub">Per kWh residential</div>
      </div>
      <div class="card">
        <div class="kpi-label">Off-Peak EV Rate</div>
        <div class="kpi-val">{t["off_peak_kwh_rate"]*100:.1f}&cent;</div>
        <div class="kpi-sub">${p["ev_cost_per_1000_mi_offpeak"]:.2f} per 1,000 EV miles</div>
      </div>
      <div class="card">
        <div class="kpi-label">Fixed Monthly Fee</div>
        <div class="kpi-val">${t["fixed_monthly_charge"]:.2f}</div>
        <div class="kpi-sub">Meter / customer charge</div>
      </div>
      <div class="card">
        <div class="kpi-label">Est. Solar Payback</div>
        <div class="kpi-val">{p["solar_est_payback_years"]} yrs</div>
        <div class="kpi-sub">~${p["solar_annual_savings_7kw"]:,}/yr (7 kW)</div>
      </div>
    </section>

    <section id="payback-calculator" class="card"
      data-blended="{t['blended_kwh_rate']}"
      data-offpeak="{t['off_peak_kwh_rate']}"
      data-dgfactor="{dg_factor}">
      <div class="calc-tabs">
        <button id="tab-ev" class="tab-btn active" type="button">EV Home Charging Calculator</button>
        <button id="tab-solar" class="tab-btn" type="button">Rooftop Solar Payback</button>
      </div>

      <div id="panel-ev">
        <div class="slider-row">
          <label><span>Annual Miles Driven</span><strong id="ev-miles-val">12,000 mi/yr</strong></label>
          <input id="ev-miles" type="range" min="3000" max="30000" step="500" value="12000" />
        </div>
        <div class="slider-row">
          <label><span>Local Gas Price Comparison</span><strong id="gas-price-val">$3.45/gal</strong></label>
          <input id="gas-price" type="range" min="2.00" max="6.50" step="0.05" value="3.45" />
        </div>
        <div class="slider-row">
          <label><span>Gas Vehicle Fuel Economy</span><strong id="gas-mpg-val">28 MPG</strong></label>
          <input id="gas-mpg" type="range" min="14" max="50" step="1" value="28" />
        </div>
        <div class="result-banner grid-3" style="margin:12px 0 0;">
          <div><div class="kpi-label">Off-Peak EV Cost</div><div id="ev-annual-offpeak" class="kpi-val">&mdash;</div></div>
          <div><div class="kpi-label">Standard Rate EV Cost</div><div id="ev-annual-std" class="kpi-val">&mdash;</div></div>
          <div><div class="kpi-label">Annual Fuel Savings</div><div id="ev-annual-savings" class="kpi-val" style="color:var(--accent-2);">&mdash;</div></div>
        </div>
        {ev_cta_html}
      </div>

      <div id="panel-solar" class="hidden">
        <div class="slider-row">
          <label><span>Solar System Size</span><strong id="solar-kw-val">7.0 kW</strong></label>
          <input id="solar-kw" type="range" min="3" max="16" step="0.5" value="7" />
        </div>
        <div class="slider-row">
          <label><span>Installed Cost per Watt (Before Incentives)</span><strong id="solar-cost-val">$2.95/W</strong></label>
          <input id="solar-cost" type="range" min="2.00" max="4.50" step="0.05" value="2.95" />
        </div>
        <div class="slider-row">
          <label><span>Local Solar Production</span><strong id="solar-sun-val">1,400 kWh/kW/yr</strong></label>
          <input id="solar-sun" type="range" min="1000" max="1850" step="50" value="1400" />
        </div>
        <div class="result-banner grid-4" style="margin:12px 0 0;">
          <div><div class="kpi-label">Est. System Cost</div><div id="solar-install-cost" class="kpi-val">&mdash;</div></div>
          <div><div class="kpi-label">Annual Bill Savings</div><div id="solar-yr-savings" class="kpi-val">&mdash;</div></div>
          <div><div class="kpi-label">Simple Payback</div><div id="solar-payback" class="kpi-val" style="color:var(--accent-2);">&mdash;</div></div>
          <div><div class="kpi-label">25-Year Net Value</div><div id="solar-25yr" class="kpi-val">&mdash;</div></div>
        </div>
        {solar_cta_html}
      </div>
    </section>

    {sponsor_html}

    <section class="card" style="margin-top:24px;">
      <h2>24-Hour Weekday Rate Window ({esc("Time-of-Use" if t["has_tou"] else "Flat Residential Rate")})</h2>
      <p class="kpi-sub">Green hours indicate the lowest off-peak rate ({t["off_peak_kwh_rate"]*100:.1f}&cent;/kWh). Red hours indicate peak pricing ({t["on_peak_kwh_rate"]*100:.1f}&cent;/kWh).</p>
      <div class="tou-grid">{"".join(tou_cells)}</div>
    </section>

    {peers_section}
    """
    return render_shell(
        title=f'{u["utility_name"]} Electricity Rate, EV Charging & Solar Payback | {config["site_name"]}',
        description=f'{u["utility_name"]} ({u["state"]}) residential electricity rate is {t["blended_kwh_rate"]*100:.1f}c/kWh. Calculate off-peak EV charging costs and solar payback.',
        depth=2,
        body_html=body,
        config=config,
    )


def main() -> int:
    config = json.loads((DATA_DIR / "config.json").read_text(encoding="utf-8"))
    sponsors_data = json.loads((DATA_DIR / "sponsors.json").read_text(encoding="utf-8"))
    sponsors = sponsors_data.get("sponsors", [])

    utilities_path = DATA_DIR / "utilities.json"
    if not utilities_path.exists():
        print("Missing data/utilities.json. Run scripts/fetch_urdb.py first.", file=sys.stderr)
        return 1

    utilities = json.loads(utilities_path.read_text(encoding="utf-8"))
    states_map = collections.defaultdict(list)
    for u in utilities:
        states_map[u["state"]].append(u)

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    (ASSETS_DIR / "style.css").write_text(STYLE_CSS, encoding="utf-8")
    (ASSETS_DIR / "calculator.js").write_text(CALCULATOR_JS, encoding="utf-8")

    (DIST_DIR / "index.html").write_text(render_home(utilities, states_map, config), encoding="utf-8")

    domain = (config.get("site_domain") or "").strip().strip("/")
    base_url = (os.environ.get("SITE_URL") or (f"https://{domain}" if domain else "")).rstrip("/")
    sitemap_paths = ["/"]

    for state, st_utils in sorted(states_map.items()):
        out_dir = DIST_DIR / "states" / state.lower()
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(render_state_page(state, st_utils, config), encoding="utf-8")
        sitemap_paths.append(f"/states/{state.lower()}/")

    for u in utilities:
        out_dir = DIST_DIR / "utility" / u["slug"]
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "index.html").write_text(
            render_utility_page(u, states_map[u["state"]], sponsors, config),
            encoding="utf-8",
        )
        sitemap_paths.append(f'/utility/{u["slug"]}/')

    url_entries = "\n".join(f"  <url><loc>{esc(base_url + p)}</loc></url>" for p in sitemap_paths)
    sitemap_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset>\n'
        f"{url_entries}\n"
        "</urlset>\n"
    )
    (DIST_DIR / "sitemap.xml").write_text(sitemap_xml, encoding="utf-8")
    robots_lines = ["User-agent: *", "Allow: /"]
    if base_url:
        robots_lines.append(f"Sitemap: {base_url}/sitemap.xml")
    (DIST_DIR / "robots.txt").write_text("\n".join(robots_lines) + "\n", encoding="utf-8")

    print(
        f"Built static site in {DIST_DIR}: 1 home page, {len(states_map)} state hubs, "
        f"{len(utilities)} utility calculator pages ({len(sitemap_paths)} total URLs)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

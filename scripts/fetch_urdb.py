#!/usr/bin/env python3
"""
Fetch and normalize U.S. residential electricity tariffs from the OpenEI Utility Rate Database (URDB).

Usage:
  # Live API pull (requires free OPENEI_API_KEY from https://openei.org/services/):
  OPENEI_API_KEY=your_key python3 scripts/fetch_urdb.py --limit 500

  # Zero-key local test mode using realistic seed utilities:
  python3 scripts/fetch_urdb.py --seed
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CONFIG_PATH = DATA_DIR / "config.json"
SEED_PATH = DATA_DIR / "seed_utilities.json"
OUTPUT_PATH = DATA_DIR / "utilities.json"

URDB_ENDPOINT = "https://api.openei.org/utility_rates"


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "utility"


def compute_metrics(tariff: dict, defaults: dict) -> dict:
    """Compute pre-rendered EV charging and rooftop solar payback metrics."""
    blended = float(tariff["blended_kwh_rate"])
    off_peak = float(tariff["off_peak_kwh_rate"])

    kwh_per_100 = float(defaults.get("ev_kwh_per_100_mi", 28.0))
    gas_mpg = float(defaults.get("gas_mpg_comparison", 28.0))
    gas_price = float(defaults.get("gas_price_per_gal", 3.45))
    solar_kw = float(defaults.get("solar_system_kw", 7.0))
    cost_per_watt = float(defaults.get("solar_install_cost_per_watt", 2.95))
    kwh_per_kw_yr = float(defaults.get("solar_annual_kwh_per_kw", 1400))

    kwh_per_1000 = kwh_per_100 * 10.0
    ev_std_1000 = round(kwh_per_1000 * blended, 2)
    ev_offpeak_1000 = round(kwh_per_1000 * off_peak, 2)
    gas_1000 = round((1000.0 / gas_mpg) * gas_price, 2)

    annual_solar_kwh = solar_kw * kwh_per_kw_yr
    # Slight discount if utility does not offer full retail Net Metering
    dg = str(tariff.get("dg_compensation", "Net Metering")).lower()
    export_factor = 0.95 if "net metering" in dg else 0.78
    solar_annual_savings = round(annual_solar_kwh * blended * export_factor)
    gross_install_cost = solar_kw * 1000.0 * cost_per_watt
    payback_years = round(gross_install_cost / max(solar_annual_savings, 1), 1)

    return {
        "ev_cost_per_1000_mi_home": ev_std_1000,
        "ev_cost_per_1000_mi_offpeak": ev_offpeak_1000,
        "gas_cost_per_1000_mi": gas_1000,
        "ev_savings_per_1000_mi_offpeak": round(gas_1000 - ev_offpeak_1000, 2),
        "solar_annual_savings_7kw": solar_annual_savings,
        "solar_est_payback_years": payback_years,
    }


def parse_urdb_item(item: dict) -> dict | None:
    """Normalize a single OpenEI URDB JSON item into our clean schema."""
    utility_name = item.get("utility")
    if not utility_name:
        return None

    # Extract tiered energy rate structure: [[{rate, adj, max, ...}, ...], ...]
    ers = item.get("energyratestructure") or []
    period_rates = []
    for period in ers:
        if not period:
            continue
        first_tier = period[0]
        rate = float(first_tier.get("rate", 0.0) or 0.0) + float(first_tier.get("adj", 0.0) or 0.0)
        if rate > 0:
            period_rates.append(rate)

    if not period_rates:
        return None

    off_peak = round(min(period_rates), 4)
    on_peak = round(max(period_rates), 4)
    blended = round(sum(period_rates) / len(period_rates), 4)
    has_tou = len(set(round(r, 3) for r in period_rates)) > 1

    # Detect weekday peak hours from July (index 6) weekday schedule
    weekday_peak_hours = []
    weekday_sched = item.get("energyweekdayschedule")
    if has_tou and isinstance(weekday_sched, list) and len(weekday_sched) >= 7:
        max_period_idx = period_rates.index(max(period_rates))
        july_hours = weekday_sched[6]
        if isinstance(july_hours, list) and len(july_hours) == 24:
            weekday_peak_hours = [h for h, p in enumerate(july_hours) if p == max_period_idx]

    fixed_charge = float(item.get("fixedchargefirstmeter", 0.0) or 0.0)
    fixed_units = str(item.get("fixedchargeunits", "$/month") or "$/month").lower()
    if "day" in fixed_units:
        fixed_charge = round(fixed_charge * 30.0, 2)
    elif "year" in fixed_units:
        fixed_charge = round(fixed_charge / 12.0, 2)
    else:
        fixed_charge = round(fixed_charge, 2)

    state = str(item.get("state") or "US").upper()[:2]
    eia_id = item.get("eiaid") or 0
    uri = item.get("uri") or "https://apps.openei.org/USURDB/"

    return {
        "slug": slugify(f"{utility_name}-{state}"),
        "utility_name": utility_name.strip(),
        "state": state,
        "eia_id": int(eia_id) if str(eia_id).isdigit() else 0,
        "zip_codes": [],
        "source_uri": uri,
        "default_tariff": {
            "rate_name": str(item.get("name") or "Residential Standard").strip(),
            "fixed_monthly_charge": fixed_charge,
            "blended_kwh_rate": blended,
            "off_peak_kwh_rate": off_peak,
            "on_peak_kwh_rate": on_peak,
            "has_tou": has_tou,
            "dg_compensation": str(item.get("dgrules") or "Net Metering"),
            "weekday_peak_hours": weekday_peak_hours,
        },
    }


def fetch_from_openei(api_key: str, limit: int, max_pages: int) -> list:
    """Pull approved residential tariffs from OpenEI URDB REST API."""
    records_by_slug = {}
    page_size = min(limit, 500)

    for page in range(max_pages):
        offset = page * page_size
        params = urllib.parse.urlencode(
            {
                "version": "latest",
                "format": "json",
                "sector": "Residential",
                "approved": "true",
                "country": "USA",
                "detail": "full",
                "limit": page_size,
                "offset": offset,
                "api_key": api_key,
            }
        )
        url = f"{URDB_ENDPOINT}?{params}"
        print(f"Fetching OpenEI URDB offset={offset} limit={page_size}...")
        req = urllib.request.Request(url, headers={"User-Agent": "WattWisePaybackBot/1.0"})
        with urllib.request.urlopen(req, timeout=45) as resp:
            payload = json.loads(resp.read().decode("utf-8"))

        items = payload.get("items") or []
        if not items:
            break

        for raw in items:
            parsed = parse_urdb_item(raw)
            if not parsed:
                continue
            slug = parsed["slug"]
            # Prefer tariffs marked is_default or containing TOU data
            if slug not in records_by_slug or raw.get("is_default"):
                records_by_slug[slug] = parsed

        if len(items) < page_size or len(records_by_slug) >= limit:
            break

    return list(records_by_slug.values())


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync OpenEI URDB residential utility rates.")
    parser.add_argument("--seed", action="store_true", help="Use local seed dataset (no API key required).")
    parser.add_argument("--limit", type=int, default=500, help="Max utilities to pull from OpenEI API.")
    parser.add_argument("--max-pages", type=int, default=5, help="Max API pagination calls.")
    args = parser.parse_args()

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    defaults = config.get("defaults", {})
    today = datetime.date.today().isoformat()

    api_key = os.environ.get("OPENEI_API_KEY", "").strip()
    if args.seed or not api_key:
        if not args.seed:
            print("OPENEI_API_KEY not set; falling back to local seed dataset (data/seed_utilities.json).")
        utilities = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    else:
        utilities = fetch_from_openei(api_key=api_key, limit=args.limit, max_pages=args.max_pages)

    enriched = []
    for u in utilities:
        u["last_updated"] = today
        u["precomputed"] = compute_metrics(u["default_tariff"], defaults)
        enriched.append(u)

    enriched.sort(key=lambda x: (x["state"], x["utility_name"]))
    OUTPUT_PATH.write_text(json.dumps(enriched, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(enriched)} normalized utility records to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

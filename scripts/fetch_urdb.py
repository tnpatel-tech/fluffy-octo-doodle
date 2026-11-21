#!/usr/bin/env python3
"""
Fetch and normalize U.S. residential electricity tariffs from the OpenEI Utility Rate Database (URDB).
Merges live OpenEI tariffs with curated seed ZIP/state metadata and infers U.S. states cleanly.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CONFIG_PATH = DATA_DIR / "config.json"
SEED_PATH = DATA_DIR / "seed_utilities.json"
OUTPUT_PATH = DATA_DIR / "utilities.json"

URDB_ENDPOINT = "https://api.openei.org/utility_rates"

STATE_NAME_TO_CODE = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
}

VALID_STATES = set(STATE_NAME_TO_CODE.values())

CITY_TO_STATE = {
    "seattle": "WA", "tacoma": "WA", "houston": "TX", "dallas": "TX", "austin": "TX",
    "san antonio": "TX", "los angeles": "CA", "san diego": "CA", "sacramento": "CA",
    "san francisco": "CA", "chicago": "IL", "phoenix": "AZ", "tucson": "AZ",
    "miami": "FL", "orlando": "FL", "tampa": "FL", "jacksonville": "FL",
    "atlanta": "GA", "boston": "MA", "detroit": "MI", "denver": "CO",
    "philadelphia": "PA", "pittsburgh": "PA", "charlotte": "NC", "raleigh": "NC",
    "richmond": "VA", "huntsville": "AL", "birmingham": "AL", "nashville": "TN",
    "memphis": "TN", "knoxville": "TN", "chattanooga": "TN", "omaha": "NE",
    "lincoln": "NE", "anchorage": "AK", "fairbanks": "AK", "honolulu": "HI",
    "portland": "OR", "las vegas": "NV", "salt lake": "UT", "columbus": "OH",
    "cleveland": "OH", "cincinnati": "OH", "indianapolis": "IN", "milwaukee": "WI",
    "minneapolis": "MN", "st. louis": "MO", "kansas city": "MO", "new orleans": "LA",
    "baltimore": "MD", "newark": "NJ", "buffalo": "NY", "rochester": "NY",
}


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "utility"


def infer_state(raw_state: str, utility_name: str) -> str:
    """Resolve a 2-letter U.S. state code from API field or utility name."""
    s = (raw_state or "").strip().upper()
    if len(s) == 2 and s in VALID_STATES:
        return s

    lower = utility_name.lower()
    # Check full state names (longest first so "west virginia" matches before "virginia")
    for name in sorted(STATE_NAME_TO_CODE.keys(), key=len, reverse=True):
        if re.search(r"\b" + re.escape(name) + r"\b", lower):
            return STATE_NAME_TO_CODE[name]

    # Check major city names
    for city, code in CITY_TO_STATE.items():
        if re.search(r"\b" + re.escape(city) + r"\b", lower):
            return code

    # Check parenthetical or trailing 2-letter state code, e.g., "(TX)" or "- NC"
    m = re.search(r"[\(\-\s,]([A-Z]{2})\)?$", utility_name.strip())
    if m and m.group(1) in VALID_STATES:
        return m.group(1)

    return "US"


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
    utility_name = str(item.get("utility") or "").strip()
    if not utility_name:
        return None

    ers = item.get("energyratestructure") or []
    period_rates = []
    for period in ers:
        if not period:
            continue
        first_tier = period[0]
        rate = float(first_tier.get("rate", 0.0) or 0.0) + float(first_tier.get("adj", 0.0) or 0.0)
        # Filter out broken/outlier tariffs outside realistic residential bounds ($0.04–$1.00/kWh)
        if 0.04 <= rate <= 1.00:
            period_rates.append(rate)

    if not period_rates:
        return None

    off_peak = round(min(period_rates), 4)
    on_peak = round(max(period_rates), 4)
    blended = round(sum(period_rates) / len(period_rates), 4)
    has_tou = len(set(round(r, 3) for r in period_rates)) > 1

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

    state = infer_state(str(item.get("state") or ""), utility_name)
    eia_id = item.get("eiaid") or 0
    uri = item.get("uri") or "https://apps.openei.org/USURDB/"

    return {
        "slug": slugify(f"{utility_name}-{state}"),
        "utility_name": utility_name,
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
    """Pull approved residential tariffs from OpenEI URDB REST API with retry/backoff."""
    records_by_slug = {}
    page_size = min(limit, 100)

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
        payload = None
        for attempt in range(3):
            print(f"Fetching OpenEI URDB offset={offset} limit={page_size} (attempt {attempt + 1})...")
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; WattWisePayback/1.0)"},
            )
            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                    wait_s = 5 * (attempt + 1)
                    print(f"OpenEI returned HTTP {exc.code}; retrying in {wait_s}s...")
                    time.sleep(wait_s)
                    continue
                raise

        items = (payload or {}).get("items") or []
        if not items:
            break

        for raw in items:
            parsed = parse_urdb_item(raw)
            if not parsed:
                continue
            slug = parsed["slug"]
            if slug not in records_by_slug or raw.get("is_default"):
                records_by_slug[slug] = parsed

        if len(items) < page_size or len(records_by_slug) >= limit:
            break
        time.sleep(2)

    return list(records_by_slug.values())


def merge_with_seed(live_records: list, seed_records: list) -> list:
    """Ensure curated major utilities and their ZIP mappings are always preserved."""
    by_eia = {}
    by_slug = {}

    for u in live_records:
        by_slug[u["slug"]] = u
        if u.get("eia_id"):
            by_eia[u["eia_id"]] = u

    for s in seed_records:
        match = by_eia.get(s.get("eia_id")) if s.get("eia_id") else None
        if match:
            # Enrich live record with curated state and ZIP codes
            if match["state"] == "US" and s.get("state"):
                match["state"] = s["state"]
            existing_zips = set(match.get("zip_codes") or [])
            existing_zips.update(s.get("zip_codes") or [])
            match["zip_codes"] = sorted(existing_zips)
        elif s["slug"] not in by_slug:
            by_slug[s["slug"]] = s

    return list(by_slug.values())


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync OpenEI URDB residential utility rates.")
    parser.add_argument("--seed", action="store_true", help="Use local seed dataset (no API key required).")
    parser.add_argument("--limit", type=int, default=500, help="Max utilities to pull from OpenEI API.")
    parser.add_argument("--max-pages", type=int, default=5, help="Max API pagination calls.")
    args = parser.parse_args()

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    defaults = config.get("defaults", {})
    today = datetime.date.today().isoformat()
    seed_utilities = json.loads(SEED_PATH.read_text(encoding="utf-8"))

    api_key = os.environ.get("OPENEI_API_KEY", "").strip()
    if args.seed or not api_key:
        if not args.seed:
            print("OPENEI_API_KEY not set; using local seed dataset (data/seed_utilities.json).")
        utilities = seed_utilities
    else:
        try:
            live = fetch_from_openei(api_key=api_key, limit=args.limit, max_pages=args.max_pages)
            utilities = merge_with_seed(live, seed_utilities)
        except Exception as exc:
            print(f"Warning: OpenEI API request failed ({exc}). Keeping existing dataset so deploy succeeds.")
            if OUTPUT_PATH.exists():
                utilities = merge_with_seed(json.loads(OUTPUT_PATH.read_text(encoding="utf-8")), seed_utilities)
            else:
                utilities = seed_utilities

    enriched = []
    for u in utilities:
        u["last_updated"] = today
        u["precomputed"] = compute_metrics(u["default_tariff"], defaults)
        enriched.append(u)

    enriched.sort(key=lambda x: (x["state"] == "US", x["state"], x["utility_name"]))
    OUTPUT_PATH.write_text(json.dumps(enriched, indent=2) + "\n", encoding="utf-8")
    states_count = len({u["state"] for u in enriched if u["state"] != "US"})
    print(f"Wrote {len(enriched)} normalized utility records across {states_count} states to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Build a compact client-side ZIP-to-utility lookup JSON index.
Keeps total static site files well under Cloudflare Pages' 20,000-file free limit.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UTILITIES_PATH = ROOT / "data" / "utilities.json"
DIST_DIR = ROOT / "dist"
ZIP_MAP_PATH = DIST_DIR / "zip-map.json"


def main() -> int:
    if not UTILITIES_PATH.exists():
        print(f"Missing {UTILITIES_PATH}. Run scripts/fetch_urdb.py first.", file=sys.stderr)
        return 1

    utilities = json.loads(UTILITIES_PATH.read_text(encoding="utf-8"))
    zip_map = {}
    for u in utilities:
        entry = {
            "slug": u["slug"],
            "name": u["utility_name"],
            "state": u["state"],
            "rate": u["default_tariff"]["blended_kwh_rate"],
        }
        for z in u.get("zip_codes", []):
            z_clean = str(z).strip().zfill(5)
            zip_map.setdefault(z_clean, []).append(entry)

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    ZIP_MAP_PATH.write_text(json.dumps(zip_map, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {len(zip_map)} ZIP mappings to {ZIP_MAP_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

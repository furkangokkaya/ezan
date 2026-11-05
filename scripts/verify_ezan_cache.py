#!/usr/bin/env python3
"""GitHub Actions — bitlis_ezan_cache.json doğrulama."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bitlis_services.ezan import is_ezan_cache_complete, today_tr  # noqa: E402

CACHE = ROOT / "bitlis_ezan_cache.json"


def main() -> int:
    today = today_tr()
    data = json.loads(CACHE.read_text(encoding="utf-8"))
    print(f"date={data.get('date')} expected={today} total={data.get('total')} source={data.get('source')}")
    if "diyanet" not in str(data.get("source") or "").lower():
        print(f"HATA: beklenmeyen kaynak: {data.get('source')}", file=sys.stderr)
        return 1
    if str(data.get("date") or "") != today:
        print(f"HATA: tarih uyumsuz ({data.get('date')} != {today})", file=sys.stderr)
        return 1
    if not is_ezan_cache_complete(data):
        print("HATA: ezan cache eksik", file=sys.stderr)
        return 1
    print("OK: ezan cache")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

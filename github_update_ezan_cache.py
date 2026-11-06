#!/usr/bin/env python3
"""GitHub Actions — günlük ezan vakti cache."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from bitlis_services.ezan import ezan_posting_moment, fetch_live, is_ezan_cache_complete  # noqa: E402

OUT = ROOT / "bitlis_ezan_cache.json"


def main() -> int:
    day = ezan_posting_moment()
    today = day.strftime("%Y-%m-%d")
    print(f"TR tarih: {today}", flush=True)
    data: dict = {}
    last_error = ""
    for attempt in range(1, 4):
        data = fetch_live(day)
        if (
            data.get("ok")
            and str(data.get("date") or "") == today
            and is_ezan_cache_complete(data)
        ):
            break
        last_error = str(data.get("error") or "ezan verisi alinamadi")
        print(f"Uyari: deneme {attempt}/3 basarisiz: {last_error}", flush=True)
        if attempt < 3:
            time.sleep(8 * attempt)

    if not is_ezan_cache_complete(data) or str(data.get("date") or "") != today:
        if OUT.exists():
            try:
                cached = json.loads(OUT.read_text(encoding="utf-8"))
                if str(cached.get("date") or "") == today and is_ezan_cache_complete(cached):
                    print("Uyari: canli scrape basarisiz, bugunku cache korunuyor.", flush=True)
                    return 0
            except Exception:
                pass
        print("HATA:", last_error or data.get("error") or "ezan verisi alinamadi", file=sys.stderr)
        return 1

    payload = {k: v for k, v in data.items() if not str(k).startswith("_")}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK: {data.get('total', 0)} ilce — {today} — {data.get('source')} -> {OUT.name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

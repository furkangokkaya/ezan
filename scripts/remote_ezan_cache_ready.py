#!/usr/bin/env python3
"""Remote ezan cache bugün hazırsa scrape adımını atla."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bitlis_services.ezan import is_ezan_cache_complete, today_tr  # noqa: E402


def main() -> int:
    today = today_tr()
    ready = False
    r = subprocess.run(
        ["git", "show", "origin/main:bitlis_ezan_cache.json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if r.returncode == 0 and (r.stdout or "").strip():
        try:
            data = json.loads(r.stdout)
            ready = (
                str(data.get("date") or "") == today
                and "diyanet" in str(data.get("source") or "").lower()
                and is_ezan_cache_complete(data)
            )
        except Exception:
            ready = False

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"ready={'true' if ready else 'false'}\n")
    print(f"Remote ezan cache {'hazir' if ready else 'guncellenmeli'} ({today}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

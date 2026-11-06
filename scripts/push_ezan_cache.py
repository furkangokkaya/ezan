#!/usr/bin/env python3
"""GitHub Actions — ezan cache push."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "bitlis_ezan_cache.json"
sys.path.insert(0, str(ROOT))


# Hesaba bağlı e-posta yok — GitHub Contributors listesine düşmez.
_GIT = ["git", "-c", "user.name=ezan", "-c", "user.email=ezan@example.invalid"]


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)


def _cache_ok(data: dict) -> bool:
    from bitlis_services.ezan import ezan_posting_date, is_ezan_cache_complete

    return (
        str(data.get("date") or "") == ezan_posting_date()
        and "diyanet" in str(data.get("source") or "").lower()
        and is_ezan_cache_complete(data)
    )


def _remote_ok() -> bool:
    r = _run(["git", "show", "origin/main:bitlis_ezan_cache.json"])
    if r.returncode != 0 or not (r.stdout or "").strip():
        return False
    try:
        return _cache_ok(json.loads(r.stdout))
    except Exception:
        return False


def main() -> int:
    from bitlis_services.ezan import ezan_posting_date

    if not CACHE.is_file():
        print("HATA: bitlis_ezan_cache.json yok", file=sys.stderr)
        return 1
    local = json.loads(CACHE.read_text(encoding="utf-8"))
    if not _cache_ok(local):
        print("HATA: yerel ezan cache dogrulanamadi", file=sys.stderr)
        return 1

    if _run(["git", "fetch", "origin", "main"]).returncode != 0:
        print("HATA: fetch", file=sys.stderr)
        return 1
    if _remote_ok():
        print("Remote zaten bugunku ezan cache — push atlandi.")
        return 0

    today = ezan_posting_date()
    _run(["git", "add", "bitlis_ezan_cache.json"])
    if _run(["git", "diff", "--staged", "--quiet"]).returncode == 0:
        print("Staged degisiklik yok.")
        return 0
    if _run([*_GIT, "commit", "-m", f"chore: ezan cache {today}"]).returncode != 0:
        print("HATA: commit", file=sys.stderr)
        return 1

    for attempt in range(1, 6):
        if _run(["git", "push", "origin", "HEAD:main"]).returncode == 0:
            print("Push OK.")
            return 0
        print(f"Push deneme {attempt}/5", flush=True)
        _run(["git", "fetch", "origin", "main"])
        if _remote_ok():
            _run(["git", "reset", "--hard", "origin/main"])
            print("Remote bugunku cache OK.")
            return 0
        rebase = _run(["git", "pull", "--rebase", "origin", "main"])
        if rebase.returncode != 0:
            _run(["git", "rebase", "--abort"])
            _run(["git", "reset", "--hard", "origin/main"])
            CACHE.write_text(json.dumps(local, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            _run(["git", "add", "bitlis_ezan_cache.json"])
            _run([*_GIT, "commit", "-m", f"chore: ezan cache {today}"])
        time.sleep(min(20, 4 * attempt))
    print("HATA: push basarisiz", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

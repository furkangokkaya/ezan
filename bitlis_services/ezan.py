"""Bitlis il ve ilçe ezan vakitleri — Diyanet resmi tablosu."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

logger = logging.getLogger("bitlis.ezan")

TZ_TR = ZoneInfo("Europe/Istanbul")
CACHE_PATH = Path(__file__).resolve().parents[1] / "bitlis_ezan_cache.json"
DEFAULT_GITHUB_CACHE_URL = (
    "https://raw.githubusercontent.com/furkangokkaya/ezan/main/bitlis_ezan_cache.json"
)
SOURCE = "namazvakitleri.diyanet.gov.tr"
_MONTHS = (
    "", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
)
# Diyanet ilçe kimlikleri — namazvakitleri.diyanet.gov.tr
LOCS = (
    ("BİTLİS MERKEZ", 9311),
    ("TATVAN", 9314),
    ("ADİLCEVAZ", 9309),
    ("AHLAT", 9310),
    ("GÜROYMAK", 17887),
    ("HİZAN", 9312),
    ("MUTKİ", 9313),
)
KEYS = ("İmsak", "Güneş", "Öğle", "İkindi", "Akşam", "Yatsı")
_HHMM = re.compile(r"^\d{2}:\d{2}$")


def today_tr(now: Optional[datetime] = None) -> str:
    moment = now or datetime.now(TZ_TR)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=TZ_TR)
    return moment.astimezone(TZ_TR).strftime("%Y-%m-%d")


def is_ezan_cache_complete(data: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(data, dict) or not data.get("ok"):
        return False
    places = data.get("places") or []
    if len(places) < len(LOCS):
        return False
    names = {str(p.get("name") or "") for p in places}
    if any(name not in names for name, _district_id in LOCS):
        return False
    for place in places:
        if not _times_sane(place.get("times") or {}):
            return False
    return True


def _minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def _times_sane(times: Dict[str, Any]) -> bool:
    values: List[int] = []
    for key in KEYS:
        text = str(times.get(key) or "").strip()
        if not _HHMM.fullmatch(text):
            return False
        values.append(_minutes(text))
    return all(values[i] < values[i + 1] for i in range(len(values) - 1))


def _diyanet_day(moment: datetime) -> str:
    return f"{moment.day:02d} {_MONTHS[moment.month]} {moment.year}"


def _row_times(html: str, day_prefix: str) -> Optional[List[str]]:
    pattern = re.compile(
        r"<td>\s*" + re.escape(day_prefix) + r"[^<]*</td>\s*"
        r"<td>[^<]*</td>\s*"
        + r"<td>\s*(\d{2}:\d{2})\s*</td>\s*" * 6,
        re.IGNORECASE,
    )
    match = pattern.search(html or "")
    if not match:
        return None
    return list(match.groups())


def fetch_live(now: Optional[datetime] = None) -> Dict[str, Any]:
    """Diyanet resmi ilçe tablosu. Tarih Europe/Istanbul."""
    moment = now or datetime.now(TZ_TR)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=TZ_TR)
    else:
        moment = moment.astimezone(TZ_TR)
    day_prefix = _diyanet_day(moment)
    places: List[Dict[str, Any]] = []
    last_error = ""
    headers = {"User-Agent": "BitlisBilgiBot/1.0", "Accept-Language": "tr-TR"}
    for name, district_id in LOCS:
        url = f"https://namazvakitleri.diyanet.gov.tr/tr-TR/{district_id}"
        try:
            response = requests.get(url, headers=headers, timeout=40)
            response.raise_for_status()
            clocks = _row_times(response.text, day_prefix)
            if not clocks or not _times_sane(dict(zip(KEYS, clocks))):
                raise ValueError(f"{day_prefix} satiri yok veya saat sirasi hatali")
            places.append({
                "name": name,
                "diyanet_id": district_id,
                "times": {label: clock for label, clock in zip(KEYS, clocks)},
            })
        except Exception as exc:
            last_error = str(exc)
            logger.warning("Ezan alinamadi (%s): %s", name, exc)
    result: Dict[str, Any] = {
        "ok": len(places) == len(LOCS),
        "date": moment.strftime("%Y-%m-%d"),
        "date_label": moment.strftime("%d.%m.%Y"),
        "source": SOURCE,
        "total": len(places),
        "places": places,
    }
    if not result["ok"]:
        result["error"] = last_error or "ezan vakitleri alinamadi"
    return result


def _save_cache(data: Dict[str, Any]) -> None:
    if not data.get("ok"):
        return
    try:
        payload = {k: v for k, v in data.items() if not str(k).startswith("_")}
        CACHE_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.debug("Ezan cache yazilamadi: %s", exc)


def _load_local_cache(expected: str) -> Optional[Dict[str, Any]]:
    if not CACHE_PATH.is_file():
        return None
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    if str(data.get("date") or "") != expected or not is_ezan_cache_complete(data):
        return None
    return data


def fetch_ezan_times(
    *,
    remote_url: str = "",
    remote_token: str = "",
    github_only: bool = True,
) -> Dict[str, Any]:
    """Bugünün vakitleri. Varsayılan: GitHub raw cache. github_only=False canlı Aladhan."""
    expected = today_tr()
    if not github_only:
        live = fetch_live()
        if is_ezan_cache_complete(live) and str(live.get("date") or "") == expected:
            _save_cache(live)
        return live

    url = (remote_url or DEFAULT_GITHUB_CACHE_URL).strip()
    headers = {
        "Accept": "application/json",
        "User-Agent": "BitlisBilgiBot/1.0",
        "Cache-Control": "no-cache",
    }
    if remote_token:
        headers["Authorization"] = f"Bearer {remote_token}"
    sep = "&" if "?" in url else "?"
    try:
        response = requests.get(f"{url}{sep}t={int(datetime.now().timestamp())}", headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        local = _load_local_cache(expected)
        if local:
            local["source_mode"] = "local_cache"
            return local
        return {
            "ok": False,
            "date": "",
            "error": f"GitHub ezan cache alinamadi: {exc}",
            "source": "remote_bridge",
            "_stale": True,
        }

    if not isinstance(data, dict):
        return {"ok": False, "error": "GitHub ezan cache gecersiz", "_stale": True}

    remote_date = str(data.get("date") or "").strip()
    ready = remote_date == expected and is_ezan_cache_complete(data)
    data["_stale"] = not ready
    data["source"] = data.get("source") or SOURCE
    if ready:
        _save_cache(data)
        return data

    local = _load_local_cache(expected)
    if local:
        local["source_mode"] = "local_cache"
        return local
    data["ok"] = False
    data["error"] = data.get("error") or f"GitHub ezan cache bugun degil ({remote_date or 'yok'})"
    return data

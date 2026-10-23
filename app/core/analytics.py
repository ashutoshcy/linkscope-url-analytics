from datetime import datetime, timedelta
from collections import Counter
from urllib.parse import urlsplit
import hashlib
import hmac
import re
from sqlalchemy import select, func
from app.db.models import Click, Link, utcnow
from app.core.config import secret_key


def classify(ua: str) -> tuple[str, str, str, bool]:
    ua = ua[:512]
    low = ua.lower()
    bot = bool(re.search(r"bot|spider|crawler|headless|preview|curl|wget|python-requests|httpx", low))
    device = "Tablet" if "ipad" in low or "tablet" in low else "Mobile" if "mobile" in low or "iphone" in low or "android" in low else "Desktop"
    platform = "iOS" if "iphone" in low or "ipad" in low else "Android" if "android" in low else "Windows" if "windows" in low else "macOS" if "mac os" in low else "Linux" if "linux" in low else "Other"
    browser = "Edge" if "edg/" in low else "Firefox" if "firefox" in low else "Chrome" if "chrome" in low else "Safari" if "safari" in low else "Other"
    return device, browser, platform, bot


def referrer_domain(ref: str) -> str:
    try:
        parsed = urlsplit(ref)
        host = parsed.hostname
        return host.lower()[:200] if parsed.scheme in ("http", "https") and host else "Direct"
    except ValueError:
        return "Direct"


def fingerprint(ip: str, ua: str, link_id: int, date: str) -> str:
    # HMAC makes visitor grouping possible without storing raw IP addresses.
    blob = f"{link_id}|{date}|{ip}|{ua[:300]}".encode("utf-8")
    return hmac.new(secret_key().encode(), blob, hashlib.sha256).hexdigest()


def rollup(clicks: list[Click], days: int):
    today = utcnow().date()
    daily = Counter(c.clicked_at.date().isoformat() for c in clicks)
    series = [{"date": (today - timedelta(days=i)).isoformat(), "clicks": daily.get((today - timedelta(days=i)).isoformat(), 0)} for i in range(days-1, -1, -1)]
    return {
        "total_clicks": len(clicks),
        "unique_visitors": sum(1 for c in clicks if c.is_unique),
        "series": series,
        "referrers": [{"name": k, "value": v} for k,v in Counter(c.referrer for c in clicks).most_common(6)],
        "devices": [{"name": k, "value": v} for k,v in Counter(c.device for c in clicks).most_common()],
        "browsers": [{"name": k, "value": v} for k,v in Counter(c.browser for c in clicks).most_common(5)],
        "campaigns": [{"name": k, "value": v} for k,v in Counter(c.utm_campaign for c in clicks if c.utm_campaign).most_common(6)],
    }

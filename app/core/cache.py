"""Optional Redis: short-link lookup cache and distributed auth rate limits.

The app works without Redis; any connection failure falls back to SQL reads.
"""
import json
import os
from functools import lru_cache

@lru_cache(maxsize=1)
def client():
    url=os.getenv('REDIS_URL', '').strip()
    if not url:
        return None
    try:
        import redis
        return redis.Redis.from_url(url, socket_connect_timeout=0.3, socket_timeout=0.3, decode_responses=True)
    except (ImportError, ValueError):
        return None


def get_link(slug: str):
    c=client()
    if not c:
        return None
    try:
        found=c.get('linkscope:slug:'+slug)
        return json.loads(found) if found else None
    except Exception:
        return None


def cache_link(slug: str, data: dict):
    c=client()
    if c:
        try: c.setex('linkscope:slug:'+slug,60,json.dumps(data))
        except Exception: pass


def invalidate_link(slug: str):
    c=client()
    if c:
        try: c.delete('linkscope:slug:'+slug)
        except Exception: pass


def allow_attempt(ip: str, action: str, limit: int, window: int = 60) -> bool:
    """Fixed-window rate limiter with Redis, fail-open without Redis."""
    c=client()
    if not c:
        return True
    try:
        from hashlib import sha256
        key='linkscope:rl:'+action+':'+sha256(ip.encode()).hexdigest()[:24]
        count=c.incr(key)
        if count==1: c.expire(key,window)
        return count<=limit
    except Exception:
        return True

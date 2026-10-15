"""Login brute-force protection, 2FA code storage and admin roles.

State lives in Redis (shared between processes, survives restarts). If Redis is unreachable we fall back to
process memory and log a warning, so the admin panel keeps working in development.
"""
import logging
import time
from typing import Dict, Optional, Tuple

from fastapi import HTTPException, Request

from bot.core.config import config

log = logging.getLogger("admin_api.security")

LOCK_SECONDS = 15 * 60
# (name, max failures): a failure counts against all three counters, any of them reaching its limit locks the login.
LIMIT_USER_IP = 5      # one username from one IP: stops guessing without letting an outsider lock the real admin out
LIMIT_IP = 20          # one IP trying many usernames
LIMIT_USER = 30        # one username from many IPs (distributed guessing)
CODE_TTL = 300
CODE_MAX_ATTEMPTS = 5

ROLE_SUPER = "superadmin"
ROLE_MODERATOR = "moderator"
ROLE_FINANCE = "finance"
ADMIN_ROLES = (ROLE_SUPER, ROLE_MODERATOR, ROLE_FINANCE)


def effective_role(user) -> str:
    """Admins created before roles existed have admin_role = NULL and keep full access."""
    return getattr(user, "admin_role", None) or ROLE_SUPER


class _Memory:
    def __init__(self):
        self._d: Dict[str, Tuple[str, float]] = {}

    def _alive(self, key: str) -> Optional[Tuple[str, float]]:
        item = self._d.get(key)
        if item and item[1] <= time.time():
            self._d.pop(key, None)
            return None
        return item

    async def incr(self, key: str, ttl: int) -> int:
        item = self._alive(key)
        if item:
            self._d[key] = (str(int(item[0]) + 1), item[1])
            return int(item[0]) + 1
        self._d[key] = ("1", time.time() + ttl)
        return 1

    async def ttl(self, key: str) -> int:
        item = self._alive(key)
        return max(0, int(item[1] - time.time())) if item else 0

    async def get(self, key: str) -> Optional[str]:
        item = self._alive(key)
        return item[0] if item else None

    async def set(self, key: str, value: str, ttl: int) -> None:
        self._d[key] = (value, time.time() + ttl)

    async def delete(self, *keys: str) -> None:
        for k in keys:
            self._d.pop(k, None)


class Store:
    """Redis with a transparent in-memory fallback."""

    def __init__(self):
        self._mem = _Memory()
        self._redis = None
        self._redis_failed_at = 0.0

    def _client(self):
        if self._redis is None and time.time() - self._redis_failed_at > 30:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(config.REDIS_URL, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
            except Exception as e:  # pragma: no cover
                self._mark_failed(e)
        return self._redis

    def _mark_failed(self, err):
        log.warning("Redis unavailable for admin auth (%s), using in-memory state", err)
        self._redis = None
        self._redis_failed_at = time.time()

    async def _run(self, name: str, *args):
        client = self._client()
        if client is not None:
            try:
                if name == "incr":
                    key, ttl = args
                    pipe = client.pipeline()
                    pipe.incr(key)
                    pipe.ttl(key)
                    count, left = await pipe.execute()
                    if left < 0:  # first hit (or lost expiry): start the window
                        await client.expire(key, ttl)
                    return int(count)
                if name == "ttl":
                    return max(0, int(await client.ttl(args[0])))
                if name == "get":
                    return await client.get(args[0])
                if name == "set":
                    key, value, ttl = args
                    return await client.set(key, value, ex=ttl)
                if name == "delete":
                    return await client.delete(*args)
            except Exception as e:
                self._mark_failed(e)
        return await getattr(self._mem, name)(*args)

    async def incr(self, key, ttl): return await self._run("incr", key, ttl)
    async def ttl(self, key): return await self._run("ttl", key)
    async def get(self, key): return await self._run("get", key)
    async def set(self, key, value, ttl): return await self._run("set", key, value, ttl)
    async def delete(self, *keys): return await self._run("delete", *keys)


store = Store()


def client_ip(request: Request) -> str:
    if config.TRUST_PROXY_HEADERS:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _keys(username: str, ip: str):
    u = (username or "").strip().lower()[:100]
    return (f"login:fail:uip:{u}:{ip}", LIMIT_USER_IP), (f"login:fail:ip:{ip}", LIMIT_IP), (f"login:fail:user:{u}", LIMIT_USER)


async def ensure_login_allowed(username: str, ip: str) -> None:
    for key, limit in _keys(username, ip):
        raw = await store.get(key)
        if raw is not None and int(raw) >= limit:
            wait = await store.ttl(key) or LOCK_SECONDS
            raise HTTPException(status_code=429, detail="Too many attempts. Try again later.",
                                headers={"Retry-After": str(wait)})


async def register_login_failure(username: str, ip: str) -> None:
    for key, _ in _keys(username, ip):
        await store.incr(key, LOCK_SECONDS)


async def clear_login_failures(username: str, ip: str) -> None:
    await store.delete(_keys(username, ip)[0][0])


# ---- 2FA codes ----

async def save_2fa_code(username: str, code: str) -> None:
    await store.set(f"2fa:code:{username}", code, CODE_TTL)
    await store.delete(f"2fa:attempts:{username}")


async def check_2fa_code(username: str, code: str) -> str:
    """Returns 'ok' | 'missing' | 'wrong' | 'locked'. A correct code is consumed."""
    import hmac
    stored = await store.get(f"2fa:code:{username}")
    if stored is None:
        return "missing"
    if hmac.compare_digest(stored.encode(), (code or "").encode()):
        await store.delete(f"2fa:code:{username}", f"2fa:attempts:{username}")
        return "ok"
    attempts = await store.incr(f"2fa:attempts:{username}", CODE_TTL)
    if attempts >= CODE_MAX_ATTEMPTS:
        await store.delete(f"2fa:code:{username}", f"2fa:attempts:{username}")
        return "locked"
    return "wrong"

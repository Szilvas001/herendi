"""Udvarias HTTP-réteg a bejáráshoz.

- hostonkénti minimális késleltetés (settings: http.min_delay_sec),
- robots.txt tiszteletben tartása,
- lemez-cache típusonkénti élettartammal,
- 403/429/CAPTCHA esetén `BlockedError`: a bejárás az adott hoston leáll,
  a korlátozást nem kerüljük meg.
"""
from __future__ import annotations

import gzip
import hashlib
import logging
import threading
import time
import urllib.robotparser
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import requests

from . import settings

log = logging.getLogger(__name__)

GZIP_MAGIC = bytes([0x1F, 0x8B])   # .gz fájltörzs felismerése

BLOCK_MARKERS = ("cf-chl", "challenge-platform", "turnstile", "g-recaptcha", "hcaptcha",
                 "captcha", "unusual traffic", "access denied", "are you a robot")


class BlockedError(RuntimeError):
    """A forrás korlátozta a hozzáférést (403/429/CAPTCHA). Nem próbáljuk megkerülni."""


class NetworkError(RuntimeError):
    """A forrás hálózati szinten nem érhető el (DNS, proxy, időtúllépés)."""


class DisallowedError(RuntimeError):
    """A robots.txt tiltja az URL-t."""


@dataclass
class Response:
    url: str
    status: int
    text: str
    from_cache: bool = False
    content: bytes | None = None


@dataclass
class Fetcher:
    cache_dir: Path | None = None
    min_delay: float | None = None
    user_agent: str | None = None
    respect_robots: bool | None = None
    offline_dir: Path | None = None           # tesztekhez / demóhoz: URL -> fájl
    session: requests.Session = field(default_factory=requests.Session)
    stats: dict = field(default_factory=lambda: {"fetched": 0, "cache_hit": 0, "failed": 0,
                                                 "blocked": 0, "disallowed": 0, "bytes": 0})

    def __post_init__(self):
        http = settings.get("http")
        self.cache_dir = Path(self.cache_dir or settings.path("cache_dir"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_delay = http["min_delay_sec"] if self.min_delay is None else self.min_delay
        self.user_agent = self.user_agent or http["user_agent"]
        self.respect_robots = http["respect_robots_txt"] if self.respect_robots is None else self.respect_robots
        self.timeout = http["timeout_sec"]
        self.retries = http["retries"]
        self._last: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._blocked_hosts: set[str] = set()
        self._lock = threading.Lock()

    # -- cache ---------------------------------------------------------------
    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / f"{hashlib.sha1(url.encode()).hexdigest()}.gz"

    def _cache_get(self, url: str, ttl: float) -> bytes | None:
        if ttl <= 0:
            return None
        p = self._cache_path(url)
        if p.exists() and time.time() - p.stat().st_mtime < ttl:
            try:
                return gzip.decompress(p.read_bytes())
            except OSError:
                return None
        return None

    def _cache_put(self, url: str, data: bytes) -> None:
        try:
            self._cache_path(url).write_bytes(gzip.compress(data))
        except OSError:
            pass

    # -- policy --------------------------------------------------------------
    def _throttle(self, host: str) -> None:
        with self._lock:
            wait = self._last.get(host, 0) + self.min_delay - time.monotonic()
            self._last[host] = max(time.monotonic(), self._last.get(host, 0) + self.min_delay)
        if wait > 0:
            time.sleep(wait)

    def allowed(self, url: str) -> bool:
        if not self.respect_robots or self.offline_dir:
            return True
        parsed = urlparse(url)
        root = f"{parsed.scheme}://{parsed.netloc}"
        if root not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                resp = self.session.get(root + "/robots.txt", timeout=self.timeout,
                                        headers={"User-Agent": self.user_agent})
                if resp.status_code == 200:
                    rp.parse(resp.text.splitlines())
                    self._robots[root] = rp
                else:
                    self._robots[root] = None   # nincs robots.txt -> engedélyezett
            except requests.RequestException as exc:
                log.warning("robots.txt nem olvasható (%s): %s", root, exc)
                self._robots[root] = None
        rp = self._robots[root]
        return True if rp is None else rp.can_fetch(self.user_agent, url)

    def is_blocked(self, url: str) -> bool:
        return urlparse(url).netloc in self._blocked_hosts

    @staticmethod
    def _maybe_gunzip(data: bytes) -> bytes:
        """.gz kiterjesztesu torzs (pl. sitemap_1_17.xml.gz) kibontasa szovegkent olvasashoz."""
        if data[:2] == GZIP_MAGIC:
            try:
                return gzip.decompress(data)
            except OSError:
                return data
        return data

    @staticmethod
    def block_marker(text: str) -> str | None:
        low = (text or "")[:200_000].lower()
        return next((m for m in BLOCK_MARKERS if m in low), None)

    # -- public --------------------------------------------------------------
    def get(self, url: str, ttl: float = 0, binary: bool = False) -> Response | None:
        """GET cache-sel. None: 404/410 vagy tartós hiba. BlockedError: korlátozás."""
        if self.offline_dir:
            return self._offline(url, binary)
        host = urlparse(url).netloc
        if host in self._blocked_hosts:
            raise BlockedError(f"{host} korábban korlátozta a hozzáférést ebben a futásban")
        cached = self._cache_get(url, ttl)
        if cached is not None:
            self.stats["cache_hit"] += 1
            return Response(url, 200,
                            "" if binary else self._maybe_gunzip(cached).decode("utf-8", "ignore"),
                            True, cached if binary else None)
        if not self.allowed(url):
            self.stats["disallowed"] += 1
            raise DisallowedError(f"robots.txt tiltja: {url}")

        last_exc = None
        net_fail = False
        for attempt in range(self.retries):
            self._throttle(host)
            try:
                resp = self.session.get(url, timeout=self.timeout,
                                        headers={"User-Agent": self.user_agent,
                                                 "Accept-Language": "hu-HU,hu;q=0.9,en;q=0.6"})
            except requests.RequestException as exc:
                last_exc = exc
                net_fail = True
                time.sleep(min(30, 2 ** attempt))
                continue
            net_fail = False
            waf = resp.headers.get("x-amzn-waf-action") or ("Incapsula" in (resp.text or "")[:3000] and "incapsula")
            if waf or (resp.status_code == 202 and not resp.content):
                # bot-védelmi kihívás (pl. AWS WAF challenge, Incapsula): nem oldjuk meg, nem kerüljük meg
                self.stats["blocked"] += 1
                self._blocked_hosts.add(host)
                raise BlockedError(f"bot-védelmi kihívás ({waf or 'HTTP 202 üres válasz'}): {url}")
            if resp.status_code in (403, 429):
                self.stats["blocked"] += 1
                if settings.get("http.stop_on_block", True):
                    self._blocked_hosts.add(host)
                raise BlockedError(f"HTTP {resp.status_code}: {url}")
            if resp.status_code in (404, 410):
                self.stats["failed"] += 1
                return Response(url, resp.status_code, "")
            if resp.status_code >= 500:
                last_exc = RuntimeError(f"HTTP {resp.status_code}")
                time.sleep(min(30, 2 ** attempt))
                continue
            data = resp.content
            text_body = ""
            if not binary:
                text_body = (self._maybe_gunzip(data).decode("utf-8", "ignore")
                             if data[:2] == GZIP_MAGIC else resp.text)
                marker = self.block_marker(text_body)
                if marker:
                    self.stats["blocked"] += 1
                    self._blocked_hosts.add(host)
                    raise BlockedError(f"CAPTCHA/anti-bot oldal ({marker}): {url}")
            self.stats["fetched"] += 1
            self.stats["bytes"] += len(data)
            if ttl > 0 and resp.status_code == 200:
                self._cache_put(url, data)
            return Response(resp.url, resp.status_code, "" if binary else text_body, False,
                            data if binary else None)
        self.stats["failed"] += 1
        log.warning("Sikertelen letöltés %s: %s", url, last_exc)
        if net_fail:
            why = "proxy/tűzfal 403 Forbidden" if "403" in str(last_exc) else type(last_exc).__name__
            raise NetworkError(f"{host} nem érhető el: {why}")
        return None

    def _offline(self, url: str, binary: bool) -> Response | None:
        key = hashlib.sha1(url.encode()).hexdigest()
        tail = url.rstrip("/").split("/")[-1].split("?")[0]
        candidates = [self.offline_dir / key, self.offline_dir / f"{key}.html", self.offline_dir / tail]
        mapping = self.offline_dir / "urls.txt"      # "url<TAB>fájlnév" sorok
        if mapping.exists():
            for line in mapping.read_text(encoding="utf-8").splitlines():
                if "\t" in line:
                    u, f = line.split("\t", 1)
                    if u.strip() == url:
                        candidates.insert(0, self.offline_dir / f.strip())
        for p in candidates:
            if p.is_file():
                data = p.read_bytes()
                self.stats["cache_hit"] += 1
                return Response(url, 200, "" if binary else data.decode("utf-8", "ignore"), True,
                                data if binary else None)
        return Response(url, 404, "")

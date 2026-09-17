"""HTTP réteg: lemez-cache, retry, anti-bot detektálás, offline mód."""
import gzip
import hashlib
import logging
import random
import threading
import time
from pathlib import Path

import requests

from . import config

log = logging.getLogger(__name__)


def _key(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8", "ignore")).hexdigest()


class HttpClient:
    """Egyszerű, cache-elő GET kliens.

    offline_dir megadásakor nem megy ki a hálózatra: a lementett HTML-eket
    olvassa (tesztelés / demó futtatás internet nélkül).
    """

    def __init__(self, cache_dir: Path | None = None, ttl_sec: int | None = None,
                 delay: float | None = None, offline_dir: Path | None = None):
        self.cache_dir = Path(cache_dir or config.CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = config.CACHE_TTL_SEC if ttl_sec is None else ttl_sec
        self.delay = config.REQUEST_DELAY if delay is None else delay
        self.offline_dir = Path(offline_dir) if offline_dir else None
        self._local = threading.local()
        self._lock = threading.Lock()
        self.stats = {"cache_hit": 0, "fetched": 0, "failed": 0, "antibot": 0}

    @property
    def session(self) -> requests.Session:
        """Szálanként külön requests.Session (a ThreadPool miatt)."""
        sess = getattr(self._local, "session", None)
        if sess is None:
            sess = requests.Session()
            self._local.session = sess
        return sess

    def _bump(self, key: str) -> None:
        with self._lock:
            self.stats[key] += 1

    # -- cache ---------------------------------------------------------------
    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / f"{_key(url)}.html.gz"

    def _cache_read(self, url: str) -> str | None:
        if self.ttl < 0:          # --no-cache: mindig friss letöltés
            return None
        p = self._cache_path(url)
        if not p.exists():
            return None
        if (time.time() - p.stat().st_mtime) > self.ttl:
            return None
        try:
            with gzip.open(p, "rt", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except OSError:
            return None

    def _cache_write(self, url: str, text: str) -> None:
        try:
            with gzip.open(self._cache_path(url), "wt", encoding="utf-8", errors="ignore") as f:
                f.write(text or "")
        except OSError:
            pass

    # -- offline -------------------------------------------------------------
    def _offline_read(self, url: str) -> str | None:
        """Offline módban a fájlnév az URL sha1-e, vagy az URL utolsó szegmense."""
        cand = [self.offline_dir / f"{_key(url)}.html"]
        tail = url.rstrip("/").split("/")[-1].split("?")[0]
        if tail:
            cand.append(self.offline_dir / tail)
        if "listings/index.php" in url:
            cand.append(self.offline_dir / "search.html")
        for p in cand:
            if p.exists():
                return p.read_text(encoding="utf-8", errors="ignore")
        return None

    # -- anti-bot ------------------------------------------------------------
    @staticmethod
    def looks_blocked(html: str) -> str | None:
        h = (html or "").lower()
        for marker in ("cf-chl", "challenge-platform", "turnstile", "captcha",
                       "unusual traffic", "access denied"):
            if marker in h:
                return marker
        return None

    # -- publikus ------------------------------------------------------------
    def get(self, url: str) -> str | None:
        if self.offline_dir:
            return self._offline_read(url)

        cached = self._cache_read(url)
        if cached is not None:
            self._bump("cache_hit")
            return cached

        last_err: Exception | None = None
        for attempt in range(config.HTTP_RETRIES):
            try:
                resp = self.session.get(url, headers=config.HEADERS,
                                        timeout=config.HTTP_TIMEOUT)
                if resp.status_code in (403, 429) or resp.status_code >= 500:
                    raise RuntimeError(f"HTTP {resp.status_code}")
                if resp.status_code != 200:
                    log.debug("HTTP %s (nem retry-zunk): %s", resp.status_code, url)
                    self._bump("failed")
                    return None

                html = resp.text or ""
                marker = self.looks_blocked(html)
                if marker:
                    self._bump("antibot")
                    log.warning("Anti-bot oldal (%s): %s", marker, url)
                    return None

                self._cache_write(url, html)
                self._bump("fetched")
                if self.delay:
                    time.sleep(self.delay)
                return html
            except Exception as exc:  # hálózati hiba, 403/429/5xx
                last_err = exc
                time.sleep(min(10.0, 0.8 * (2 ** attempt) + random.random() * 0.3))

        self._bump("failed")
        log.debug("Sikertelen letöltés: %s (%s)", url, last_err)
        return None

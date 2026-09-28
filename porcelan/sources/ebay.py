"""eBay Browse API (hivatalos) – amerikai AKTÍV kínálat összehasonlító adatnak.

Kulcsok: EBAY_CLIENT_ID, EBAY_CLIENT_SECRET környezeti változók (eBay Developer
Program, "Application access" OAuth). A Browse API csak aktív hirdetést ad:
az itt gyűjtött ár `asking_active` típusú, NEM eladási ár. Lezárt eladásokhoz a
Marketplace Insights API külön jogosultságot igényel; addig CSV-importtal
(`python -m porcelan import-prices`) adhatók hozzá realizált árak.
"""
from __future__ import annotations

import base64
import logging
import os

import requests

from .. import settings
from .base import Source

log = logging.getLogger(__name__)
TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"


class EbaySource(Source):
    name = "ebay"
    market = "US"

    def __init__(self):
        self.cfg = settings.get("ebay")

    def available(self) -> tuple[bool, str]:
        if not (os.environ.get("EBAY_CLIENT_ID") and os.environ.get("EBAY_CLIENT_SECRET")):
            return False, "Nincs EBAY_CLIENT_ID / EBAY_CLIENT_SECRET a környezetben."
        return True, ""

    def _token(self, session) -> str:
        cred = f"{os.environ['EBAY_CLIENT_ID']}:{os.environ['EBAY_CLIENT_SECRET']}".encode()
        resp = session.post(TOKEN_URL, timeout=20, headers={
            "Authorization": "Basic " + base64.b64encode(cred).decode(),
            "Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"})
        resp.raise_for_status()
        return resp.json()["access_token"]

    def fetch_active(self, max_items_per_query: int = 1000, session=None):
        """Generátor: (query, item_summary dict). Lapoz, amíg van `next`."""
        ok, why = self.available()
        if not ok:
            raise RuntimeError(why)
        session = session or requests.Session()
        headers = {"Authorization": f"Bearer {self._token(session)}",
                   "X-EBAY-C-MARKETPLACE-ID": self.cfg["marketplace"]}
        for q in self.cfg["queries"]:
            offset, got = 0, 0
            while got < max_items_per_query:
                resp = session.get(SEARCH_URL, headers=headers, timeout=30,
                                   params={"q": q, "limit": 200, "offset": offset,
                                           "filter": "buyingOptions:{FIXED_PRICE}"})
                if resp.status_code == 429:
                    log.warning("eBay API kvóta elérve; leállás.")
                    return
                resp.raise_for_status()
                data = resp.json()
                items = data.get("itemSummaries", [])
                for it in items:
                    yield q, it
                got += len(items)
                if not data.get("next") or not items:
                    break
                offset += len(items)

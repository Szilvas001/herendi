"""Budgeted Hungarian collectibles discovery. No paid model calls.

Run: python -m elemzes.hungarian_scan --seconds 240 --pages 2 --details 36
Network failures are explicit; cached observations are never labelled live.
"""
import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from porcelan import config
from porcelan.httpclient import HttpClient
from porcelan.vatera import search_url
from porcelan.parsing import parse_listing

TERMS = ['herendi nyúl', 'herendi figura', 'herendi apponyi', 'zsolnay eozin',
         'zsolnay medve', 'zsolnay teknős', 'hollóházi szász', 'gorka váza',
         'tungsram ecc83', 'tungsram e88cc', 'ajka kristály', 'pécsi kesztyű']

def seller_description(html):
    text = BeautifulSoup(html, 'html.parser').get_text(' ', strip=True)
    match = re.search(r'Eladó leírása a termékről(.*?)Szállítási feltételek', text)
    return match.group(1).strip() if match else ''

def product_brand(title):
    # Never derive brand from navigation or recommendations in the page body.
    return next((b for b in ['Herendi','Zsolnay','Tungsram','Hollóházi','Gorka','Ajka']
                 if b.casefold() in title.casefold()), 'Ismeretlen')

def run(seconds=240, pages=2, details=36):
    if seconds <= 0 or pages < 1 or details < 0:
        raise ValueError('Invalid budget')
    start = time.monotonic()
    config.HTTP_TIMEOUT = min(12, seconds)
    config.HTTP_RETRIES = 1
    client = HttpClient(ttl_sec=-1, delay=.25)
    rows, searches, errors = {}, [], []
    def available():
        return time.monotonic() - start < seconds
    for page in range(1, pages + 1):
        for term in TERMS:
            if not available():
                break
            url = search_url(term, page)
            html = client.get(url)
            searches.append({'term': term, 'page': page, 'url': url, 'ok': bool(html)})
            if not html:
                errors.append(url)
                continue
            for el in BeautifulSoup(html, 'html.parser').select('[data-product-id][data-gtm-price]'):
                a = el.select_one('a.product_link[href]')
                if not a or el.get('data-expired') != '0' or el.get('data-gtm-auction-type') != 'fix_price':
                    continue
                try:
                    price = float(el['data-gtm-price'])
                except (ValueError, TypeError):
                    continue
                if price <= 0:
                    continue
                key = el['data-product-id']
                rows.setdefault(key, {'id': key, 'title': el.get('data-gtm-name', ''),
                    'price_huf': price, 'url': urljoin(config.BASE_URL, a['href']),
                    'term': term, 'observed_at': datetime.now(timezone.utc).isoformat(),
                    'evidence': 'live_search_card', 'detail': None})
            print(term, page, len(rows), flush=True)
    # Round-robin across search terms prevents cheap accessories crowding out porcelain.
    groups = [[r for r in sorted(rows.values(), key=lambda x:x['price_huf']) if r['term']==t] for t in TERMS]
    shortlist = []
    for i in range(max([len(g) for g in groups], default=0)):
        for group in groups:
            if i < len(group):
                shortlist.append(group[i])
    for row in shortlist[:details]:
        if not available():
            break
        html = client.get(row['url'])
        if html:
            row['detail'] = parse_listing(row['url'], html)
            row['seller_description'] = seller_description(html)
            if row['detail']:
                row['detail']['brand'] = product_brand(row['title'])
                row['detail']['description'] = row['seller_description']
                row['detail']['decor_hints'] = ''  # page-wide legacy hints are unsafe
                row['detail']['damage_flags'] = 'manual_review_required'
            row['detail_text'] = BeautifulSoup(html, 'html.parser').get_text(' ', strip=True)[-16000:]
        else:
            errors.append(row['url'])
    result = {'checked_at':datetime.now(timezone.utc).isoformat(), 'seconds':round(time.monotonic()-start,1),
        'budget_seconds':seconds, 'scope':'Targeted Vatera sample; not whole-market coverage',
        'searches':searches, 'errors':errors, 'http':client.stats, 'candidates':list(rows.values())}
    dest=Path('out/hungarian_scan.json'); dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('saved', dest, len(rows), flush=True)
    return result

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seconds', type=int, default=240)
    p.add_argument('--pages', type=int, default=2)
    p.add_argument('--details', type=int, default=36)
    a=p.parse_args(); run(a.seconds,a.pages,a.details)

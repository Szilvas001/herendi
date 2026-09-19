"""Live first-page screening; run from repo root with PYTHONPATH=."""
import json,re
from pathlib import Path
from bs4 import BeautifulSoup
from porcelan.httpclient import HttpClient
from porcelan.vatera import search_url, extract_product_links
from porcelan import config
from elemzes.likvid_analyze import norm,RULES,tube_model
from elemzes.candidate_filter import screening_reason
Path("out/review").mkdir(parents=True, exist_ok=True)
c=HttpClient(); rows={}; links=set(); failed_terms=[]
for term in config.LIKVID_SEARCH_TERMS:
 h=c.get(search_url(term))
 if not h:
  failed_terms.append(term)
  continue
 links.update(extract_product_links(h))
 s=BeautifulSoup(h,'html.parser')
 for el in s.select('[data-product-id][data-gtm-price]'):
  a=el.select_one('a.product_link[href]')
  if not a:continue
  title=el.get('data-gtm-name',''); t=norm(title)
  try:price=int(float(el['data-gtm-price']))
  except ValueError:continue
  if price<1000 or el.get('data-expired')!='0' or el.get('data-gtm-auction-type')!='fix_price':continue
  if any(re.search(r'\b'+re.escape(cue)+r'\b',t) for cue in config.LIKVID_EXCLUDE_CUES+config.LIKVID_NON_ITEM_CUES):continue
  tm=tube_model(t) if 'tungsram' in t else None
  rule=next((r for r in RULES if re.search(r[1],t)),None)
  if not tm and not rule:continue
  model='Tungsram '+tm.upper() if tm else rule[0]
  if screening_reason(title, model):continue
  rows[el['data-product-id']]=dict(listing_id=el['data-product-id'],title=title,url=a['href'],price_huf=price,model=model)
by={}
for row in sorted(rows.values(),key=lambda r:r['price_huf']):
 by.setdefault(row['model'],[])
 if len(by[row['model']])<2:by[row['model']].append(row)
selected=[r for group in by.values() for r in group]
Path('out/review/search_candidates.json').write_text(json.dumps(selected,ensure_ascii=False,indent=2))
print('recognized fixed candidates',len(rows),'model groups',len(by),'shortlist',len(selected))

# Detailed check of the two lowest advertised prices per recognized model.
# This is a screening sample, not a claim that the whole marketplace was valued.
from concurrent.futures import ThreadPoolExecutor
from porcelan.parsing import parse_listing
from datetime import datetime, timezone
config.apply_profile('likvid')

def detail(row):
    html=c.get(row['url'])
    record=parse_listing(row['url'],html or '')
    if record:
        soup=BeautifulSoup(html,'html.parser')
        text=soup.get_text(' ',strip=True)
        desc=re.search(r'Eladó leírása a termékről (.*?) Szállítási feltételek',text)
        if desc:record['description']=desc.group(1)[:2000]
    return {**row,'record':record}

checked=[]
with ThreadPoolExecutor(max_workers=4) as pool:
    for i,row in enumerate(pool.map(detail,selected),1):
        checked.append(row)
        if i%20==0:print('detail',i,'/',len(selected),flush=True)
result={'checked_at':datetime.now(timezone.utc).isoformat(),
        'search_terms':len(config.LIKVID_SEARCH_TERMS),'pages_per_term':1,
        'unique_product_links':len(links),'failed_search_terms':failed_terms,
        'recognized_fixed_candidates':len(rows),'model_groups':len(by),
        'method':'Two cheapest advertised fixed-price candidates per regex model; not a valuation',
        'candidates':checked}
Path('out/review/screened.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print('saved',len(checked),'details; HTTP',c.stats)

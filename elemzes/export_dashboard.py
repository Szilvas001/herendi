"""Build a shareable report and standalone dashboard from reviewed evidence.

No inferred model matching or fabricated sold data. Analyst inputs are explicit.
"""
import json
from pathlib import Path
from elemzes.decision_model import Costs, scenario

ROOT = Path(__file__).resolve().parents[1]

def build():
    source=ROOT/'riport/hungarian-top3.json'
    report=json.loads(source.read_text(encoding='utf-8'))
    scan_path=ROOT/'out/hungarian_scan.json'
    if scan_path.exists():
        scan=json.loads(scan_path.read_text(encoding='utf-8'))
        observed={r['url']:r for r in scan['candidates']}
        selected=[]
        for item in report['items']:
            r=observed.get(item['url'])
            if not r or not r.get('detail') or r['detail']['price_huf'] != item['purchase_huf']:
                raise ValueError('Reviewed price does not match observed detail: '+item['name'])
            selected.append({k:r['detail'].get(k) for k in ['listing_id','title','url','price_huf','sale_type','availability','end_time']})
        audit={k:scan[k] for k in ['checked_at','seconds','budget_seconds','scope','searches','errors','http']}
        audit['candidate_count']=len(scan['candidates'])
        audit['selected']=selected
        (ROOT/'riport/hungarian-scan-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if len(report['items']) != 3:
        raise ValueError('Exactly three reviewed candidates required')
    lines=['# Hungarian Finds — három exportjelölt', '', report['warning'], '',
           f"Ellenőrzés: {report['checked_at']}", '', report['method'], '',
           '## Összehasonlító táblázat', '',
           'Eladási árak: nem kalibrált tervezési forgatókönyvek. Az eladási idő a meghirdetéstől induló feltételezés, nem mért átlag. Akár egy éven túl is készleten maradhatnak.', '',
           '| Termék | Vételár Ft | EU eladási ár: stressz / alap / magas EUR | EU fedezet Ft (alap) | ROI (alap / stressz) | USA ROI (alap) | Időbecslés nap | 30% ROI vételi plafon Ft |',
           '|---|---:|---:|---:|---:|---:|---|---:|']
    for row in report['items']:
        costs=Costs(**row['costs_huf'],fee_rate=.18,risk_rate=.10)
        results={k:scenario(row['purchase_huf'],v*395,costs) for k,v in row['sale_eur'].items()}
        usa=Costs(**{**row['costs_huf'],'outbound':row['costs_huf']['outbound']+15000},fee_rate=.18,risk_rate=.10)
        us=scenario(row['purchase_huf'],row['sale_eur']['base']*395,usa)
        row['computed_eu']=results; row['computed_us_base']=us
        b=results['base']; s=results['stress']; prices=row['sale_eur']
        lines.append(f"| [{row['name']}]({row['url']}) | {row['purchase_huf']} | {prices['stress']} / {prices['base']} / {prices['high']} | {b['profit_huf']} | {b['roi_pct']}% / {s['roi_pct']}% | {us['roi_pct']}% | {row['days']} | {b['max_purchase_huf']} |")
    lines += ['', '## Költségek és döntési küszöb', '',
        '395 HUF/EUR tervezési árfolyam; 18% díj és 10% kockázati tartalék az eladási árból. Ezek nem aktuális díjajánlatok. ROI = (eladási ár × 0,72 − vételár − fix költségek) / (vételár + fix költségek). Postát az eladó fizet. Adó, munkaidő és tőkeköltség nincs levonva.', '',
        'USA: ugyanaz az EUR-ban kifejezett bevételi feltételezés, plusz 15 000 Ft/tétel érzékenységi tartalék. Ez nem vám- vagy postai árajánlat; útvonal, biztosítás, importköltség és vevő/eladó tehermegosztás nélkül USA-vételi döntés nem hozható. A magasabb amerikai eladási ár nincs igazolva.', '',
        'Vételi kapu: pontos modell/dekor/méret és állapot egyezése; működés vagy sérülés ellenőrzése; legalább öt releváns lezárt eladás; pozitív stressz-fedezet és legalább 30% alap-ROI. Jelenleg egyik jelöltnél sincs teljesítve minden kapu. A sorrend kutatási prioritás, nem biztos profit szerinti rangsor.', '']
    for r in report['items']:
        lines += [f"## {r['name']}", '',r['thesis'],'',r['condition'],'',r['price_basis'],'',
            f"Időterv: {r['days']} nap; magas áron {r['days_high']} nap. Alacsony bizonyosságú kereskedői munkahipotézis, nincs hozzá követett eladási kohorsz.", '',
            'Fix költségek (Ft): '+', '.join(f'{k}={v}' for k,v in r['costs_huf'].items()), '',
            'Források:']
        lines += [f"- [{s['label']}]({s['url']}) — {s['kind']}" for s in r['sources']]
        lines += ['']
    lines += ['## Lefedettség és következő futás','',json.dumps(report['coverage'],ensure_ascii=False), '',
        '12 célzott keresőkifejezés, két oldal/kifejezés, csoportonként ár szerint kiválasztott összesen 30 részletes ellenőrzés. A keresőkártyák nem mind releváns termékek. Nem teljes Vatera- vagy hazai piactér-lefedés. Jófogás és Galéria Savaria webes keresése nem adott kellően ellenőrizhető konkrét termékadatot ebben a keretben; onnan nincs vételi jelölt.', '',
        'A scraper nem hív fizetős LLM API-t. A riport az asszisztens forrásértékelésével és determinisztikus számítással készül; külön Astra API-futtatás nem történt. A napi keretből hátralévő mennyiséget a program nem látja.', '',
        'Új gyűjtés: `python -m elemzes.hungarian_scan --seconds 210 --pages 2 --details 30`. A nyers találatokból kézzel ellenőrzött jelöltekkel frissítsd a `hungarian-top3.json` fájlt, majd `python -m elemzes.export_dashboard`.', '',
        'A futás keresési URL-jei, HTTP-statisztikái és kiválasztott termékrekordjai: `hungarian-scan-audit.json`.', '',
        '## Dashboard', '',
        'A `dashboard/index.html` közvetlenül böngészőben megnyitható. Árforgatókönyv, EU/USA összevetés, díj- és tartalékállítás, ROI, vételi plafon és JSON-export. A felület SaaS prototípus; nincs még éles többfelhasználós bejelentkezés, előfizetés vagy automatizált szolgáltatás. A SaaS-terv a `dashboard/README.md` fájlban található.']
    (ROOT/'riport/hungarian-top3.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    data=json.dumps(report,ensure_ascii=False,indent=2)
    (ROOT/'dashboard/data.js').write_text('window.REPORT = '+data.replace('<','\\u003c')+';\n',encoding='utf-8')
    print('Built report and dashboard for', len(report['items']), 'candidates')

if __name__=='__main__':
    build()

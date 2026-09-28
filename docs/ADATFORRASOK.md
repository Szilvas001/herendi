# Adatforrások, ártípusok és a tanítóadat hiánya

Utolsó frissítés: 2026-09-28.

## 1. Ártípusok – mit jelent egy ár

| `price_type` | Jelentés | Tanításra | Honnan jön |
|---|---|---|---|
| `realized_sale` | ténylegesen realizált eladási ár | **igen** (elsődleges) | importált CSV (saját eladások, Vatera „elkelt” jelzés fix áron) |
| `auction_hammer` | aukciósházi leütési ár; a vevői jutalék (`buyer_premium_rate`) külön mezőben, a célváltozó a vevő által fizetett ár | **igen** | importált CSV (Axioart / BÁV / Darabanth / LiveAuctioneers eredmények) |
| `auction_final_bid` | piactéri aukció záró licitje, licitekkel lezárva | **igen** (külön jelölve) | a crawler automatikusan rögzíti a lejárt Vatera-aukciók újraellenőrzésekor |
| `asking_active` | aktív hirdetés kínálati ára | csak tartalékként, **kísérleti** jelöléssel | Vatera, Jófogás, eBay Browse API, régi riportok |
| `auction_current_bid` | futó aukció aktuális licitje | **nem** | crawler |
| `auction_start_price` | kikiáltási ár | **nem** | crawler, régi riportok |

Szabályok a kódban (`porcelan/dataset.py`, `porcelan/crawler.py`):
- Piaconként legalább 200 realizált ár kell ahhoz, hogy a célváltozó realizált ár legyen; különben a modell kínálati áron tanul, és a manifest, az értékelés és a dashboard is **KÍSÉRLETI**-nek jelöli.
- Az eltűnt hirdetés `disappeared` státuszt kap, és **soha nem lesz eladás**. Eltűnt-jelölés csak teljes (minden keresés a lapozás végéig ért) bejárás után történik.
- A lejárt, licit nélküli aukció `ended`, nem eladás.
- Az amerikai célváltozó USD-ben van. Az US-érték nem a magyar becslés átváltása, hanem külön kvantilisfej becsli, amely az amerikai adatokon tanul.
- Minden ár-rekord megőrzi a forrást, az azonosítót, az időpontot, az ártípust, a címet, a leírást és a `provenance` mezőt (fájl, sor, bejárás-azonosító).
- A duplikátumokat a normalizált cím + eladó (újrahirdetés) szerint szűrjük. A csoportképzés a közös képet (sha256, pHash) és a közel azonos címet is figyelembe veszi, így ugyanaz a tárgy nem kerülhet több halmazba.

## 2. Ténylegesen rendelkezésre álló adat (a repóban, 2026-09-16/19-i élő futásokból)

| Adat | Darab | Ártípus | Megjegyzés |
|---|---:|---|---|
| Vatera fix áras hirdetések (`riport/fix-aras.md`) | 1640 | `asking_active` | cím, ár, URL; leírás és kép nélkül |
| Vatera alkuképes hirdetések (`riport/alkukepes.md`) | 475 | `asking_active` | irányár |
| Vatera aukciók (`riport/aukcio.md`) | 206 | `auction_start_price` | 195 kikiáltási ár; nem tanítóadat |
| Kiszűrt hirdetések (`riport/kiszurt.md`) | 31 | – | elutasítottként importálva |
| Részletes termékoldalak (`riport/decision-evidence.json`) | 14 Herendi/Zsolnay | `asking_active` | leírással, készletjelzéssel (2026-09-19) |
| eBay aktív hirdetések PicClicken át (`elemzes/comps.json`) | 119 US + 36 EU | `asking_active` | kulcsonként legfeljebb 7 minta; a lekérés dátuma nincs tárolva (2026-09-16-ra becsülve) |

**Realizált eladási ár: 0. Leütési ár: 0. Letöltött kép: 0.**

A duplikátumszűrés után 1794 tanítósor maradt (HU: 1677, US: 117), 1623 csoportban.

## 3. Miért nem gyűlt friss adat ebben a munkamenetben

A fejlesztői konténer kimenő forgalmát a környezet hálózati szabályzata korlátozza. A következő hostok 403-at adtak (proxy CONNECT elutasítva):
`www.vatera.hu`, `img.vatera.hu`, `www.jofogas.hu`, `picclick.com`, `www.ebay.com`, `huggingface.co`, `www.liveauctioneers.com`, `axioart.com`, `www.bav.hu`, `www.darabanth.com`, `www.worthpoint.com`, `web.archive.org`.
Elérhető volt a PyPI és a GitHub release-letöltés: innen jöttek a CLIP-súlyok, SHA-256 ellenőrzéssel.

Az élő bejárás ezért `failed` állapotban, folytatható módon áll meg („www.vatera.hu nem érhető el: proxy/tűzfal 403 Forbidden”). A dashboard ezt hibás adatforrásként jelzi. Egy olyan gépen, ahonnan a Vatera elérhető, ugyanaz a parancs (`python -m porcelan crawl`) innen folytatja.

## 4. Felkutatott, felhasználható adatforrások

| Forrás | Piac | Ártípus | Hozzáférés | Állapot a kódban |
|---|---|---|---|---|
| **Vatera** lezárult aukciói (saját bejárásból) | HU | `auction_final_bid` | nyilvános termékoldal, robots.txt tiszteletben tartva | **kész**: a crawler a lejárt aukciókat újraellenőrzi, és licittel zárult aukciónál rögzíti a záró licitet. Idővel ez a legnagyobb magyar tanítóforrás. |
| Vatera aktív kínálat | HU | `asking_active` | nyilvános keresés és kategória | **kész** (teljes lapozás, névváltozatok, kategóriák, inkrementális) |
| Vatera tömeges API (PST/SOAP) | HU | – | eladói feltöltésre szolgál, nem kínálat-lekérdezésre | nem használható kínálatgyűjtésre (a Vatera súgója alapján) |
| **Axioart** aukciós archívum (Darabanth, BÁV és mások) | HU | `auction_hammer` | részben bejelentkezéshez kötött; a felhasználási feltételeket ellenőrizni kell | CSV-importtal (`import-prices`); saját scraper nincs |
| **LiveAuctioneers** Price Results (kb. 2745 Herend eredmény) | US | `auction_hammer` | nyilvános árarchívum; automatikus gyűjtés előtt ellenőrizni kell a felhasználási feltételeket | CSV-importtal |
| eBay Browse API (hivatalos) | US | `asking_active` | ingyenes fejlesztői kulcs | **kész** (`import-ebay`, `EBAY_CLIENT_ID/SECRET`) |
| eBay Marketplace Insights API (eladott tételek) | US | `realized_sale` | Limited Release, új fejlesztőknek zárt | nem elérhető; Terapeak-exportból CSV-import lehetséges |
| Jófogás | HU | `asking_active` | nyilvános apróhirdetés | adapter kész (`jofogas.enabled`), élesben nem ellenőrzött |
| Saját vásárlások/eladások | HU/US | `realized_sale` | saját adat | CSV-importtal – ez a legjobb validációs adat az ajánlások találati pontosságához |

Az ár-CSV formátuma: `config/prices.example.csv`. Kitalált vagy becsült árat nem szabad importálni; az importer az ismeretlen ártípust elutasítja.

## 5. Mi kell a „validált” státuszhoz

A `[validation]` beállítások szerint piaconként: realizált ár a célváltozó, gyártónként legalább 50 realizált tesztminta, MdAPE ≤ 35%, a 80%-os intervallum tényleges lefedettsége 70–90% között, és a választott modell jobb a csoportmedián-baseline-nál. Időbeli teszthez legalább 30 napnyi megfigyelés kell. Reális út odáig:

1. Élő Vatera-bejárás naponta (vagy óránként a relevánsakra). Ekkor 4–8 hét alatt több száz Herendi/Zsolnay `auction_final_bid` gyűlik.
2. Axioart- és LiveAuctioneers-eredmények kézi vagy engedélyezett exportja CSV-be (Herendi, Zsolnay; 2–3 év).
3. Képek letöltése (`python -m porcelan images`): ettől a képi ág is tanul.
4. Újratanítás (`python -m porcelan train`): ha a feltételek teljesülnek, a státusz automatikusan „validált” lesz.

Források:
- eBay Marketplace Insights hozzáférés: [eBay Community](https://community.ebay.com/t5/eBay-APIs-Talk-to-your-fellow/Marketplace-Insights-API-access/td-p/34838736/), [apis.io leírás](https://apis.io/apis/ebay/marketplace-insights-api/), [Scavio blog (2026)](https://scavio.dev/blog/ebay-sold-listings-api-login-wall-2026)
- LiveAuctioneers Herend árarchívum: [price guide](https://www.liveauctioneers.com/price-guide/herend-porcelain-manufactory/26089/), [auction results](https://www.liveauctioneers.com/auction-results)
- Axioart / Darabanth / BÁV: [aukciós archívum](https://axioart.com/aukcios-archivum), [Darabanth porcelán tételek](https://axioart.com/aukcio/2024-05-23/466-gyorsarveres/porcelan-11808-12343?count=50&set_lang=hu&page=7), [BÁV aukció](https://bav-art.hu/esemenyek/2-online-aukcio/)
- Vatera tömeges feltöltés (nem lekérdező API): [Vatera súgó](https://www.vatera.hu/segitseg/?tutorial=registration)

# Hitelesítés és kérésfolyam

A repó parancssori scraper, nem felhasználói belépést kezelő webalkalmazás.
Nincs saját login, JWT, jelszóadatbázis, OAuth callback vagy jogosultsági middleware.

| Komponens | Kérés és adat | Hitelesítés / tárolás |
|---|---|---|
| [`run.py`](run.py), `main()` | CLI → scraper → CSV → opcionális AI → riport | Nincs alkalmazásszintű felhasználói hitelesítés |
| [`porcelan/vatera.py`](porcelan/vatera.py), `scrape()` | Keresőoldalak → termékoldalak → parser | Publikus Vatera GET kérések; nincs vásárlás vagy fiókbelépés |
| [`porcelan/httpclient.py`](porcelan/httpclient.py), `HttpClient.session/get()` | Szálanként `requests.Session`; retry, timeout, cache | A session cookie-kat memóriában kezelheti; a kód nem tölt be böngészős sütiket és nem ír cookie-jar fájlt |
| [`porcelan/config.py`](porcelan/config.py), `HEADERS` | User-Agent, Accept, Accept-Language | Nem hitelesítési fejlécek; a User-Agent nem bejelentkezés |
| [`porcelan/ai_review.py`](porcelan/ai_review.py), `_client()` | `anthropic.Anthropic()` | `ANTHROPIC_API_KEY` vagy `ANTHROPIC_AUTH_TOKEN` jelenlétét ellenőrzi; a hálózati hitelesítést az SDK végzi |
| `ai_review._call()` | Eladási típusonként, adagolva JSON hirdetésadatokat küld | Modell: `CLAUDE_MODEL`; streamelt válasz, strukturált JSON; a fallback-beta hibájánál sima hívásra vált |
| [`porcelan/storage.py`](porcelan/storage.py), [`porcelan/report.py`](porcelan/report.py) | CSV, JSON, Markdown fájlok | Nem adatbázis és nem külső riporttábla API |
| [`elemzes/likvid_analyze.py`](elemzes/likvid_analyze.py), `comps()` | PicClick publikus HTML `curl` lekéréssel | Nincs eBay OAuth és nincs lezárt eladásokhoz hitelesített hozzáférés |

## Konkrét folyamat

```python
# run.py (rövidítve)
client = HttpClient(...)
accepted, rejected = vatera.scrape(..., client=client)
buckets = vatera.split_by_sale_type(accepted)
paths = storage.save_all(buckets, rejected, ...)
ai_result = ai_review.analyse(buckets, ...)  # ha van adat és nincs --no-ai
report.write_markdown(..., buckets, rejected, ai_result)
```

Az AI-kulcs csak a környezetből kerül az SDK-hoz. A `to_payload()` engedélyezett
hirdetésmezőket küld (azonosító, URL, ár, típus, állapotjelzők és rövidített leírás),
nem a teljes környezetet. A repó nem hoz létre, nem frissít és nem von vissza
hozzáférési tokeneket. A `.env` fájlt a `.gitignore` kizárja, de a program nem
tölt be automatikusan `.env`-et: a változókat a futtató környezetnek kell átadnia.
Kulcsot ne írj a kódba vagy a riportba.

A futtatókörnyezetbe telepített Anthropic Python SDK 1.7.0 forrásának
ellenőrzése szerint az API-kulcs `X-Api-Key` fejlécbe, az auth token
`Authorization: Bearer …` fejlécbe kerül. Ezt az SDK állítja elő;
a repó maga egyik fejlécet sem építi. A függőség nincs pontos verzióra rögzítve,
ezért ez a megállapítás a vizsgált SDK-verzióra vonatkozik.

A HTML-cache `.cache_vatera/<URL SHA1>.html.gz`: a SHA1 fájlnévképzés,
nem titkosítás. A cache a válasz HTML-jét tárolja. Az AI-válaszok és hibák az
eredményekbe / naplóba kerülhetnek; nincs általános titokmaszkoló a kódban.
API-hibaüzeneteket ezért közzététel előtt át kell nézni.

A README `fix_price` / `bid` „tokenjei” HTML-jelölések, nem hozzáférési tokenek.
Az AI `input_tokens` / `output_tokens` számlálói pedig szövegfeldolgozási egységek.

## A mostani futás

Az Anthropic-kulcs és auth token, valamint az OpenAI-kulcs nem volt jelen;
külön LLM API-hívás nem történt. A scraper és az új, determinisztikus
[`elemzes/decision_model.py`](elemzes/decision_model.py) futtatása kulcs nélkül működik.
A GitHubra feltöltés a munkamenet külön GitHub-kapcsolatával történik;
annak hitelesítési adatai nem részei a scrapernek és nem kerülnek a repóba.

## A rangsorolás adatvédelmi és adatminőségi határa

Az LLM URL-visszaellenőrzése az `analyse()`-ban a bemeneti URL-ekhez köti a
találatokat, de nem bizonyítja a modell piaci árát vagy likviditási becslését.
Az új döntési modell ezeket külön kezeli: az aktív kínálat mennyiségéből
nem gyárt eladási időt. A készletellenőrzés az adott termék SKU-jához tartozó
JSON-LD ajánlatot olvassa, mert a rejtett „elkelt” HTML-sablon önmagában nem bizonyíték.

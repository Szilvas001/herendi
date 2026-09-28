"""Mit tárolunk egy hirdetésről: egy valódi, letöltött rekord mezőnként."""
from porcelan import db, images

c = db.get_conn()
r = c.execute("SELECT * FROM listings WHERE last_checked IS NOT NULL AND description IS NOT NULL "
              "AND description<>'' AND brand IS NOT NULL ORDER BY id DESC LIMIT 1").fetchone()
if r is None:
    print("még nincs letöltött termékoldal")
    raise SystemExit

for k in r.keys():
    v = r[k]
    if isinstance(v, str) and len(v) > 160:
        v = v[:160] + f"... [összesen {len(r[k])} karakter]"
    print(f"{k:18} {v}")

print("\nképek ehhez a hirdetéshez:")
for im in c.execute("SELECT url, status, width, height, path FROM images WHERE listing_id=? ORDER BY position",
                    (r["id"],)):
    print(f"  {im['status']:10} {im['width']}x{im['height']} {im['path']} {im['url'][:80]}")

print("\nár-rekordok ehhez a hirdetéshez:")
for p in c.execute("SELECT price_type, amount, currency, corpus, observed_at FROM price_records WHERE listing_id=?",
                   (r["id"],)):
    print(f"  {p['price_type']:20} {p['amount']} {p['currency']} corpus={p['corpus']} {p['observed_at']}")

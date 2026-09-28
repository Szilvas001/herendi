"""Rövid pillanatkép a gyűjtés állásáról (a hosszú `status` kimenet helyett)."""
from porcelan import db

c = db.get_conn()
q = lambda s: c.execute(s).fetchone()[0]  # noqa: E731

print("hirdetés összesen:      ", q("SELECT COUNT(*) FROM listings"))
print("  ebből elfogadott:     ", q("SELECT COUNT(*) FROM listings WHERE relevance='accepted'"))
print("  Herendi:              ", q("SELECT COUNT(*) FROM listings WHERE brand='Herendi'"))
print("  Zsolnay:              ", q("SELECT COUNT(*) FROM listings WHERE brand='Zsolnay'"))
print("termékoldal letöltve:   ", q("SELECT COUNT(*) FROM listings WHERE last_checked IS NOT NULL"))
print("ár-rekord:              ", q("SELECT COUNT(*) FROM price_records"))
print("  realizált (záró licit):", q("SELECT COUNT(*) FROM price_records WHERE price_type='auction_final_bid'"))
print("kép-URL:                ", q("SELECT COUNT(*) FROM images"))
print("nyitott feladat:        ", q("SELECT COUNT(*) FROM frontier WHERE status='pending'"))
print("kész feladat:           ", q("SELECT COUNT(*) FROM frontier WHERE status='done'"))

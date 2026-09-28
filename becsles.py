"""Mennyi adat lesz a végén: a már bejárt rész alapján extrapolálva."""
from porcelan import db

c = db.get_conn()
run = c.execute("SELECT id FROM crawl_runs WHERE source='vatera' ORDER BY id DESC LIMIT 1").fetchone()[0]

sm_done = c.execute("SELECT COUNT(*) FROM frontier WHERE run_id=? AND kind IN ('sitemap','category') "
                    "AND url LIKE '%sitemap%' AND status='done'", (run,)).fetchone()[0]
sm_all = c.execute("SELECT COUNT(*) FROM frontier WHERE run_id=? AND kind IN ('sitemap','category') "
                   "AND url LIKE '%sitemap%'", (run,)).fetchone()[0]
sm_cards = c.execute("SELECT COALESCE(SUM(listings_seen),0) FROM coverage WHERE run_id=? AND scope LIKE '%sitemap%'",
                     (run,)).fetchone()[0]

print(f"sitemap-fájl: {sm_done}/{sm_all} kész, eddig {sm_cards} márkás tétel")
if sm_done:
    print(f"  -> becsült márkás tétel a teljes sitemapből: {round(sm_cards / sm_done * sm_all):,}".replace(",", " "))

print("\nkategória-hatókörök (a Vatera által jelzett találatszám):")
tot = 0
for r in c.execute("SELECT scope, reported_total, listings_seen, exhausted FROM coverage "
                   "WHERE run_id=? AND scope NOT LIKE '%sitemap%' AND reported_total IS NOT NULL "
                   "ORDER BY reported_total DESC", (run,)):
    tot += r["reported_total"]
    print(f"  {r['reported_total']:>7} jelzett | {r['listings_seen']:>6} látott | "
          f"{'kész' if r['exhausted'] else 'folyik'} | {r['scope'][-60:]}")
print(f"  összesen jelzett: {tot}")

det = c.execute("SELECT COUNT(*) FROM listings WHERE relevance='accepted'").fetchone()[0]
print(f"\nletöltendő termékoldal (jelenlegi elfogadott): {det}")
print(f"  ~1,5 mp/kérés -> {det * 1.5 / 3600:.1f} óra")

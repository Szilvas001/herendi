"""Képi ág: CLIP-beágyazás, zero-shot előszűrés, képes tanítás és becslés.

A CLIP-súlyfájl (~600 MB, `python -m porcelan setup-models`) nélkül kihagyva.
A képek szintetikusak: a teszt a MECHANIKÁT ellenőrzi, nem a képi pontosságot.
"""
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IsolatedEnv  # noqa: E402


def _weights_present() -> bool:
    try:
        from porcelan import vision
        return vision.available()
    except Exception:
        return False


def _img(color, shape, seed):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (224, 224), (245, 245, 240))
    d = ImageDraw.Draw(img)
    off = seed % 40
    if shape == "vase":
        d.ellipse((60 + off, 40, 160 + off, 200), fill=color)
    else:
        d.rectangle((40, 60 + off, 190, 150 + off), fill=color)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


@unittest.skipUnless(_weights_present(), "CLIP-súlyok nincsenek letöltve")
class VisionTest(unittest.TestCase):
    def test_image_branch_end_to_end(self):
        with IsolatedEnv():
            from porcelan import db, images, predict, train, vision
            from helpers import synthetic_price_records
            conn = db.get_conn()
            synthetic_price_records(conn, n_hu=120, n_us=40)
            recs = conn.execute("SELECT id, title, source_ref FROM price_records").fetchall()
            for i, r in enumerate(recs[:90]):
                lid, _ = db.upsert_listing(conn, "vatera", f"8{i:08d}", {
                    "url": f"https://www.vatera.hu/x-8{i:08d}.html", "title": r["title"], "status": "active",
                    "relevance": "accepted"}, db.now_iso())
                info = images.store_image_bytes(_img((30, 80, 160) if "váza" in r["title"] else (160, 60, 40),
                                                     "vase" if "váza" in r["title"] else "box", i))
                conn.execute("INSERT INTO images(listing_id, url, position, sha256, phash, path, status) "
                             "VALUES(?,?,?,?,?,?, 'ok')", (lid, f"https://img/{i}.png", 0, info["sha256"],
                                                          info["phash"], info["path"]))
                conn.execute("UPDATE price_records SET listing_id=? WHERE id=?", (lid, r["id"]))
            conn.commit()
            n = vision.embed_pending_images(conn)
            self.assertGreater(n, 10)
            vecs = vision.listing_image_vectors(conn, [1, 2, 3])
            self.assertEqual(len(vecs), 3)
            import numpy as np
            probs = vision.zero_shot(np.stack(list(vecs.values())), conn)
            self.assertAlmostEqual(sum(probs[0].values()), 1.0, places=4)

            man = train.train(conn, n_seeds=1, use_clip=True)
            self.assertGreater(man["dataset"]["with_images"], 50)
            est = predict.Estimator()
            out = est.predict([dict(conn.execute("SELECT * FROM listings WHERE id=1").fetchone())], conn)
            self.assertTrue(out[0]["image_used"])
            self.assertIn("HU", out[0]["markets"])


if __name__ == "__main__":
    unittest.main()

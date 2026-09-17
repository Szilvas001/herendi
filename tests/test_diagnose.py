"""Füst-teszt a diagnózis eszközre (offline fixture-ökön)."""
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import diagnose  # noqa: E402

FIX = str(Path(__file__).parent / "fixtures")


class DiagnoseTest(unittest.TestCase):
    def test_search_and_details(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = diagnose.main(["--offline-dir", FIX, "--details", "2"])
        out = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("termék-link: 5 db", out)
        self.assertIn("A scraper feltevései teljesülnek", out)

    def test_single_url(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = diagnose.main([
                "--offline-dir", FIX,
                "--url", "https://www.vatera.hu/zsolnay-eozin-keszlet-100000002.html"])
        out = buf.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("Fix áras", out)
        self.assertIn("24900", out)


if __name__ == "__main__":
    unittest.main()

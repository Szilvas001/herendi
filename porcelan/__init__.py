"""Herendi / Zsolnay porcelán deal finder – Vatera scraper + Claude Opus 5 elemzés."""

__version__ = "0.1.0"

import logging as _logging

# a faiss CPU-utasításkészlet-próbálgatása (avx512 → avx2 → generic) zajos, de ártalmatlan
_logging.getLogger("faiss.loader").setLevel(_logging.WARNING)

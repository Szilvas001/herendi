"""Adatforrás-adapterek. Új forrás: `Source` alosztály + regisztráció a `SOURCES`-ban."""
from __future__ import annotations

from .base import Card, IndexPage, Source, Task


def get_source(name: str) -> Source:
    from .ebay import EbaySource
    from .jofogas import JofogasSource
    from .vatera import VateraSource
    sources = {"vatera": VateraSource, "jofogas": JofogasSource, "ebay": EbaySource}
    if name not in sources:
        raise ValueError(f"Ismeretlen forrás: {name} (elérhető: {', '.join(sources)})")
    return sources[name]()


__all__ = ["Card", "IndexPage", "Source", "Task", "get_source"]

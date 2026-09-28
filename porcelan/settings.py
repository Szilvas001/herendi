"""Konfiguráció betöltése: config/settings.toml (ha van) a minta fölé rétegezve.

A `HZ_SETTINGS` környezeti változó más fájlra mutathat; a `HZ_DATA_DIR`
az adatkönyvtárat írja felül (tesztekhez).
"""
from __future__ import annotations

import copy
import os
import tomllib
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "config" / "settings.example.toml"
LOCAL = ROOT / "config" / "settings.toml"


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


@lru_cache(maxsize=1)
def load() -> dict:
    with EXAMPLE.open("rb") as fh:
        data = tomllib.load(fh)
    override_path = Path(os.environ.get("HZ_SETTINGS", LOCAL))
    if override_path.exists():
        with override_path.open("rb") as fh:
            data = _merge(data, tomllib.load(fh))
    data_dir = os.environ.get("HZ_DATA_DIR")
    if data_dir:
        base = Path(data_dir)
        data["paths"]["data_dir"] = str(base)
        data["paths"]["db_file"] = str(base / "hzfinder.sqlite")
        data["paths"]["image_dir"] = str(base / "images")
        data["paths"]["cache_dir"] = str(base / "http_cache")
    if os.environ.get("HZ_MODELS_DIR"):
        data["paths"]["models_dir"] = os.environ["HZ_MODELS_DIR"]
    return data


def reload() -> dict:
    load.cache_clear()
    return load()


def path(key: str) -> Path:
    return _resolve(load()["paths"][key])


def get(section: str, default=None):
    node = load()
    for part in section.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node

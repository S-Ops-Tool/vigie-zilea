"""Chargement de la configuration. Un repertoire config/ par client."""
import json, os, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG_DIR = pathlib.Path(os.environ.get("VIGIE_CONFIG", ROOT / "config"))
DATA_DIR = pathlib.Path(os.environ.get("VIGIE_DATA", ROOT / "data"))
OUT_DIR = pathlib.Path(os.environ.get("VIGIE_OUT", ROOT / "out"))


def load(name):
    with open(CONFIG_DIR / f"{name}.json", encoding="utf-8") as f:
        return json.load(f)


CLIENT = load("client")
SOURCES = load("sources")
ENTITIES = load("entities")
EDITORIAL = load("editorial")

DATA_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)

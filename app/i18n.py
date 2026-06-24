import json
from pathlib import Path

_DIR = Path(__file__).resolve().parent / "i18n"
LANGS = ["zh-Hans", "zh-Hant", "en"]

def load(lang: str) -> dict:
    if lang not in LANGS:
        lang = "zh-Hans"
    return json.loads((_DIR / f"{lang}.json").read_text(encoding="utf-8"))

def t(table: dict, key: str) -> str:
    return table.get(key, key)

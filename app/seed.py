"""
seed.py — seed demo voices and presets on first run.

Idempotent: only seeds when the store is empty so a returning user's
own voices/presets are never overwritten or duplicated.
"""
from pathlib import Path
from app import voice_library, presets

_ASSETS = Path(__file__).resolve().parent / "assets" / "demo_voices"

# Chinese voice first (index 0) so it becomes the default selection.
# Names are based on voice characteristics (pitch / timbre analysis).
_DEMO_VOICES = [
    ("低沉男声（中文朗读）", "voice_zh1.wav"),
    ("明亮女声（英文朗读）", "voice_en1.wav"),
    ("柔和女声（英文朗读）", "voice_en2.wav"),
    ("女声（法语朗读）",     "voice_fr1.wav"),
    ("沉稳男声（德语朗读）", "voice_de1.wav"),
]

# Preset templates — voice_index refers to position in _DEMO_VOICES above
_DEMO_PRESET_TEMPLATES = [
    ("新闻播报（中文·稳定）",       {"lang": "chinese", "voice_index": 0,
                                     "temperature": 0.5, "top_p": 0.85, "speed": 1.0}),
    ("有声书旁白（中文·自然·偏慢）", {"lang": "chinese", "voice_index": 0,
                                     "temperature": 0.8, "top_p": 0.90, "speed": 0.95}),
    ("活泼短视频（中文·生动·偏快）", {"lang": "chinese", "voice_index": 0,
                                     "temperature": 1.2, "top_p": 0.95, "speed": 1.1}),
    ("英文朗读示例（English·自然）", {"lang": "english", "voice_index": 1,
                                     "temperature": 0.9, "top_p": 0.90, "speed": 1.0}),
    ("德语朗读示例（Deutsch·自然）", {"lang": "german",  "voice_index": 4,
                                     "temperature": 0.9, "top_p": 0.90, "speed": 1.0}),
]


def seed_defaults() -> None:
    """Seed demo voices and presets when the stores are empty."""
    # --- voices ---
    existing_voices = voice_library.list_voices()
    if not existing_voices:
        seeded_ids = []
        for name, filename in _DEMO_VOICES:
            asset_path = _ASSETS / filename
            item = voice_library.add_voice(name, str(asset_path), front=False)
            seeded_ids.append(item["id"])
    else:
        # Look up ids by name so we can reference them for presets
        name_to_id = {v["name"]: v["id"] for v in existing_voices}
        seeded_ids = []
        for name, _ in _DEMO_VOICES:
            seeded_ids.append(name_to_id.get(name))

    # --- presets ---
    if not presets.list_presets():
        for preset_name, template in _DEMO_PRESET_TEMPLATES:
            idx = template["voice_index"]
            voice_id = seeded_ids[idx] if idx < len(seeded_ids) else None
            if voice_id is not None:
                presets.save_preset(preset_name, {
                    "lang": template["lang"],
                    "voice_id": voice_id,
                    "temperature": template["temperature"],
                    "top_p": template["top_p"],
                    "speed": template["speed"],
                })

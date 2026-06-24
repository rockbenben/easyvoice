"""
Tests for app.seed — seed_defaults() behaviour:
  1. Seeds 5 voices + 5 presets when stores are empty.
  2. Idempotent: calling twice does not duplicate.
  3. Non-destructive: skips seeding when voices already exist.
  4. Seeded presets carry param keys (temperature, top_p, speed).
"""
import pytest
from app import seed, voice_library, presets, config


def _patch_dirs(monkeypatch, tmp_path):
    """Redirect voice / preset storage to isolated tmp dirs."""
    monkeypatch.setattr(config, "VOICES_DIR", tmp_path / "voices")
    monkeypatch.setattr(config, "PRESETS_DIR", tmp_path / "presets")
    # ensure_dirs so the stores can write
    config.ensure_dirs()


def test_seed_populates_empty_stores(monkeypatch, tmp_path):
    """Empty stores → 5 voices and 5 presets are created."""
    _patch_dirs(monkeypatch, tmp_path)

    seed.seed_defaults()

    voices = voice_library.list_voices()
    assert len(voices) == 5, f"Expected 5 voices, got {len(voices)}"

    plist = presets.list_presets()
    assert len(plist) == 5, f"Expected 5 presets, got {len(plist)}"


def test_seed_idempotent(monkeypatch, tmp_path):
    """Calling seed_defaults() twice does not duplicate voices or presets."""
    _patch_dirs(monkeypatch, tmp_path)

    seed.seed_defaults()
    seed.seed_defaults()

    assert len(voice_library.list_voices()) == 5
    assert len(presets.list_presets()) == 5


def test_seed_non_destructive_when_voices_exist(monkeypatch, tmp_path):
    """If a voice already exists, seed_defaults() leaves voices untouched."""
    _patch_dirs(monkeypatch, tmp_path)

    # Add a custom voice before seeding
    demo_wav = seed._ASSETS / "voice_en1.wav"
    voice_library.add_voice("我的自定义音色", str(demo_wav))

    seed.seed_defaults()

    # The pre-existing voice must still be there and no new voices were added
    voices = voice_library.list_voices()
    names = [v["name"] for v in voices]
    assert "我的自定义音色" in names, "Pre-existing voice was removed"
    # seed skips when list is non-empty, so only 1 voice total
    assert len(voices) == 1, (
        f"Expected 1 voice (non-destructive), got {len(voices)}: {names}"
    )


def test_seed_preset_voice_ids_valid(monkeypatch, tmp_path):
    """Seeded presets reference voice ids that actually exist in the library."""
    _patch_dirs(monkeypatch, tmp_path)

    seed.seed_defaults()

    voice_ids = {v["id"] for v in voice_library.list_voices()}
    for pname in presets.list_presets():
        p = presets.get_preset(pname)
        assert p.get("voice_id") in voice_ids, (
            f"Preset '{pname}' references unknown voice_id '{p.get('voice_id')}'"
        )


def test_seed_presets_carry_param_keys(monkeypatch, tmp_path):
    """All seeded presets must have temperature, top_p, and speed keys."""
    _patch_dirs(monkeypatch, tmp_path)

    seed.seed_defaults()

    for pname in presets.list_presets():
        p = presets.get_preset(pname)
        assert "temperature" in p, f"Preset '{pname}' missing 'temperature'"
        assert "top_p" in p, f"Preset '{pname}' missing 'top_p'"
        assert "speed" in p, f"Preset '{pname}' missing 'speed'"


def test_seed_chinese_voice_is_first(monkeypatch, tmp_path):
    """The first seeded voice should be the Chinese voice (低沉男声)."""
    _patch_dirs(monkeypatch, tmp_path)

    seed.seed_defaults()

    voices = voice_library.list_voices()
    assert len(voices) >= 1
    assert "中文" in voices[0]["name"], (
        f"Expected first voice to be Chinese, got: {voices[0]['name']}"
    )


def test_seed_voice_names_are_characteristic_based(monkeypatch, tmp_path):
    """Seeded voice names should describe voice characteristics, not generic indices."""
    _patch_dirs(monkeypatch, tmp_path)

    seed.seed_defaults()

    voices = voice_library.list_voices()
    names = [v["name"] for v in voices]
    expected_names = [
        "低沉男声（中文朗读）",
        "明亮女声（英文朗读）",
        "柔和女声（英文朗读）",
        "女声（法语朗读）",
        "沉稳男声（德语朗读）",
    ]
    for expected in expected_names:
        assert expected in names, (
            f"Expected voice '{expected}' not found in {names}"
        )


def test_seed_german_voice_exists(monkeypatch, tmp_path):
    """German demo voice (沉稳男声（德语朗读）) should be seeded at index 4."""
    _patch_dirs(monkeypatch, tmp_path)

    seed.seed_defaults()

    voices = voice_library.list_voices()
    assert len(voices) == 5, f"Expected 5 voices, got {len(voices)}"
    assert voices[4]["name"] == "沉稳男声（德语朗读）", (
        f"Expected German voice at index 4, got: {voices[4]['name']}"
    )


def test_seed_preset_names_are_self_explanatory(monkeypatch, tmp_path):
    """Seeded preset names should include both use-case and key config hints."""
    _patch_dirs(monkeypatch, tmp_path)

    seed.seed_defaults()

    plist = presets.list_presets()
    expected_names = [
        "新闻播报（中文·稳定）",
        "有声书旁白（中文·自然·偏慢）",
        "活泼短视频（中文·生动·偏快）",
        "英文朗读示例（English·自然）",
        "德语朗读示例（Deutsch·自然）",
    ]
    for name in expected_names:
        assert name in plist, (
            f"Expected preset '{name}' not found in {plist}"
        )

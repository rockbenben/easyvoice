from pathlib import Path
from app import config

def test_supported_langs_has_ten_with_required():
    codes = {l["code"] for l in config.SUPPORTED_LANGS}
    # code 必须是模型 generate_voice_clone(language=...) 接受的全词(见 SPIKE)
    for c in ["chinese", "english", "japanese", "korean", "german",
              "french", "russian", "portuguese", "spanish", "italian"]:
        assert c in codes
    assert all("label_key" in l for l in config.SUPPORTED_LANGS)
    assert len(config.SUPPORTED_LANGS) == 10

def test_ensure_dirs_creates(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "VOICES_DIR", tmp_path / "voices")
    monkeypatch.setattr(config, "PRESETS_DIR", tmp_path / "presets")
    monkeypatch.setattr(config, "OUTPUTS_DIR", tmp_path / "outputs")
    config.ensure_dirs()
    assert (tmp_path / "voices").is_dir()
    assert (tmp_path / "presets").is_dir()
    assert (tmp_path / "outputs").is_dir()

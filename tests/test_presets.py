import pytest
from app import presets


def test_save_get_list_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(presets.config, "PRESETS_DIR", tmp_path)
    presets.save_preset("老王讲法语", {"lang": "french", "voice_id": "ab12"})
    assert "老王讲法语" in presets.list_presets()
    assert presets.get_preset("老王讲法语")["lang"] == "french"
    presets.delete_preset("老王讲法语")
    assert presets.list_presets() == []


def test_blank_name_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(presets.config, "PRESETS_DIR", tmp_path)
    with pytest.raises(ValueError):
        presets.save_preset("  ", {"lang": "zh"})


def test_resave_same_name_overwrites(tmp_path, monkeypatch):
    monkeypatch.setattr(presets.config, "PRESETS_DIR", tmp_path)
    presets.save_preset("讲法语", {"lang": "french", "voice_id": "a"})
    presets.save_preset("讲法语", {"lang": "german", "voice_id": "b"})  # same name -> overwrite ok
    assert presets.get_preset("讲法语")["lang"] == "german"
    assert presets.list_presets() == ["讲法语"]


def test_colliding_names_raise(tmp_path, monkeypatch):
    monkeypatch.setattr(presets.config, "PRESETS_DIR", tmp_path)
    presets.save_preset("my@preset", {"lang": "english", "voice_id": "a"})
    with pytest.raises(ValueError):
        presets.save_preset("my_preset", {"lang": "english", "voice_id": "b"})  # both map to my_preset


def test_get_unknown_raises_valueerror(tmp_path, monkeypatch):
    monkeypatch.setattr(presets.config, "PRESETS_DIR", tmp_path)
    with pytest.raises(ValueError):
        presets.get_preset("不存在")


def test_rename_preset_moves_config_and_name(tmp_path, monkeypatch):
    monkeypatch.setattr(presets.config, "PRESETS_DIR", tmp_path)
    presets.save_preset("旧名", {"lang": "french", "voice_id": "ab12"})
    presets.rename_preset("旧名", "新名")
    assert presets.list_presets() == ["新名"]
    assert presets.get_preset("新名")["lang"] == "french"   # 配置保留
    with pytest.raises(ValueError):
        presets.get_preset("旧名")                            # 旧文件已删


def test_rename_preset_rejects_blank_and_duplicate(tmp_path, monkeypatch):
    monkeypatch.setattr(presets.config, "PRESETS_DIR", tmp_path)
    presets.save_preset("A", {"lang": "english"})
    presets.save_preset("B", {"lang": "german"})
    with pytest.raises(ValueError):
        presets.rename_preset("A", "  ")        # 空名
    with pytest.raises(ValueError):
        presets.rename_preset("A", "B")         # 与他方案重名
    presets.rename_preset("A", "A")             # 同名 → no-op，不报错
    assert sorted(presets.list_presets()) == ["A", "B"]

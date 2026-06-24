import wave, struct, pytest
from app import voice_library as vl

def _make_wav(p):
    with wave.open(str(p), "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(struct.pack("<h", 0) * 1600)

def test_add_list_rename_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(vl.config, "VOICES_DIR", tmp_path)
    src = tmp_path / "src.wav"; _make_wav(src)
    v = vl.add_voice("老王", str(src))
    assert v["name"] == "老王"
    assert vl.list_voices()[0]["name"] == "老王"
    assert (tmp_path / "index.json").exists()
    vl.rename_voice(v["id"], "老李")
    assert vl.list_voices()[0]["name"] == "老李"
    assert vl.get_audio_path(v["id"]).endswith(".wav")
    vl.delete_voice(v["id"])
    assert vl.list_voices() == []

def test_add_rejects_blank_name(tmp_path, monkeypatch):
    monkeypatch.setattr(vl.config, "VOICES_DIR", tmp_path)
    src = tmp_path / "src.wav"; _make_wav(src)
    with pytest.raises(ValueError):
        vl.add_voice("  ", str(src))

def test_rename_rejects_blank_name(tmp_path, monkeypatch):
    monkeypatch.setattr(vl.config, "VOICES_DIR", tmp_path)
    src = tmp_path / "src.wav"; _make_wav(src)
    v = vl.add_voice("老王", str(src))
    with pytest.raises(ValueError):
        vl.rename_voice(v["id"], "  ")

def test_add_front_vs_append(tmp_path, monkeypatch):
    monkeypatch.setattr(vl.config, "VOICES_DIR", tmp_path)
    src = tmp_path / "src.wav"; _make_wav(src)
    vl.add_voice("A", str(src), front=False)        # append
    vl.add_voice("B", str(src), front=False)        # append -> [A, B]
    assert [v["name"] for v in vl.list_voices()] == ["A", "B"]
    vl.add_voice("C", str(src))                      # front=True (default) -> [C, A, B]
    assert [v["name"] for v in vl.list_voices()] == ["C", "A", "B"]

def test_move_voice_up_down_and_bounds(tmp_path, monkeypatch):
    monkeypatch.setattr(vl.config, "VOICES_DIR", tmp_path)
    src = tmp_path / "src.wav"; _make_wav(src)
    a = vl.add_voice("A", str(src), front=False)
    b = vl.add_voice("B", str(src), front=False)
    c = vl.add_voice("C", str(src), front=False)    # [A, B, C]
    vl.move_voice(b["id"], -1)                       # B up -> [B, A, C]
    assert [v["name"] for v in vl.list_voices()] == ["B", "A", "C"]
    vl.move_voice(b["id"], 1)                        # B down -> [A, B, C]
    assert [v["name"] for v in vl.list_voices()] == ["A", "B", "C"]
    vl.move_voice(a["id"], -1)                       # already top -> no-op
    vl.move_voice(c["id"], 1)                        # already bottom -> no-op
    assert [v["name"] for v in vl.list_voices()] == ["A", "B", "C"]

def test_move_voice_missing_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(vl.config, "VOICES_DIR", tmp_path)
    with pytest.raises(KeyError):
        vl.move_voice("nope", -1)

def test_set_ref_text_persists_and_strips(tmp_path, monkeypatch):
    monkeypatch.setattr(vl.config, "VOICES_DIR", tmp_path)
    src = tmp_path / "src.wav"; _make_wav(src)
    v = vl.add_voice("声音", str(src))
    vl.set_ref_text(v["id"], "  这是参考原话  ")
    assert vl.get_ref_text(v["id"]) == "这是参考原话"

def test_replace_audio_swaps_file(tmp_path, monkeypatch):
    monkeypatch.setattr(vl.config, "VOICES_DIR", tmp_path)
    src = tmp_path / "a.wav"; _make_wav(src)
    v = vl.add_voice("声音", str(src))            # 存为 <vid>.wav
    assert vl.get_audio_path(v["id"]).endswith(".wav")
    new = tmp_path / "b.mp3"; new.write_bytes(b"ID3fake")
    vl.replace_audio(v["id"], str(new))
    assert vl.get_audio_path(v["id"]).endswith(".mp3")    # 扩展名跟随新音频
    assert not (tmp_path / (v["id"] + ".wav")).exists()   # 旧文件已删

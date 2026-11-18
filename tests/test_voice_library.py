from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import struct
from threading import Event
import wave

import pytest

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


def test_concurrent_rename_and_delete_keep_both_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(vl.config, "VOICES_DIR", tmp_path / "voices")
    source = tmp_path / "ref.wav"
    _make_wav(source)
    a = vl.add_voice("A", str(source))
    b = vl.add_voice("B", str(source))
    b_audio = Path(vl.get_audio_path(b["id"]))
    rename_before_commit = Event()
    release_rename = Event()
    delete_started = Event()
    delete_finished = Event()
    write = vl._write

    def pause_rename(items):
        if any(item["name"] == "Renamed A" for item in items):
            rename_before_commit.set()
            assert release_rename.wait(5)
        write(items)

    def delete_b():
        delete_started.set()
        vl.delete_voice(b["id"])
        delete_finished.set()

    monkeypatch.setattr(vl, "_write", pause_rename)
    with ThreadPoolExecutor(max_workers=2) as executor:
        rename = executor.submit(vl.rename_voice, a["id"], "Renamed A")
        try:
            assert rename_before_commit.wait(5)
            delete = executor.submit(delete_b)
            assert delete_started.wait(5)
            # 无锁时删除会在重命名提交旧快照之前完成。
            assert not delete_finished.wait(0.5)
        finally:
            release_rename.set()
        rename.result(timeout=5)
        delete.result(timeout=5)

    assert [(v["id"], v["name"]) for v in vl.list_voices()] == [(a["id"], "Renamed A")]
    assert Path(vl.get_audio_path(a["id"])).is_file()
    assert not b_audio.exists()


@pytest.mark.parametrize("operation", ["rename", "delete", "add", "replace"])
def test_failed_index_replace_preserves_existing_library(tmp_path, monkeypatch, operation):
    library = tmp_path / "voices"
    monkeypatch.setattr(vl.config, "VOICES_DIR", library)
    source = tmp_path / "ref.wav"
    _make_wav(source)
    replacement = tmp_path / "new.mp3"
    replacement.write_bytes(b"replacement audio")
    voice_id = vl.add_voice("原音色", str(source))["id"]
    index = library / "index.json"
    old_index = index.read_bytes()
    old_audio = Path(vl.get_audio_path(voice_id))
    old_bytes = old_audio.read_bytes()
    replace = Path.replace

    def fail_index_replace(staged, target):
        if target == index:
            assert staged != index and staged.parent == index.parent
            assert isinstance(json.loads(staged.read_text(encoding="utf-8")), list)
            assert index.read_bytes() == old_index
            assert old_audio.read_bytes() == old_bytes
            raise PermissionError("index in use")
        return replace(staged, target)

    monkeypatch.setattr(Path, "replace", fail_index_replace)
    edits = {
        "rename": lambda: vl.rename_voice(voice_id, "新名字"),
        "delete": lambda: vl.delete_voice(voice_id),
        "add": lambda: vl.add_voice("新音色", str(source)),
        "replace": lambda: vl.replace_audio(voice_id, str(replacement)),
    }
    with pytest.raises(PermissionError, match="index in use"):
        edits[operation]()

    assert index.read_bytes() == old_index
    assert old_audio.read_bytes() == old_bytes
    assert set(library.iterdir()) == {index, old_audio}


def test_partial_index_write_leaves_previous_json_readable(tmp_path, monkeypatch):
    library = tmp_path / "voices"
    monkeypatch.setattr(vl.config, "VOICES_DIR", library)
    source = tmp_path / "ref.wav"
    _make_wav(source)
    voice = vl.add_voice("A", str(source))
    write = Path.write_text

    def partial_write(path, text, **kwargs):
        write(path, text[:4], **kwargs)
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", partial_write)
    with pytest.raises(OSError, match="disk full"):
        vl.rename_voice(voice["id"], "B")

    assert vl.list_voices() == [voice]
    assert set(library.iterdir()) == {library / "index.json", library / voice["audio"]}


def test_index_replace_retries_transient_windows_sharing_error(tmp_path, monkeypatch):
    monkeypatch.setattr(vl.config, "VOICES_DIR", tmp_path / "voices")
    source = tmp_path / "ref.wav"
    _make_wav(source)
    voice = vl.add_voice("A", str(source))
    replace = Path.replace
    attempts = []

    def temporarily_locked(staged, target):
        attempts.append(staged)
        if len(attempts) == 1:
            error = PermissionError("index in use")
            error.winerror = 32
            raise error
        return replace(staged, target)

    monkeypatch.setattr(Path, "replace", temporarily_locked)
    vl.rename_voice(voice["id"], "Renamed")

    assert len(attempts) == 2 and attempts[0] == attempts[1]
    assert vl.list_voices() == [dict(voice, name="Renamed")]


def test_partial_audio_copy_leaves_same_extension_audio_intact(tmp_path, monkeypatch):
    monkeypatch.setattr(vl.config, "VOICES_DIR", tmp_path / "voices")
    source = tmp_path / "ref.wav"
    _make_wav(source)
    voice = vl.add_voice("A", str(source))
    old_audio = Path(vl.get_audio_path(voice["id"]))
    old_bytes = old_audio.read_bytes()

    def partial_copy(source, target):
        Path(target).write_bytes(b"partial audio")
        raise OSError("copy interrupted")

    monkeypatch.setattr(vl.shutil, "copyfile", partial_copy)
    with pytest.raises(OSError, match="copy interrupted"):
        vl.replace_audio(voice["id"], str(source))

    assert vl.list_voices() == [voice]
    assert old_audio.read_bytes() == old_bytes
    assert set(old_audio.parent.iterdir()) == {old_audio, old_audio.parent / "index.json"}


def test_old_index_preserves_ids_paths_and_existing_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(vl.config, "VOICES_DIR", tmp_path)
    legacy = [
        {"id": "legacy-a", "name": "旧音色", "audio": "录音.WAV", "notes": "保留"},
        {"id": "legacy-b", "name": "旁白", "audio": "旁白.wav", "ref_text": "已有原话"},
    ]
    for item in legacy:
        _make_wav(tmp_path / item["audio"])
    (tmp_path / "index.json").write_text(json.dumps(legacy, ensure_ascii=False), encoding="utf-8")

    assert vl.get_ref_text("legacy-a") == ""
    assert vl.get_ref_text("legacy-b") == "已有原话"
    vl.rename_voice("legacy-a", "重命名音色")
    vl.move_voice("legacy-b", -1)

    assert vl.list_voices() == [legacy[1], dict(legacy[0], name="重命名音色")]
    assert Path(vl.get_audio_path("legacy-a")) == tmp_path / "录音.WAV"


def test_delete_commits_index_when_audio_is_still_open(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(vl.config, "VOICES_DIR", tmp_path / "voices")
    source = tmp_path / "ref.wav"
    _make_wav(source)
    voice = vl.add_voice("A", str(source))
    audio = Path(vl.get_audio_path(voice["id"]))
    unlink = Path.unlink

    def locked_audio(path, *args, **kwargs):
        if path == audio:
            raise PermissionError("audio in use")
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", locked_audio)
    vl.delete_voice(voice["id"])

    assert vl.list_voices() == []
    assert audio.is_file()
    assert "unreferenced voice library file" in caplog.text

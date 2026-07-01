def test_split_speaker_and_build_project(monkeypatch):
    from app import dubbing_project as dp
    assert dp.split_speaker("张三：你好") == ("张三", "你好")
    assert dp.split_speaker("Alice: hi there") == ("Alice", "hi there")
    assert dp.split_speaker("没有前缀的一句") == (None, "没有前缀的一句")

    srt = ("1\n00:00:01,000 --> 00:00:02,000\n张三：你好\n\n"
           "2\n00:00:03,000 --> 00:00:04,000\n李四：还行\n\n"
           "3\n00:00:05,000 --> 00:00:06,000\n旁白一句\n")
    proj = dp.build_project(srt, "chinese", "v0")
    assert {c["speaker"] for c in proj["cues"]} == {"张三", "李四", dp.DEFAULT_SPEAKER}
    assert proj["cues"][0]["text"] == "你好"            # 前缀已剥离
    assert proj["speakers"]["张三"] == "v0"             # 默认指向传入音色
    assert proj["cues"][2]["speaker"] == dp.DEFAULT_SPEAKER
    assert all(c["status"] == "pending" for c in proj["cues"])


def test_split_speaker_ignores_incidental_colons():
    """无说话人前缀但正文含冒号的行不得被误拆成「说话人：台词」而吞掉正文。"""
    from app import dubbing_project as dp
    # 多词短语(含空格) → 不是说话人，整句保留
    assert dp.split_speaker("Meeting at 12:30 PM") == (None, "Meeting at 12:30 PM")
    # 纯数字前缀(时间) → 不是说话人
    assert dp.split_speaker("12:30 PM 开会") == (None, "12:30 PM 开会")
    # 真说话人(单词、非数字)仍然识别
    assert dp.split_speaker("张三：你好") == ("张三", "你好")
    assert dp.split_speaker("John: hi") == ("John", "hi")


def test_build_project_detect_speakers_off_keeps_text():
    """detect_speakers=False：不拆前缀，所有行归到单一默认角色，正文一字不丢。"""
    from app import dubbing_project as dp
    srt = ("1\n00:00:01,000 --> 00:00:02,000\nMeeting at 12:30 PM\n\n"
           "2\n00:00:03,000 --> 00:00:04,000\n张三：你好\n")
    proj = dp.build_project(srt, "english", "v0", detect_speakers=False)
    assert list(proj["speakers"].keys()) == [dp.DEFAULT_SPEAKER]
    assert proj["cues"][0]["text"] == "Meeting at 12:30 PM"    # 冒号正文完整保留
    assert proj["cues"][1]["text"] == "张三：你好"             # 前缀也不剥离(整行原样)


def test_edits_mark_dirty():
    from app import dubbing_project as dp
    srt = ("1\n00:00:01,000 --> 00:00:02,000\n张三：你好\n\n"
           "2\n00:00:03,000 --> 00:00:04,000\n李四：还行\n\n"
           "3\n00:00:05,000 --> 00:00:06,000\n张三：那就好\n")
    p = dp.build_project(srt, "chinese", "v0")
    for c in p["cues"]:
        c["status"] = "ok"                      # 先假装都已生成

    dp.set_speaker_voice(p, "张三", "v9")
    assert p["speakers"]["张三"] == "v9"
    assert [c["status"] for c in p["cues"]] == ["dirty", "ok", "dirty"]  # 仅张三两条变脏

    for c in p["cues"]:
        c["status"] = "ok"
    dp.set_cue_text(p, 1, "改成这句")
    assert dp._cue(p, 1)["text"] == "改成这句"
    assert [c["status"] for c in p["cues"]] == ["ok", "dirty", "ok"]     # 仅该条变脏

    dp.set_cue_speaker(p, 1, "新角色")
    assert dp._cue(p, 1)["speaker"] == "新角色"
    assert "新角色" in p["speakers"]            # 新角色被登记


def test_generate_all_and_reroll(tmp_path, monkeypatch):
    from app import dubbing_project as dp
    import numpy as np
    monkeypatch.setattr(dp.config, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(dp.voice_library, "get_audio_path", lambda vid: f"/voices/{vid}.wav")
    calls = []

    def _fake_one(text, lang, ref, params):
        calls.append((text, ref, params.get("seed")))
        return np.full(2400, 0.3, np.float32), 24000

    monkeypatch.setattr(dp.tts_engine, "synthesize_one", _fake_one)

    srt = ("1\n00:00:01,000 --> 00:00:02,000\n张三：你好\n\n"
           "2\n00:00:03,000 --> 00:00:04,000\n李四：还行\n")
    p = dp.build_project(srt, "chinese", "v0")
    dp.set_speaker_voice(p, "李四", "v1")        # 李四换音色 v1

    seen = []
    dp.generate_all(p, progress_cb=lambda d, t: seen.append((d, t)))
    assert all(c["status"] == "ok" for c in p["cues"])
    import os
    assert all(c["audio_path"] and os.path.exists(c["audio_path"]) for c in p["cues"])
    assert "/voices/v0.wav" in {r for _, r, _ in calls}   # 张三用 v0
    assert "/voices/v1.wav" in {r for _, r, _ in calls}   # 李四用 v1
    assert seen[-1] == (2, 2)

    # 再次 generate_all：全 ok，不再重生
    calls.clear()
    dp.generate_all(p)
    assert calls == []                            # 没有 pending/dirty → 不调用

    # 重录第 0 条：强制重生，seed 传 0(新随机)
    calls.clear()
    dp.reroll_cue(p, 0)
    assert len(calls) == 1 and calls[0][2] == 0
    assert p["cues"][0]["status"] == "ok"


def test_generate_cue_missing_voice_marks_error(tmp_path, monkeypatch):
    from app import dubbing_project as dp
    monkeypatch.setattr(dp.config, "OUTPUTS_DIR", tmp_path)

    def _boom(vid):
        raise KeyError(vid)

    monkeypatch.setattr(dp.voice_library, "get_audio_path", _boom)
    srt = "1\n00:00:01,000 --> 00:00:02,000\n你好\n"
    p = dp.build_project(srt, "chinese", None)
    dp.generate_cue(p, 0)
    assert p["cues"][0]["status"] == "error"


def test_assemble_reads_cached_audio(tmp_path, monkeypatch):
    from app import dubbing_project as dp
    import numpy as np, soundfile as sf
    monkeypatch.setattr(dp.config, "OUTPUTS_DIR", tmp_path)
    captured = {}

    def _fake_assemble(items, max_speedup=1.5):
        captured["items"] = items
        return "out.wav", "out.srt"

    monkeypatch.setattr(dp.tts_engine, "assemble_timeline", _fake_assemble)
    srt = ("1\n00:00:01,000 --> 00:00:02,000\n你好\n\n"
           "2\n00:00:03,000 --> 00:00:04,000\n世界\n")
    p = dp.build_project(srt, "chinese", "v0")
    # 给第 0 条写一个缓存音频，第 1 条留空(未生成)
    a = tmp_path / "c0.wav"
    sf.write(str(a), np.full(2400, 0.2, np.float32), 24000)
    p["cues"][0]["audio_path"] = str(a)
    p["cues"][0]["status"] = "ok"        # B1: assemble now requires status=='ok'

    wav, srt_out = dp.assemble(p)
    assert (wav, srt_out) == ("out.wav", "out.srt")
    assert len(captured["items"]) == 1                 # 只拼已生成的那条
    assert captured["items"][0]["text"] == "你好"


def test_assemble_without_audio_raises(monkeypatch):
    from app import dubbing_project as dp
    import pytest
    srt = "1\n00:00:01,000 --> 00:00:02,000\n你好\n"
    p = dp.build_project(srt, "chinese", "v0")
    with pytest.raises(ValueError):
        dp.assemble(p)


def test_assemble_excludes_dirty_cue(tmp_path, monkeypatch):
    from app import dubbing_project as dp
    import numpy as np, soundfile as sf
    monkeypatch.setattr(dp.config, "OUTPUTS_DIR", tmp_path)
    captured = {}
    monkeypatch.setattr(dp.tts_engine, "assemble_timeline",
                        lambda items, max_speedup=1.5: (captured.update(items=items), ("w", "s"))[1])
    srt = ("1\n00:00:01,000 --> 00:00:02,000\n你好\n\n"
           "2\n00:00:03,000 --> 00:00:04,000\n世界\n")
    p = dp.build_project(srt, "chinese", "v0")
    for i in (0, 1):
        a = tmp_path / f"c{i}.wav"
        sf.write(str(a), np.full(2400, 0.2, np.float32), 24000)
        p["cues"][i]["audio_path"] = str(a)
    p["cues"][0]["status"] = "ok"
    p["cues"][1]["status"] = "dirty"      # 已改未重生 → 应被排除
    dp.assemble(p)
    assert [it["text"] for it in captured["items"]] == ["你好"]   # 只含 ok 那条


def test_generate_cue_non_keyerror_marks_error(tmp_path, monkeypatch):
    from app import dubbing_project as dp
    monkeypatch.setattr(dp.config, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(dp.voice_library, "get_audio_path",
                        lambda vid: (_ for _ in ()).throw(ValueError("corrupt index")))
    p = dp.build_project("1\n00:00:01,000 --> 00:00:02,000\n你好\n", "chinese", "v0")
    dp.generate_cue(p, 0)                  # 不应抛
    assert p["cues"][0]["status"] == "error"


def test_generate_cue_write_failure_marks_error(tmp_path, monkeypatch):
    from app import dubbing_project as dp
    import numpy as np
    monkeypatch.setattr(dp.config, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(dp.voice_library, "get_audio_path", lambda vid: "r.wav")
    monkeypatch.setattr(dp.tts_engine, "synthesize_one",
                        lambda *a, **k: (np.full(2400, 0.2, np.float32), 24000))
    monkeypatch.setattr(dp.sf, "write", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    p = dp.build_project("1\n00:00:01,000 --> 00:00:02,000\n你好\n", "chinese", "v0")
    dp.generate_cue(p, 0)
    assert p["cues"][0]["status"] == "error"


def test_generate_all_retries_error_cue(tmp_path, monkeypatch):
    from app import dubbing_project as dp
    import numpy as np
    monkeypatch.setattr(dp.config, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(dp.voice_library, "get_audio_path", lambda vid: "r.wav")
    monkeypatch.setattr(dp.tts_engine, "synthesize_one",
                        lambda *a, **k: (np.full(2400, 0.2, np.float32), 24000))
    p = dp.build_project("1\n00:00:01,000 --> 00:00:02,000\n你好\n", "chinese", "v0")
    p["cues"][0]["status"] = "error"       # 之前失败
    dp.generate_all(p)
    assert p["cues"][0]["status"] == "ok"  # 重点生成时被重试并成功

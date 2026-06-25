def test_build_ui_returns_blocks(monkeypatch, tmp_path):
    from app import config
    monkeypatch.setattr(config, "VOICES_DIR", tmp_path / "v")
    monkeypatch.setattr(config, "PRESETS_DIR", tmp_path / "p")
    monkeypatch.setattr(config, "OUTPUTS_DIR", tmp_path / "o")
    from app import ui
    import gradio as gr
    blocks = ui.build_ui("zh-Hans")
    assert isinstance(blocks, gr.Blocks)

def test_generate_handler_uses_engine(monkeypatch, tmp_path):
    from app import ui, tts_engine, voice_library, config
    monkeypatch.setattr(config, "VOICES_DIR", tmp_path)
    monkeypatch.setattr(tts_engine, "synthesize", lambda *a, **k: str(tmp_path / "x.wav"))
    monkeypatch.setattr(voice_library, "get_audio_path", lambda vid: str(tmp_path / "ref.wav"))
    # do_generate has temperature/top_p/speed defaulted, so 3-arg call still works
    out = ui.do_generate(text="你好", lang="chinese", voice_id="ab12")
    assert out.endswith("x.wav")

def test_generate_handler_forwards_params(monkeypatch, tmp_path):
    from app import ui, tts_engine, voice_library, config
    monkeypatch.setattr(config, "VOICES_DIR", tmp_path)
    captured = {}
    def _mock_synth(text, lang, ref, temperature=0.9, top_p=0.9, speed=1.0, **kwargs):
        captured.update({"temperature": temperature, "top_p": top_p, "speed": speed})
        return str(tmp_path / "x.wav")
    monkeypatch.setattr(tts_engine, "synthesize", _mock_synth)
    monkeypatch.setattr(voice_library, "get_audio_path", lambda vid: str(tmp_path / "ref.wav"))
    ui.do_generate(text="测试", lang="chinese", voice_id="ab12",
                   temperature=0.5, top_p=0.85, speed=1.2)
    assert captured["temperature"] == 0.5
    assert captured["top_p"] == 0.85
    assert captured["speed"] == 1.2


def test_do_generate_forwards_seed(monkeypatch, tmp_path):
    from app import ui, tts_engine, voice_library, config
    monkeypatch.setattr(config, "VOICES_DIR", tmp_path)
    captured = {}
    def _mock_synth(text, lang, ref, *a, seed=0, **kwargs):
        captured["seed"] = seed
        return str(tmp_path / "x.wav")
    monkeypatch.setattr(tts_engine, "synthesize", _mock_synth)
    monkeypatch.setattr(voice_library, "get_audio_path", lambda vid: str(tmp_path / "ref.wav"))
    monkeypatch.setattr(voice_library, "get_ref_text", lambda vid: "")
    ui.do_generate(text="测试", lang="chinese", voice_id="ab12", seed=123)
    assert captured["seed"] == 123


def test_do_subtitle_dub_parses_and_synthesizes(monkeypatch, tmp_path):
    from app import ui, tts_engine, voice_library, config
    monkeypatch.setattr(config, "VOICES_DIR", tmp_path)
    sub = tmp_path / "x.srt"
    sub.write_text("1\n00:00:01,000 --> 00:00:02,000\n你好\n", encoding="utf-8")
    monkeypatch.setattr(voice_library, "get_audio_path", lambda vid: str(tmp_path / "ref.wav"))
    monkeypatch.setattr(voice_library, "get_ref_text", lambda vid: "")
    cap = {}
    monkeypatch.setattr(tts_engine, "synthesize_subtitles",
                        lambda cues, lang, ref, **k: cap.update(n=len(cues), lang=lang)
                        or (str(tmp_path / "o.wav"), str(tmp_path / "o.srt")))
    wav, srt = ui.do_subtitle_dub(str(sub), "v1", "chinese")
    assert cap["n"] == 1 and cap["lang"] == "chinese"
    assert wav.endswith("o.wav") and srt.endswith("o.srt")


def test_do_subtitle_dub_requires_file(monkeypatch, tmp_path):
    from app import ui, config
    import gradio as gr, pytest
    monkeypatch.setattr(config, "VOICES_DIR", tmp_path / "v")
    with pytest.raises(gr.Error):
        ui.do_subtitle_dub(None, "v1", "chinese")

def test_do_tok_estimate_converts_and_localizes():
    from app import ui
    r = ui.do_tok_estimate(1500, "zh-Hans")        # 1500/12.5/60 = 2.0 分钟
    assert "2.0" in r and "分钟" in r and "⚠️" not in r   # 正常值不提醒
    assert "min of audio" in ui.do_tok_estimate(1500, "en")
    long_zh = ui.do_tok_estimate(20000, "zh-Hans")        # 超长 → 带 ⚠️ 提醒
    assert "⚠️" in long_zh and "分段" in long_zh
    assert "split long text" in ui.do_tok_estimate(20000, "en")


def test_do_apply_style_returns_correct_params():
    from app import ui
    assert ui.do_apply_style("stable") == (0.5, 0.85)
    assert ui.do_apply_style("natural") == (0.9, 0.90)
    assert ui.do_apply_style("lively") == (1.2, 0.95)

def test_do_voice_delete_clears_and_bumps(monkeypatch, tmp_path):
    from app import ui, voice_library, config
    monkeypatch.setattr(config, "VOICES_DIR", tmp_path / "v")
    deleted = []
    monkeypatch.setattr(voice_library, "delete_voice", lambda vid: deleted.append(vid))
    monkeypatch.setattr(voice_library, "list_voices", lambda: [])
    bump, pending, _upd = ui.do_voice_delete("voice-123", 4)
    assert deleted == ["voice-123"]
    assert bump == 5 and pending is None   # +1 重渲染、清空待确认

def test_do_voice_delete_resets_stale_selection(monkeypatch, tmp_path):
    """删除配音里选中的音色 → voice_dd 改选第一个剩余(否则下拉残留已删音色)；删非选中则保持。"""
    from app import ui, voice_library, config
    monkeypatch.setattr(config, "VOICES_DIR", tmp_path / "v")
    monkeypatch.setattr(voice_library, "delete_voice", lambda vid: None)
    monkeypatch.setattr(voice_library, "list_voices", lambda: [{"id": "b", "name": "B"}])  # 删后剩 b
    _b, _p, upd = ui.do_voice_delete("a", 1, current="a")            # 选中的就是被删的 a
    assert (upd["value"] if isinstance(upd, dict) else getattr(upd, "value", None)) == "b"
    _b2, _p2, upd2 = ui.do_voice_delete("a", 1, current="b")         # 选中 b(没删) → 保持 b
    assert (upd2["value"] if isinstance(upd2, dict) else getattr(upd2, "value", None)) == "b"


def test_do_subtitle_preview_warns_when_cues_dropped(monkeypatch, tmp_path):
    """超 6h 上限的字幕被丢时,预览须明示(否则配音会静默缺尾)；全正常则不提示。"""
    from app import ui, config
    monkeypatch.setattr(config, "VOICES_DIR", tmp_path / "v")
    f = tmp_path / "s.srt"
    f.write_text("1\n99:00:00,000 --> 99:00:05,000\nA\n\n"
                 "2\n00:00:01,000 --> 00:00:02,000\nB\n", encoding="utf-8")
    assert "已忽略" in ui.do_subtitle_preview(str(f))          # request=None → 简体
    ok = tmp_path / "ok.srt"
    ok.write_text("1\n00:00:01,000 --> 00:00:02,000\nB\n", encoding="utf-8")
    assert "已忽略" not in ui.do_subtitle_preview(str(ok))


def test_do_add_voice_resets_capture_after_save(monkeypatch, tmp_path):
    """保存后必须清空 _cap：否则再点一次「添加」(含误双击)会用残留路径重复建同一音色。"""
    from app import ui, voice_library, config
    monkeypatch.setattr(config, "VOICES_DIR", tmp_path / "v")
    added = []
    monkeypatch.setattr(voice_library, "add_voice", lambda n, p, *a, **k: added.append((n, p)))
    monkeypatch.setattr(voice_library, "list_voices", lambda: [{"id": "x", "name": "A"}])
    ret = ui.do_add_voice("A", str(tmp_path / "ref.wav"), 0)
    # ret = (voice_dd 更新, bump, vname 更新, _cap, vref_play 更新)
    assert added == [("A", str(tmp_path / "ref.wav"))]
    assert ret[1] == 1                  # bump+1 触发重渲染
    assert ret[3] is None               # _cap 清空 → 第二次点击无残留路径，不会重复添加


def test_do_voice_save_edit_renames(monkeypatch, tmp_path):
    from app import ui, voice_library, config
    monkeypatch.setattr(config, "VOICES_DIR", tmp_path / "v")
    renamed = []
    monkeypatch.setattr(voice_library, "rename_voice", lambda vid, n: renamed.append((vid, n)))
    monkeypatch.setattr(voice_library, "list_voices", lambda: [])
    bump, editing, _upd = ui.do_voice_save_edit("v1", "新名", 4)
    assert renamed == [("v1", "新名")] and bump == 5 and editing is None
    renamed.clear()
    ui.do_voice_save_edit("v1", "   ", 0)              # 空名 → 不改名
    assert renamed == []

def test_do_preset_delete_clears_and_bumps(monkeypatch, tmp_path):
    from app import ui, presets, config
    monkeypatch.setattr(config, "PRESETS_DIR", tmp_path / "p")
    deleted = []
    monkeypatch.setattr(presets, "delete_preset", lambda name: deleted.append(name))
    monkeypatch.setattr(presets, "list_presets", lambda: [])
    bump, pending, _upd = ui.do_preset_delete("my-preset", 2)
    assert deleted == ["my-preset"]
    assert bump == 3 and pending is None

def test_do_save_preset_returns_dropdown_and_bump(monkeypatch, tmp_path):
    from app import ui, presets, config
    monkeypatch.setattr(config, "PRESETS_DIR", tmp_path / "p")
    (tmp_path / "p").mkdir()
    monkeypatch.setattr(presets, "save_preset", lambda name, data: None)
    monkeypatch.setattr(presets, "list_presets", lambda: ["X"])
    upd, bump = ui.do_save_preset("X", "chinese", "v1", 0.9, 0.9, 1.0, 4)
    assert bump == 5   # 保存后 +1 触发管理列表重渲染

def test_do_generate_raises_on_stale_voice_id(monkeypatch, tmp_path):
    from app import ui, tts_engine, voice_library, config
    import gradio as gr
    import pytest
    monkeypatch.setattr(config, "VOICES_DIR", tmp_path)
    monkeypatch.setattr(tts_engine, "synthesize", lambda *a, **k: str(tmp_path / "x.wav"))
    def _raise_key_error(vid):
        raise KeyError(vid)
    monkeypatch.setattr(voice_library, "get_audio_path", _raise_key_error)
    with pytest.raises(gr.Error):
        ui.do_generate(text="你好", lang="chinese", voice_id="stale-id")

def test_do_add_voice_returns_reset_updates(monkeypatch, tmp_path):
    from app import ui, voice_library, config
    monkeypatch.setattr(config, "VOICES_DIR", tmp_path)
    monkeypatch.setattr(voice_library, "add_voice", lambda name, ref, rt="": {"id": "x", "name": name, "audio": "x.wav"})
    monkeypatch.setattr(voice_library, "list_voices", lambda: [{"id": "x", "name": "n", "audio": "x.wav"}])
    out = ui.do_add_voice("n", "ref.wav")
    # (voice_dd, _bump, vname清空, _cap清空, vref_play隐藏) —— _cap 必须清空以防再次点击重复添加
    assert isinstance(out, tuple) and len(out) == 5
    assert out[3] is None

def test_do_save_preset_includes_params(monkeypatch, tmp_path):
    from app import ui, presets, config
    monkeypatch.setattr(config, "PRESETS_DIR", tmp_path / "p")
    (tmp_path / "p").mkdir()
    saved = {}
    def _mock_save(name, data):
        saved.update(data)
    monkeypatch.setattr(presets, "save_preset", _mock_save)
    monkeypatch.setattr(presets, "list_presets", lambda: [])
    ui.do_save_preset("test", "chinese", "v1", 0.5, 0.85, 1.2)
    assert saved["temperature"] == 0.5
    assert saved["top_p"] == 0.85
    assert saved["speed"] == 1.2

def test_do_apply_preset_returns_five_values(monkeypatch, tmp_path):
    from app import ui, presets, config
    monkeypatch.setattr(config, "PRESETS_DIR", tmp_path / "p")
    monkeypatch.setattr(presets, "get_preset", lambda name: {
        "lang": "chinese", "voice_id": "v1",
        "speed": 0.95, "temperature": 0.8, "top_p": 0.9,
    })
    result = ui.do_apply_preset("有声书旁白")
    assert result == ("chinese", "v1", 0.95, 0.8, 0.9)

def test_do_apply_preset_fallback_defaults(monkeypatch, tmp_path):
    from app import ui, presets, config
    monkeypatch.setattr(config, "PRESETS_DIR", tmp_path / "p")
    # Old preset without new param keys
    monkeypatch.setattr(presets, "get_preset", lambda name: {
        "lang": "english", "voice_id": "v2",
    })
    result = ui.do_apply_preset("old preset")
    assert result == ("english", "v2", 1.0, 0.9, 0.9)


def test_do_preset_summary_returns_markdown(monkeypatch, tmp_path):
    """do_preset_summary resolves voice name, lang label, style label, speed."""
    from app import ui, presets, voice_library, config
    monkeypatch.setattr(config, "PRESETS_DIR", tmp_path / "p")
    monkeypatch.setattr(config, "VOICES_DIR", tmp_path / "v")
    monkeypatch.setattr(presets, "get_preset", lambda name: {
        "lang": "chinese",
        "voice_id": "abc12345",
        "temperature": 0.5,
        "top_p": 0.85,
        "speed": 1.0,
    })
    monkeypatch.setattr(voice_library, "list_voices", lambda: [
        {"id": "abc12345", "name": "示例音色1（中文朗读）", "audio": "abc12345.wav"},
    ])
    result = ui.do_preset_summary("新闻播报（中文·稳定）", "zh-Hans")
    assert "示例音色1（中文朗读）" in result, f"Voice name not in summary: {result}"
    assert "稳定" in result, f"Style label not in summary: {result}"
    assert "1.0×" in result, f"Speed not in summary: {result}"


def test_do_preset_summary_empty_name(monkeypatch, tmp_path):
    """do_preset_summary returns empty string when name is empty/None."""
    from app import ui
    assert ui.do_preset_summary("") == ""
    assert ui.do_preset_summary(None) == ""


def test_do_preset_summary_missing_preset(monkeypatch, tmp_path):
    """do_preset_summary returns empty string when preset does not exist."""
    from app import ui, presets, config
    monkeypatch.setattr(config, "PRESETS_DIR", tmp_path / "p")
    monkeypatch.setattr(presets, "get_preset", lambda name: (_ for _ in ()).throw(ValueError("not found")))
    result = ui.do_preset_summary("nonexistent", "zh-Hans")
    assert result == ""


def test_do_preset_summary_lively_style(monkeypatch, tmp_path):
    """do_preset_summary uses 'lively' style for temperature > 1.0."""
    from app import ui, presets, voice_library, config
    monkeypatch.setattr(config, "PRESETS_DIR", tmp_path / "p")
    monkeypatch.setattr(config, "VOICES_DIR", tmp_path / "v")
    monkeypatch.setattr(presets, "get_preset", lambda name: {
        "lang": "chinese",
        "voice_id": "xyz",
        "temperature": 1.2,
        "top_p": 0.95,
        "speed": 1.1,
    })
    monkeypatch.setattr(voice_library, "list_voices", lambda: [
        {"id": "xyz", "name": "活泼声音", "audio": "xyz.wav"},
    ])
    result = ui.do_preset_summary("活泼短视频（中文·生动·偏快）", "zh-Hans")
    assert "生动" in result, f"Expected '生动' style label in summary: {result}"
    assert "1.1×" in result, f"Speed not in summary: {result}"


def test_do_voice_move_bumps_and_updates(monkeypatch, tmp_path):
    from app import ui, voice_library, config
    monkeypatch.setattr(config, "VOICES_DIR", tmp_path / "v")
    moved = []
    monkeypatch.setattr(voice_library, "move_voice", lambda vid, d: moved.append((vid, d)))
    monkeypatch.setattr(voice_library, "list_voices", lambda: [])
    bump, _upd = ui.do_voice_move("x", -1, 3)    # 上移
    assert moved == [("x", -1)] and bump == 4
    ui.do_voice_move("x", 1, 0)                   # 下移
    assert moved[-1] == ("x", 1)


def _btn_interactive(upd):
    """从 gr.update() 返回值里取 interactive 标志(兼容 dict / 对象两种形态)。"""
    if isinstance(upd, dict):
        return upd.get("interactive")
    return getattr(upd, "interactive", None)


def test_run_generate_resets_and_returns_audio_on_success(monkeypatch, tmp_path):
    """成功路径：先 yield 禁用(生成中)，末帧复位按钮 + 返回音频路径。"""
    from app import ui, tts_engine, voice_library, config
    monkeypatch.setattr(config, "VOICES_DIR", tmp_path)
    monkeypatch.setattr(tts_engine, "synthesize", lambda *a, **k: str(tmp_path / "x.wav"))
    monkeypatch.setattr(voice_library, "get_audio_path", lambda vid: str(tmp_path / "ref.wav"))
    monkeypatch.setattr(voice_library, "get_ref_text", lambda vid: "")
    frames = list(ui._run_generate(text="你好", lang="chinese", voice_id="ab12"))
    assert _btn_interactive(frames[0][0]) is False        # 首帧禁用按钮
    assert _btn_interactive(frames[-1][0]) is True         # 末帧复位按钮
    assert frames[-1][1].endswith("x.wav")                 # 末帧带回音频


def test_run_generate_resets_button_on_error(monkeypatch, tmp_path):
    """出错路径(空文本)：仍先 yield 复位按钮，再抛 gr.Error——按钮不卡死在"生成中"。"""
    from app import ui, config
    import gradio as gr, pytest
    monkeypatch.setattr(config, "VOICES_DIR", tmp_path / "v")
    gen = ui._run_generate(text="", lang="chinese", voice_id=None)
    frames = []
    with pytest.raises(gr.Error):
        for upd in gen:
            frames.append(upd)
    assert _btn_interactive(frames[0][0]) is False        # 首帧禁用
    assert _btn_interactive(frames[-1][0]) is True         # 抛错前已复位按钮


def test_run_subtitle_dub_resets_button_on_error(monkeypatch, tmp_path):
    """字幕配音出错路径(无文件)：同样先复位按钮再抛错。"""
    from app import ui, config
    import gradio as gr, pytest
    monkeypatch.setattr(config, "VOICES_DIR", tmp_path / "v")
    gen = ui._run_subtitle_dub(None, "v1", "chinese")
    frames = []
    with pytest.raises(gr.Error):
        for upd in gen:
            frames.append(upd)
    assert _btn_interactive(frames[0][0]) is False
    assert _btn_interactive(frames[-1][0]) is True

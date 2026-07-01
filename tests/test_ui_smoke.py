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
    # 末位是同步给 style 芯片的档位(由温度反推)：0.8 → natural
    assert result == ("chinese", "v1", 0.95, 0.8, 0.9, "natural")

def test_do_apply_preset_fallback_defaults(monkeypatch, tmp_path):
    from app import ui, presets, config
    monkeypatch.setattr(config, "PRESETS_DIR", tmp_path / "p")
    # Old preset without new param keys
    monkeypatch.setattr(presets, "get_preset", lambda name: {
        "lang": "english", "voice_id": "v2",
    })
    result = ui.do_apply_preset("old preset")
    assert result == ("english", "v2", 1.0, 0.9, 0.9, "natural")   # 默认温度 0.9 → natural


def test_do_apply_preset_syncs_style_chip(monkeypatch, tmp_path):
    """套用预设须回传与温度一致的 style 档位，避免芯片与滑块脱节；覆盖 stable/lively 两端。"""
    from app import ui, presets, config
    monkeypatch.setattr(config, "PRESETS_DIR", tmp_path / "p")
    monkeypatch.setattr(presets, "get_preset",
                        lambda name: {"lang": "chinese", "voice_id": "v", "temperature": 0.5})
    assert ui.do_apply_preset("稳定")[-1] == "stable"     # 0.5 → stable
    monkeypatch.setattr(presets, "get_preset",
                        lambda name: {"lang": "chinese", "voice_id": "v", "temperature": 1.2})
    assert ui.do_apply_preset("活泼")[-1] == "lively"     # 1.2 → lively


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


def test_subtitle_dub_helpers_build_table(monkeypatch, tmp_path):
    from app import dubbing_project as dp, ui
    monkeypatch.setattr(dp.config, "OUTPUTS_DIR", tmp_path)
    srt = ("1\n00:00:01,000 --> 00:00:02,000\n张三：你好\n\n"
           "2\n00:00:03,000 --> 00:00:04,000\n李四：还行\n")
    proj = dp.build_project(srt, "chinese", "v0")
    rows = ui._sub_table(proj)
    assert rows[0] == [1, "张三", "你好", "pending"]
    assert rows[1][1] == "李四"


def test_build_ui_with_subtitle_tab_constructs():
    from app import ui
    demo = ui.build_ui("zh-Hans")          # 不抛错即说明新标签接线无误
    assert demo is not None


def test_edit_text_without_selection_errors(monkeypatch, tmp_path):
    import pytest, gradio as gr
    from app import dubbing_project as dp, ui
    monkeypatch.setattr(dp.config, "OUTPUTS_DIR", tmp_path)
    proj = dp.build_project("1\n00:00:01,000 --> 00:00:02,000\n你好\n", "chinese", "v0")
    with pytest.raises(gr.Error):
        ui.do_sub_edit_text(proj, None, "x", None)        # 未选行 → 友好报错
    # project 为 None 时静默返回，不报错
    out, _ = ui.do_sub_edit_text(None, None, "x", None)
    assert out is None


def test_role_change_updates_voice_and_table(monkeypatch, tmp_path):
    from app import dubbing_project as dp, ui
    monkeypatch.setattr(dp.config, "OUTPUTS_DIR", tmp_path)
    srt = ("1\n00:00:01,000 --> 00:00:02,000\n张三：你好\n\n"
           "2\n00:00:03,000 --> 00:00:04,000\n李四：还行\n")
    proj = dp.build_project(srt, "chinese", "v0")
    out_proj, table_update = ui._role_change(proj, "张三", "v9")
    assert out_proj["speakers"]["张三"] == "v9"
    # 张三 the cue (row 0) is now dirty in the refreshed table
    assert table_update["value"][0][3] == "dirty"


def test_model_choices_two_tiers():
    from app import ui
    assert [v for _, v in ui._model_choices()] == ["0.6b", "1.7b"]


def test_model_choices_localized():
    from app import ui, i18n
    labels = [lbl for lbl, _ in ui._model_choices(i18n.load("en"))]
    assert "Fast 0.6B" in labels and "High 1.7B" in labels


def test_do_generate_threads_model(monkeypatch):
    from app import ui, tts_engine
    captured = {}

    def _fake_syn(text, lang, ref, *a, **k):
        captured["model"] = k.get("model")
        return "x.wav"

    monkeypatch.setattr(ui.voice_library, "get_audio_path", lambda vid: "r.wav")
    monkeypatch.setattr(tts_engine, "synthesize", _fake_syn)
    ui.do_generate("hi", "english", "v0", model="1.7b")
    assert captured["model"] == "1.7b"


def test_run_sub_gen_all_sets_model(monkeypatch, tmp_path):
    from app import ui, dubbing_project as dp
    monkeypatch.setattr(dp.config, "OUTPUTS_DIR", tmp_path)
    captured = {}
    monkeypatch.setattr(dp, "generate_all",
                        lambda p, progress_cb=None: captured.update(model=p["params"].get("model")))
    proj = dp.build_project("1\n00:00:01,000 --> 00:00:02,000\n你好\n", "chinese", "v0")
    list(ui._run_sub_gen_all(proj, "1.7b"))     # 消费生成器
    assert captured["model"] == "1.7b"
    assert proj["params"]["model"] == "1.7b"


def test_run_sub_export_flags_non_ok_cues(tmp_path, monkeypatch):
    from app import ui, dubbing_project as dp
    monkeypatch.setattr(dp.config, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(ui._dub, "assemble", lambda p: ("w.wav", "s.srt"))
    infos = []
    monkeypatch.setattr(ui.gr, "Info", lambda msg: infos.append(msg))
    srt = ("1\n00:00:01,000 --> 00:00:02,000\n你好\n\n"
           "2\n00:00:03,000 --> 00:00:04,000\n世界\n")
    p = dp.build_project(srt, "chinese", "v0")
    p["cues"][0]["status"] = "ok"
    p["cues"][1]["status"] = "dirty"       # 非 ok → 应触发"已跳过"提示
    list(ui._run_sub_export(p, None, "replace"))   # 无视频，消费生成器
    assert len(infos) == 1                  # gr.Info 提示了跳过条数


def test_do_sub_parse_threads_detect_speakers(monkeypatch, tmp_path):
    """关闭「字幕含说话人前缀」→ 含冒号正文不被误拆，全部归到单一默认角色。"""
    from app import ui, dubbing_project as dp
    monkeypatch.setattr(dp.config, "OUTPUTS_DIR", tmp_path)
    f = tmp_path / "c.srt"
    f.write_text("1\n00:00:01,000 --> 00:00:02,000\nMeeting at 12:30 PM\n", encoding="utf-8")
    out = ui.do_sub_parse(str(f), "english", "v0", False)   # detect_speakers=False
    project = out[0]
    assert list(project["speakers"].keys()) == [dp.DEFAULT_SPEAKER]
    assert project["cues"][0]["text"] == "Meeting at 12:30 PM"   # 正文完整
    # 默认(勾选)时含时间冒号也不再吞字(收紧后的规则)
    out_on = ui.do_sub_parse(str(f), "english", "v0", True)
    assert out_on[0]["cues"][0]["text"] == "Meeting at 12:30 PM"


def test_do_sub_parse_resets_selection(monkeypatch, tmp_path):
    from app import ui, dubbing_project as dp
    monkeypatch.setattr(dp.config, "OUTPUTS_DIR", tmp_path)
    f = tmp_path / "a.srt"
    f.write_text("1\n00:00:01,000 --> 00:00:02,000\nhi\n", encoding="utf-8")
    out = ui.do_sub_parse(str(f), "english", "v0")
    # 输出顺序: project, table, _sub_sel, edit_text, edit_speaker, edit_audio
    assert out[2] is None and out[5] is None        # 选中与试听被重置


def test_run_sub_export_nothing_generated_raises_grerror(monkeypatch, tmp_path):
    import gradio as gr, pytest
    from app import ui, dubbing_project as dp
    monkeypatch.setattr(dp.config, "OUTPUTS_DIR", tmp_path)
    p = dp.build_project("1\n00:00:01,000 --> 00:00:02,000\nhi\n", "english", "v0")  # 全 pending
    with pytest.raises(gr.Error):
        list(ui._run_sub_export(p, None, "replace"))   # 不是原始 ValueError


def test_do_save_preset_collision_raises_grerror(monkeypatch, tmp_path):
    import gradio as gr, pytest
    from app import ui, presets
    monkeypatch.setattr(presets.config, "PRESETS_DIR", tmp_path)
    ui.do_save_preset("test 1", "chinese", "v0", 0.9, 0.9, 1.0)
    with pytest.raises(gr.Error):
        ui.do_save_preset("test#1", "chinese", "v0", 0.9, 0.9, 1.0)  # 同 _safe → test_1.json 冲突


def test_subtitle_handlers_serialized_on_shared_concurrency_id():
    # 字幕配音里改同一 project 的 handler 必须共享 concurrency_id，
    # 否则 Gradio queue 会并行不同事件、并发改同一 gr.State dict → 竞态污染导出
    from app import ui
    demo = ui.build_ui("zh-Hans")
    ids = [getattr(f, "concurrency_id", None) for f in demo.fns.values()]
    # 静态绑定的 5 个：parse / edit / reroll / gen-all / export（role-change 在 gr.render 内，不入静态图）
    assert ids.count("ev_sub_project") >= 5


def test_do_generate_deleted_voice_midgen_friendly_error(monkeypatch, tmp_path):
    # 生成途中所选音色被删（文件消失）→ 友好 gr.Error，而非原始 FileNotFoundError
    import gradio as gr, pytest
    from app import ui, tts_engine
    monkeypatch.setattr(ui.voice_library, "get_audio_path", lambda vid: str(tmp_path / "gone.wav"))
    monkeypatch.setattr(tts_engine, "synthesize",
                        lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("ref vanished")))
    with pytest.raises(gr.Error):
        ui.do_generate("some text", "chinese", "v0")


def test_do_generate_real_error_not_masked(monkeypatch, tmp_path):
    # ref 仍在时的真实合成错误必须原样冒泡，不能被"音色缺失"掩盖
    import pytest
    from app import ui, tts_engine
    ref = tmp_path / "here.wav"; ref.write_bytes(b"x")
    monkeypatch.setattr(ui.voice_library, "get_audio_path", lambda vid: str(ref))
    monkeypatch.setattr(tts_engine, "synthesize",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("real synth failure")))
    with pytest.raises(RuntimeError):
        ui.do_generate("text", "chinese", "v0")

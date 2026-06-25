import numpy as np
from app import tts_engine as te


def test_select_no_cuda_forces_cpu_06b(monkeypatch):
    monkeypatch.setattr(te, "_cuda_available", lambda: False)
    assert te.select_device_and_model(has_17b=True) == ("cpu", te.config.MODEL_06B)


def test_select_cuda_prefers_17b_when_present(monkeypatch):
    monkeypatch.setattr(te, "_cuda_available", lambda: True)
    assert te.select_device_and_model(has_17b=True) == ("cuda", te.config.MODEL_17B)
    assert te.select_device_and_model(has_17b=False) == ("cuda", te.config.MODEL_06B)


def test_synthesize_writes_wav(tmp_path, monkeypatch):
    monkeypatch.setattr(te.config, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(te, "_cuda_available", lambda: False)
    monkeypatch.setattr(te, "has_17b_downloaded", lambda: False)

    captured_kwargs = {}

    def _mock_raw(text, lang, ref, device, model_id, temperature=0.9, top_p=0.9, **kwargs):
        captured_kwargs["temperature"] = temperature
        captured_kwargs["top_p"] = top_p
        return [np.zeros(2400, dtype=np.float32)], 24000

    monkeypatch.setattr(te, "_raw_synthesize", _mock_raw)
    out = te.synthesize("你好", "chinese", str(tmp_path / "ref.wav"),
                        temperature=0.7, top_p=0.85)
    assert out.endswith(".wav")
    import os; assert os.path.getsize(out) > 0
    import soundfile as sf
    info = sf.info(out)
    assert info.samplerate == 24000
    assert info.frames > 0
    # Verify temperature/top_p were forwarded
    assert captured_kwargs["temperature"] == 0.7
    assert captured_kwargs["top_p"] == 0.85


def test_synthesize_calls_apply_speed_when_speed_not_1(tmp_path, monkeypatch):
    """When speed != 1.0, _apply_speed must be called; when speed == 1.0, it must NOT."""
    monkeypatch.setattr(te.config, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(te, "_cuda_available", lambda: False)
    monkeypatch.setattr(te, "has_17b_downloaded", lambda: False)
    monkeypatch.setattr(te, "_raw_synthesize",
                        lambda *a, **k: ([np.zeros(2400, dtype=np.float32)], 24000))

    apply_speed_calls = []

    def _mock_apply_speed(wav_path, speed):
        apply_speed_calls.append((wav_path, speed))
        return wav_path + ".sped"

    monkeypatch.setattr(te, "_apply_speed", _mock_apply_speed)

    # speed=1.5 → _apply_speed invoked
    apply_speed_calls.clear()
    te.synthesize("hello", "english", str(tmp_path / "ref.wav"), speed=1.5)
    assert len(apply_speed_calls) == 1
    assert apply_speed_calls[0][1] == 1.5

    # speed=1.0 → _apply_speed NOT invoked
    apply_speed_calls.clear()
    te.synthesize("hello", "english", str(tmp_path / "ref.wav"), speed=1.0)
    assert len(apply_speed_calls) == 0


def test_normalize_traditional_to_simplified():
    assert te.normalize_text("發財與麵條", "chinese") == "发财与面条"


def test_normalize_non_chinese_untouched():
    assert te.normalize_text("Bonjour", "french") == "Bonjour"


def test_apply_speed_graceful_error_fallback(monkeypatch):
    """_apply_speed should return the original path unchanged when ffmpeg fails (FileNotFoundError)."""
    def _mock_subprocess_run(*args, **kwargs):
        raise FileNotFoundError("ffmpeg not found")

    monkeypatch.setattr(te.subprocess, "run", _mock_subprocess_run)

    original_path = "/some/in.wav"
    result = te._apply_speed(original_path, 1.5)
    assert result == original_path


def test_split_text_chunks_and_lossless():
    short = te._split_text("你好。", 200)
    assert short == ["你好。"]                       # 短文本不切
    long = "句子一。" * 100                           # 400 字
    chunks = te._split_text(long, 50)
    assert len(chunks) > 1
    assert all(len(c) <= 50 for c in chunks)         # 每块不超限
    assert "".join(chunks) == long                   # 不丢字


def test_synthesize_splits_and_concatenates(tmp_path, monkeypatch):
    monkeypatch.setattr(te.config, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(te, "_cuda_available", lambda: False)
    monkeypatch.setattr(te, "has_17b_downloaded", lambda: False)
    calls = []

    def _mock_raw(text, *a, **k):
        calls.append(text)
        return [np.zeros(1200, dtype=np.float32)], 24000   # 每段 0.05s

    monkeypatch.setattr(te, "_raw_synthesize", _mock_raw)
    out = te.synthesize("测试句子。" * 80, "chinese", "ref.wav")   # 400 字 → 多段
    assert len(calls) > 1
    import soundfile as sf
    assert sf.info(out).frames > 1200                  # 拼接(含段间停顿)后比单段长


def test_warmup_calls_load(monkeypatch):
    loaded = []
    monkeypatch.setattr(te, "has_17b_downloaded", lambda: False)
    monkeypatch.setattr(te, "select_device_and_model", lambda h: ("cpu", "m"))
    monkeypatch.setattr(te, "_load", lambda mid, dev: loaded.append((mid, dev)))
    te.warmup()
    assert loaded == [("m", "cpu")]


def test_parse_subtitles_srt_vtt_lrc():
    srt = "1\n00:00:01,000 --> 00:00:03,000\n你好世界\n\n2\n00:00:04,000 --> 00:00:06,500\n第二句\n"
    c = te.parse_subtitles(srt)
    assert len(c) == 2
    assert c[0]["start"] == 1.0 and c[0]["end"] == 3.0 and c[0]["text"] == "你好世界"
    assert c[1]["start"] == 4.0 and c[1]["end"] == 6.5
    v = te.parse_subtitles("WEBVTT\n\n00:00:00.500 --> 00:00:02.000\nHello\n")
    assert len(v) == 1 and v[0]["start"] == 0.5 and v[0]["text"] == "Hello"
    lrc = te.parse_subtitles("[00:01.00]第一行\n[00:03.50]第二行\n")
    assert len(lrc) == 2 and lrc[0]["start"] == 1.0 and lrc[0]["end"] == 3.5 and lrc[1]["start"] == 3.5


def test_parse_subtitles_drops_absurd_timestamps():
    # 异常/恶意时间戳(如 99:00:00)若保留，时间轴缓冲会被撑到几十 GB → MemoryError
    srt = ("1\n99:00:00,000 --> 99:00:05,000\n你好\n\n"
           "2\n00:00:01,000 --> 00:00:02,000\n世界\n")
    cues = te.parse_subtitles(srt)
    starts = [c["start"] for c in cues]
    assert 1.0 in starts                         # 正常字幕保留
    assert 356400.0 not in starts                # 99h 的异常时间戳被丢弃
    assert all(0 <= s < 6 * 3600 for s in starts)


def test_synthesize_subtitles_assembles_timeline(tmp_path, monkeypatch):
    monkeypatch.setattr(te.config, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(te, "_cuda_available", lambda: False)
    monkeypatch.setattr(te, "has_17b_downloaded", lambda: False)

    class _Fake:
        def generate_voice_clone(self, text, **k):     # 批量：每句 0.1s
            return [np.zeros(2400, dtype=np.float32) for _ in text], 24000

    monkeypatch.setattr(te, "_load", lambda mid, dev: _Fake())
    cues = [{"start": 0.0, "end": 1.0, "text": "a"}, {"start": 2.0, "end": 3.0, "text": "b"}]
    wav, srt = te.synthesize_subtitles(cues, "chinese", "ref.wav")
    import soundfile as sf
    import os
    assert abs(sf.info(wav).duration - 2.1) < 0.05    # 第二句 2.0s 开始 + 0.1s = 2.1s
    assert os.path.exists(srt) and "-->" in open(srt, encoding="utf-8").read()


def test_parse_subtitles_ex_reports_dropped_count():
    # 超 6h 上限的条数要回报，供 UI 提示，避免长字幕被静默截断
    srt = ("1\n99:00:00,000 --> 99:00:05,000\n你好\n\n"
           "2\n00:00:01,000 --> 00:00:02,000\n世界\n")
    cues, dropped = te.parse_subtitles_ex(srt)
    assert dropped == 1 and len(cues) == 1 and cues[0]["text"] == "世界"
    cues2, dropped2 = te.parse_subtitles_ex("1\n00:00:01,000 --> 00:00:02,000\nA\n")
    assert dropped2 == 0 and len(cues2) == 1


def test_synthesize_subtitles_trims_leading_silence(tmp_path, monkeypatch):
    """字幕路径也要去 qwen-tts 偶发首尾静音：否则前导静音把语音起点推后 → 错位且误触发限速压缩。"""
    monkeypatch.setattr(te.config, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(te, "_cuda_available", lambda: False)
    monkeypatch.setattr(te, "has_17b_downloaded", lambda: False)
    sr = 24000

    class _Fake:
        def generate_voice_clone(self, text, **k):         # 每条：1s 前导静音 + 0.5s 有声
            seg = np.concatenate([np.zeros(sr, np.float32),
                                  np.full(int(sr * 0.5), 0.5, np.float32)])
            return [seg for _ in text], sr

    monkeypatch.setattr(te, "_load", lambda mid, dev: _Fake())
    wav, _srt = te.synthesize_subtitles([{"start": 0.0, "end": 5.0, "text": "a"}],
                                        "chinese", "ref.wav")
    import soundfile as sf
    audio, _ = sf.read(wav, dtype="float32")
    first = int(np.nonzero(np.abs(audio) > 0.01)[0][0]) / sr
    assert first < 0.2                 # 起点≈0(已去 1s 前导静音)；未修剪则会在 ~1.0s


def test_cues_to_srt_format():
    srt = te.cues_to_srt([(0.0, 1.5, "hi"), (2.0, 1.0, "yo")])
    assert "00:00:00,000 --> 00:00:01,500" in srt
    assert "00:00:02,000 --> 00:00:03,000" in srt
    assert "hi" in srt and "yo" in srt


def test_ensure_model_skips_when_present(monkeypatch, tmp_path):
    import sys, types
    from app import tts_engine, config
    monkeypatch.setattr(config, "MODELS_DIR", tmp_path)
    (tmp_path / "Qwen" / "Qwen3-TTS-12Hz-0___6B-Base").mkdir(parents=True)
    called = {"n": 0}
    fake = types.ModuleType("modelscope")
    fake.snapshot_download = lambda *a, **k: (called.__setitem__("n", called["n"] + 1), "X")[1]
    monkeypatch.setitem(sys.modules, "modelscope", fake)
    out = tts_engine.ensure_model("Qwen/Qwen3-TTS-12Hz-0.6B-Base")
    assert called["n"] == 0
    assert out.endswith("Qwen3-TTS-12Hz-0___6B-Base")


def test_ensure_model_downloads_when_absent(monkeypatch, tmp_path):
    import sys, types
    from app import tts_engine, config
    monkeypatch.setattr(config, "MODELS_DIR", tmp_path)
    called = {"id": None}
    fake = types.ModuleType("modelscope")
    def _dl(model_id, *a, **k):
        called["id"] = model_id
        return str(tmp_path / "downloaded")
    fake.snapshot_download = _dl
    monkeypatch.setitem(sys.modules, "modelscope", fake)
    out = tts_engine.ensure_model("Qwen/Qwen3-TTS-12Hz-0.6B-Base")
    assert called["id"] == "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
    assert out.endswith("downloaded")


def test_ensure_model_raises_clear_error_on_failure(monkeypatch, tmp_path):
    import sys, types, pytest
    from app import tts_engine, config
    monkeypatch.setattr(config, "MODELS_DIR", tmp_path)
    fake = types.ModuleType("modelscope")
    def _boom(*a, **k):
        raise OSError("network down")
    fake.snapshot_download = _boom
    monkeypatch.setitem(sys.modules, "modelscope", fake)
    with pytest.raises(RuntimeError) as ei:
        tts_engine.ensure_model("Qwen/Qwen3-TTS-12Hz-0.6B-Base")
    assert "网络" in str(ei.value) or "network" in str(ei.value).lower()


def test_add_bundled_ffmpeg_to_path_prepends_dir(monkeypatch, tmp_path):
    import os
    from app import tts_engine, config
    ff = tmp_path / "ffmpeg" / "ffmpeg.exe"
    ff.parent.mkdir(parents=True)
    ff.write_bytes(b"")
    monkeypatch.setattr(config, "ROOT", tmp_path)        # 让 _ffmpeg_exe 命中随包副本
    monkeypatch.setenv("PATH", "PREEXISTING")    # 不含 os.pathsep，跨平台(Linux ':' / Windows ';')都安全
    tts_engine.add_bundled_ffmpeg_to_path()
    parts = os.environ["PATH"].split(os.pathsep)
    assert parts[0] == str(ff.parent)                    # 随包 ffmpeg 目录被前置
    assert "PREEXISTING" in parts                        # 原 PATH 保留


def test_add_bundled_ffmpeg_to_path_idempotent(monkeypatch, tmp_path):
    import os
    from app import tts_engine, config
    ff = tmp_path / "ffmpeg" / "ffmpeg.exe"
    ff.parent.mkdir(parents=True)
    ff.write_bytes(b"")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setenv("PATH", "PREEXISTING")    # 不含 os.pathsep，跨平台(Linux ':' / Windows ';')都安全
    tts_engine.add_bundled_ffmpeg_to_path()
    tts_engine.add_bundled_ffmpeg_to_path()              # 再调一次不应重复添加
    parts = os.environ["PATH"].split(os.pathsep)
    assert parts.count(str(ff.parent)) == 1

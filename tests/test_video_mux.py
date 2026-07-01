def test_build_mux_cmd_replace_and_keep(monkeypatch):
    from app import video_mux as vm
    monkeypatch.setattr(vm.tts_engine, "_ffmpeg_exe", lambda: "FF")
    rep = vm.build_mux_cmd("v.mp4", "a.wav", "o.mp4", keep_original=False)
    assert rep[0] == "FF"
    assert "-map" in rep and "0:v" in rep and "1:a" in rep and "copy" in rep
    assert "-shortest" in rep
    # 配音短于视频时，apad 补静音到视频长度 → 视频不被 -shortest 截尾(否则丢尾部画面)
    assert rep[rep.index("-af") + 1] == "apad"
    keep = vm.build_mux_cmd("v.mp4", "a.wav", "o.mp4", keep_original=True, original_volume=0.2)
    fc = keep[keep.index("-filter_complex") + 1]
    assert "volume=0.2" in fc and "amix=inputs=2" in fc
    assert keep[keep.index("-map") + 1] == "0:v"
    assert "-shortest" in keep            # C2: keep-original also caps to video length


def test_mux_returns_none_when_ffmpeg_fails(tmp_path, monkeypatch):
    from app import video_mux as vm
    monkeypatch.setattr(vm.config, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(vm.tts_engine, "_ffmpeg_exe", lambda: "FF")

    def _boom(*a, **k):
        raise FileNotFoundError("no ffmpeg")

    monkeypatch.setattr(vm.subprocess, "run", _boom)
    assert vm.mux("v.mp4", "a.wav") is None


def test_mux_returns_path_on_success(tmp_path, monkeypatch):
    from app import video_mux as vm
    monkeypatch.setattr(vm.config, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(vm.tts_engine, "_ffmpeg_exe", lambda: "FF")

    class _OK:
        returncode = 0

    monkeypatch.setattr(vm.subprocess, "run", lambda *a, **k: _OK())
    out = vm.mux("v.mp4", "a.wav")
    assert out and out.endswith(".mp4")


def test_mux_returns_none_when_outdir_unwritable(monkeypatch):
    from app import video_mux as vm

    class _BadDir:
        def mkdir(self, parents=False, exist_ok=False):
            raise PermissionError("read-only fs")
        def __truediv__(self, other):
            return "unused"

    monkeypatch.setattr(vm.config, "OUTPUTS_DIR", _BadDir())
    assert vm.mux("v.mp4", "a.wav") is None     # C1: degrade to None, not crash

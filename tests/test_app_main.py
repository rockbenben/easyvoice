def test_main_builds_and_launches(monkeypatch):
    import os
    import app_main
    calls = {}
    class FakeBlocks:
        def launch(self, **kw): calls["launch"] = kw
    def fake_build_ui(lang="zh-Hans"):
        calls["lang"] = lang
        return FakeBlocks()
    monkeypatch.setattr(app_main.ui, "build_ui", fake_build_ui)
    # 避免测试对真实 voices/presets 目录产生 seed 副作用
    monkeypatch.setattr(app_main.seed, "seed_defaults", lambda: calls.setdefault("seeded", True))
    monkeypatch.setattr(app_main.tts_engine, "warmup", lambda: None)  # 别在测试里真加载模型
    monkeypatch.setattr(app_main.tts_engine, "ensure_model", lambda mid: None)
    monkeypatch.setattr(app_main.ui.config, "ensure_dirs", lambda: None)
    app_main.main(open_browser=True)
    assert calls.get("seeded") is True
    assert calls["launch"]["inbrowser"] is True
    assert calls["launch"]["server_port"] == 7860
    assert calls["launch"]["server_name"] == "127.0.0.1"
    assert calls["lang"] == "zh-Hans"
    assert os.environ.get("MODELSCOPE_CACHE")

def test_main_ensures_model_before_launch(monkeypatch):
    import app_main
    order = []
    class FakeBlocks:
        def launch(self, **kw): order.append("launch")
    monkeypatch.setattr(app_main.ui, "build_ui", lambda lang="zh-Hans": FakeBlocks())
    monkeypatch.setattr(app_main.seed, "seed_defaults", lambda: None)
    monkeypatch.setattr(app_main.tts_engine, "warmup", lambda: None)
    monkeypatch.setattr(app_main.ui.config, "ensure_dirs", lambda: None)
    monkeypatch.setattr(app_main.tts_engine, "ensure_model",
                        lambda mid: order.append("ensure_model"))
    app_main.main(open_browser=False)
    assert order == ["ensure_model", "launch"]

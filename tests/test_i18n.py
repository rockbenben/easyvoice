from app import i18n

def test_load_known_and_unknown():
    assert i18n.load("zh-Hans")["app.title"]
    # 未知语言退回简体
    assert i18n.load("xx") == i18n.load("zh-Hans")

def test_three_locales_share_keys():
    a = set(i18n.load("zh-Hans"))
    b = set(i18n.load("zh-Hant"))
    c = set(i18n.load("en"))
    assert a == b == c  # 三语 key 必须一致,避免漏翻

def test_t_fallback_to_key():
    assert i18n.t({}, "missing.key") == "missing.key"

def test_subtitle_dubbing_keys_present():
    from app import i18n
    keys = ["sub.roles_title", "sub.parse", "sub.gen_all", "sub.col_speaker",
            "sub.edit_title", "sub.preview", "sub.reroll", "sub.video",
            "sub.mux_mode", "sub.mux_replace", "sub.mux_keep", "sub.export",
            "sub.video_out", "sub.select_hint", "err.no_project",
            "sub.edit_apply", "sub.mux_failed", "sub.export_skipped",
            "sub.detect_speakers", "sub.detect_speakers_info"]
    for loc in ("zh-Hans", "zh-Hant", "en"):
        tb = i18n.load(loc)
        for k in keys:
            assert i18n.t(tb, k) and i18n.t(tb, k) != k, f"{loc} missing {k}"

def test_model_switch_keys_present():
    from app import i18n
    keys = ["model.title", "model.fast", "model.quality", "model.dl_hint"]
    for loc in ("zh-Hans", "zh-Hant", "en"):
        tb = i18n.load(loc)
        for k in keys:
            assert i18n.t(tb, k) and i18n.t(tb, k) != k, f"{loc} missing {k}"

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

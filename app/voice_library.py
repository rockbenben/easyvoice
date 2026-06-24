import json, shutil, uuid
from pathlib import Path
from app import config

def _index_path() -> Path:
    return config.VOICES_DIR / "index.json"

def _read() -> list:
    p = _index_path()
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))

def _write(items: list) -> None:
    config.VOICES_DIR.mkdir(parents=True, exist_ok=True)
    _index_path().write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

def add_voice(name: str, ref_audio_path: str, ref_text: str = "", front: bool = True) -> dict:
    if not name or not name.strip():
        raise ValueError("音色名称不能为空")
    config.VOICES_DIR.mkdir(parents=True, exist_ok=True)
    items = _read()
    existing = {it["id"] for it in items}
    vid = uuid.uuid4().hex[:8]
    while vid in existing:
        vid = uuid.uuid4().hex[:8]
    ext = Path(ref_audio_path).suffix or ".wav"
    dst = config.VOICES_DIR / f"{vid}{ext}"
    shutil.copyfile(ref_audio_path, dst)
    item = {"id": vid, "name": name.strip(), "audio": dst.name,
            "ref_text": (ref_text or "").strip()}
    # 用户新增默认置顶(front=True)，方便刚录的音色立刻可见；
    # 内置示例 seed 时 front=False 保持既定顺序（中文示例在最前）。
    items.insert(0, item) if front else items.append(item)
    _write(items)
    return item


def move_voice(voice_id: str, delta: int) -> None:
    """在音色库顺序里上移(delta<0)/下移(delta>0)一位；越界则不动，找不到抛 KeyError。"""
    items = _read()
    idx = next((i for i, it in enumerate(items) if it["id"] == voice_id), None)
    if idx is None:
        raise KeyError(voice_id)
    new = idx + delta
    if 0 <= new < len(items):
        items[idx], items[new] = items[new], items[idx]
        _write(items)


def get_ref_text(voice_id: str) -> str:
    """参考文字稿（ICL 模式用）。不存在或未填则返回空串（不抛错）。"""
    try:
        return _find(_read(), voice_id).get("ref_text", "") or ""
    except KeyError:
        return ""

def set_ref_text(voice_id: str, ref_text: str) -> None:
    """更新某音色的参考文字稿（ICL 用）。找不到抛 KeyError。"""
    items = _read()
    _find(items, voice_id)["ref_text"] = (ref_text or "").strip()
    _write(items)

def replace_audio(voice_id: str, ref_audio_path: str) -> None:
    """重传参考音频，覆盖该音色的原文件。找不到抛 KeyError。"""
    items = _read(); it = _find(items, voice_id)
    ext = Path(ref_audio_path).suffix or ".wav"
    dst = config.VOICES_DIR / f"{voice_id}{ext}"
    old = config.VOICES_DIR / it["audio"]
    shutil.copyfile(ref_audio_path, dst)
    if old != dst and old.exists():
        old.unlink()
    it["audio"] = dst.name
    _write(items)

def list_voices() -> list:
    return _read()

def _find(items, voice_id):
    for it in items:
        if it["id"] == voice_id:
            return it
    raise KeyError(voice_id)

def rename_voice(voice_id: str, new_name: str) -> None:
    if not new_name or not new_name.strip():
        raise ValueError("音色名称不能为空")
    items = _read(); _find(items, voice_id)["name"] = new_name.strip(); _write(items)

def get_audio_path(voice_id: str) -> str:
    items = _read()
    return str(config.VOICES_DIR / _find(items, voice_id)["audio"])

def delete_voice(voice_id: str) -> None:
    items = _read(); it = _find(items, voice_id)
    audio = config.VOICES_DIR / it["audio"]
    if audio.exists():
        audio.unlink()
    items = [x for x in items if x["id"] != voice_id]; _write(items)

from contextlib import contextmanager
import json
import logging
from pathlib import Path
import shutil
from tempfile import NamedTemporaryFile
from threading import Lock
from time import sleep
import uuid

from app import config

_LOCK = Lock()
_LOG = logging.getLogger(__name__)


def _index_path() -> Path:
    return config.VOICES_DIR / "index.json"


def _read() -> list:
    p = _index_path()
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def _discard_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        _LOG.warning("Could not remove unreferenced voice library file: %s", path, exc_info=True)


@contextmanager
def _atomic_file(target: Path):
    # 同目录暂存，关闭句柄后再替换，兼容 Windows。
    with NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}-", suffix=".tmp", delete=False) as f:
        staged = Path(f.name)
    try:
        yield staged
        # Windows 上其他读取者可能短暂占用目标文件。
        for delay in (0.01, 0.05, 0.10, None):
            try:
                staged.replace(target)
                break
            except PermissionError as error:
                if delay is None or getattr(error, "winerror", None) not in (5, 32, 33):
                    raise
                sleep(delay)
    finally:
        _discard_file(staged)


def _write(items: list) -> None:
    config.VOICES_DIR.mkdir(parents=True, exist_ok=True)
    with _atomic_file(_index_path()) as staged:
        staged.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def add_voice(name: str, ref_audio_path: str, ref_text: str = "", front: bool = True) -> dict:
    if not name or not name.strip():
        raise ValueError("音色名称不能为空")
    ext = Path(ref_audio_path).suffix or ".wav"
    with _LOCK:
        config.VOICES_DIR.mkdir(parents=True, exist_ok=True)
        items = _read()
        existing = {it["id"] for it in items}
        while True:
            vid = uuid.uuid4().hex[:8]
            dst = config.VOICES_DIR / f"{vid}{ext}"
            if vid not in existing and not dst.exists():
                break
        item = {"id": vid, "name": name.strip(), "audio": dst.name,
                "ref_text": (ref_text or "").strip()}
        # 用户新增置顶，内置示例在末尾按既定顺序追加。
        if front:
            items.insert(0, item)
        else:
            items.append(item)
        with _atomic_file(dst) as staged:
            shutil.copyfile(ref_audio_path, staged)
        try:
            _write(items)
        except Exception:
            _discard_file(dst)
            raise
    return item


def move_voice(voice_id: str, delta: int) -> None:
    """在音色库顺序里上移(delta<0)/下移(delta>0)一位；越界则不动，找不到抛 KeyError。"""
    with _LOCK:
        items = _read()
        idx = next((i for i, it in enumerate(items) if it["id"] == voice_id), None)
        if idx is None:
            raise KeyError(voice_id)
        new = idx + delta
        if 0 <= new < len(items):
            items[idx], items[new] = items[new], items[idx]
            _write(items)


def get_ref_text(voice_id: str) -> str:
    """读取旧 index.json 的 ref_text 兼容字段（ICL 克隆已移除，合成不使用）；
    不存在或未填则返回空串（不抛错）。"""
    try:
        return _find(list_voices(), voice_id).get("ref_text", "") or ""
    except KeyError:
        return ""

def set_ref_text(voice_id: str, ref_text: str) -> None:
    """写旧 index.json 的 ref_text 兼容字段（ICL 克隆已移除，合成不使用）。找不到抛 KeyError。"""
    with _LOCK:
        items = _read()
        _find(items, voice_id)["ref_text"] = (ref_text or "").strip()
        _write(items)

def replace_audio(voice_id: str, ref_audio_path: str) -> None:
    """重传参考音频，覆盖该音色的原文件。找不到抛 KeyError。"""
    ext = Path(ref_audio_path).suffix or ".wav"
    with _LOCK:
        items = _read()
        item = _find(items, voice_id)
        dst = config.VOICES_DIR / f"{voice_id}{ext}"
        old = config.VOICES_DIR / item["audio"]
        with _atomic_file(dst) as staged:
            shutil.copyfile(ref_audio_path, staged)
        if old != dst:
            item["audio"] = dst.name
            try:
                _write(items)
            except Exception:
                _discard_file(dst)
                raise
            _discard_file(old)

def list_voices() -> list:
    with _LOCK:
        return _read()

def _find(items, voice_id):
    for it in items:
        if it["id"] == voice_id:
            return it
    raise KeyError(voice_id)

def rename_voice(voice_id: str, new_name: str) -> None:
    if not new_name or not new_name.strip():
        raise ValueError("音色名称不能为空")
    with _LOCK:
        items = _read()
        _find(items, voice_id)["name"] = new_name.strip()
        _write(items)

def get_audio_path(voice_id: str) -> str:
    return str(config.VOICES_DIR / _find(list_voices(), voice_id)["audio"])

def delete_voice(voice_id: str) -> None:
    with _LOCK:
        items = _read()
        audio = config.VOICES_DIR / _find(items, voice_id)["audio"]
        _write([item for item in items if item["id"] != voice_id])
        _discard_file(audio)

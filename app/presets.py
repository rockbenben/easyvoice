import json
import re
from pathlib import Path
from app import config


def _safe(name: str) -> str:
    return re.sub(r"[^\w一-鿿-]", "_", name.strip())


def save_preset(name: str, data: dict) -> None:
    if not name or not name.strip():
        raise ValueError("预设名称不能为空")
    config.PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    target = config.PRESETS_DIR / f"{_safe(name)}.json"
    if target.exists():
        existing = json.loads(target.read_text(encoding="utf-8")).get("_name")
        if existing != name.strip():
            raise ValueError(f"预设名冲突：'{name.strip()}' 与 '{existing}' 映射到同一文件名")
    payload = dict(data)
    payload["_name"] = name.strip()
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def list_presets() -> list:
    if not config.PRESETS_DIR.exists():
        return []
    out = []
    for p in sorted(config.PRESETS_DIR.glob("*.json")):
        out.append(json.loads(p.read_text(encoding="utf-8")).get("_name", p.stem))
    return out


def get_preset(name: str) -> dict:
    path = config.PRESETS_DIR / f"{_safe(name)}.json"
    if not path.exists():
        raise ValueError(f"预设 '{name}' 不存在")
    return json.loads(path.read_text(encoding="utf-8"))


def delete_preset(name: str) -> None:
    p = config.PRESETS_DIR / f"{_safe(name)}.json"
    if p.exists():
        p.unlink()


def rename_preset(old_name: str, new_name: str) -> None:
    """重命名方案：保留原配置、换显示名(并搬到对应文件)。新名为空/与他方案重名则报错。"""
    nn = (new_name or "").strip()
    if not nn:
        raise ValueError("预设名称不能为空")
    if nn == old_name:
        return
    if nn in list_presets():
        raise ValueError(f"已存在同名方案：{nn}")
    data = get_preset(old_name)            # 原方案不存在 → ValueError
    data.pop("_name", None)
    save_preset(nn, data)                   # 写新文件(含命名冲突校验)、设 _name
    old_path = config.PRESETS_DIR / f"{_safe(old_name)}.json"
    new_path = config.PRESETS_DIR / f"{_safe(nn)}.json"
    if old_path != new_path and old_path.exists():
        old_path.unlink()

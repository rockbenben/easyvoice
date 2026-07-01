# app/dubbing_project.py
import re
import uuid
from app import tts_engine
import soundfile as sf
from app import config, voice_library

# 行首「名字：」/「Name:」前缀 → 角色；名字不含冒号、≤20 字，避免把句中冒号误判为说话人
SPEAKER_RE = re.compile(r"^\s*([^\s:：][^:：]{0,20})[:：]\s*(.+)$")
DEFAULT_SPEAKER = "默认"


def split_speaker(text):
    """提取行首说话人前缀。命中返回 (角色, 去前缀文本)；否则 (None, 原文)。"""
    m = SPEAKER_RE.match(text or "")
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None, (text or "").strip()


def build_project(content, lang, default_voice_id):
    """解析字幕→识别说话人→建可编辑工程态。每个角色默认指向 default_voice_id。"""
    cues_raw, dropped = tts_engine.parse_subtitles_ex(content)
    cues, speakers = [], {}
    for i, c in enumerate(cues_raw):
        spk, clean = split_speaker(c["text"])
        spk = spk or DEFAULT_SPEAKER
        speakers.setdefault(spk, default_voice_id)
        cues.append({"idx": i, "start": c["start"], "end": c["end"],
                     "speaker": spk, "text": clean,
                     "audio_path": None, "dur": None, "status": "pending"})
    return {"id": uuid.uuid4().hex[:8], "video_path": None, "lang": lang,
            "speakers": speakers, "cues": cues, "dropped": dropped, "params": {}}


def _cue(project, idx):
    for c in project["cues"]:
        if c["idx"] == idx:
            return c
    raise KeyError(idx)


def set_speaker_voice(project, speaker, voice_id):
    """改某角色音色 → 该角色所有 cue 标脏(需重生)。"""
    project["speakers"][speaker] = voice_id
    for c in project["cues"]:
        if c["speaker"] == speaker:
            c["status"] = "dirty"
    return project


def set_cue_text(project, idx, text):
    """改单条文本 → 仅该条标脏。"""
    c = _cue(project, idx)
    c["text"] = (text or "").strip()
    c["status"] = "dirty"
    return project


def set_cue_speaker(project, idx, speaker):
    """改单条角色（缺则登记为未指派音色 None）→ 该条标脏。"""
    speaker = (speaker or "").strip() or DEFAULT_SPEAKER
    project["speakers"].setdefault(speaker, None)
    c = _cue(project, idx)
    c["speaker"] = speaker
    c["status"] = "dirty"
    return project


def _cue_dir(project):
    d = config.OUTPUTS_DIR / project["id"]
    d.mkdir(parents=True, exist_ok=True)
    return d


def generate_cue(project, idx, seed_override=None):
    """按该 cue 角色对应音色合成单条，写缓存 wav，置 audio_path/dur/status。
    音色缺失或合成失败 → status='error'（不抛，不中断整体）。"""
    c = _cue(project, idx)
    voice_id = project["speakers"].get(c["speaker"])
    try:
        ref = voice_library.get_audio_path(voice_id)
    except Exception:
        c["status"] = "error"
        return project
    params = dict(project.get("params") or {})
    if seed_override is not None:
        params["seed"] = seed_override
    try:
        audio, sr = tts_engine.synthesize_one(c["text"], project["lang"], ref, params)
    except Exception:
        c["status"] = "error"
        return project
    try:
        path = str(_cue_dir(project) / f"cue_{c['idx']}.wav")
        sf.write(path, audio, sr)
    except Exception:
        c["status"] = "error"
        return project
    c["audio_path"], c["dur"], c["status"] = path, len(audio) / sr, "ok"
    return project


def generate_all(project, progress_cb=None):
    """只生成 pending/dirty/error 的 cue（已 ok 的跳过，省时；error 在重点生成时重试）。"""
    todo = [c for c in project["cues"] if c["status"] in ("pending", "dirty", "error")]   # 重点生成时重试失败条
    for i, c in enumerate(todo):
        generate_cue(project, c["idx"])
        if progress_cb:
            progress_cb(i + 1, len(todo))
    return project


def reroll_cue(project, idx):
    """单条重录：强制以新随机种子(seed=0)重生，得到不同的一条。"""
    return generate_cue(project, idx, seed_override=0)


def assemble(project):
    """读取各 cue 缓存音频，按时间轴拼成整段 + 对齐 SRT。返回 (wav, srt)。"""
    items = []
    for c in project["cues"]:
        if c.get("status") != "ok" or not c.get("audio_path"):   # 跳过 dirty(已改未重生)/error/pending，避免音画不一致
            continue
        audio, _sr = sf.read(c["audio_path"], dtype="float32")
        items.append({"start": c["start"], "end": c["end"],
                      "text": c["text"], "audio": audio})
    if not items:
        raise ValueError("还没有已生成的配音")
    max_speedup = float((project.get("params") or {}).get("max_speedup", 1.5))
    return tts_engine.assemble_timeline(items, max_speedup=max_speedup)

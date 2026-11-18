from contextlib import contextmanager, nullcontext
import os
from pathlib import Path
import subprocess
import shutil
import uuid
import re
import threading
import numpy as np
import soundfile as sf
from opencc import OpenCC
from app import config

_T2S = OpenCC("t2s")


def normalize_text(text: str, lang: str) -> str:
    if lang == "chinese":
        return _T2S.convert(text)
    return text


def _cuda_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False


_DOWNLOADED_DIRS = {}


def resolve_model_dir(model_id: str) -> str:
    """查找随包权重、旧版和新版 ModelScope 缓存，保留 SDK 返回的实际路径。"""
    if model_id in _DOWNLOADED_DIRS:
        local = Path(_DOWNLOADED_DIRS[model_id])
        if local.is_dir():
            return str(local)

    owner, _, name = model_id.rpartition("/")
    cache = Path(os.environ.get("MODELSCOPE_CACHE") or config.MODELS_DIR).expanduser()
    bundled = config.MODELS_DIR
    for root in (bundled, cache / "models", cache, bundled / "models"):
        for leaf in (name.replace(".", "___"), name):
            local = root / owner / leaf
            if _has_model_files(local):
                return str(local)
    return model_id


def _has_model_files(path: Path) -> bool:
    # ModelScope creates the destination before all weights have been downloaded.
    return all((path / name).is_file() for name in (
        "config.json", "model.safetensors", "speech_tokenizer/model.safetensors",
    ))


def ensure_model(model_id: str) -> str:
    """确保模型权重在本地；缺失则从 ModelScope 下载(进度走控制台)。返回本地目录。
    幂等：已存在直接返回、不下载。下载失败抛带中英提示的 RuntimeError。"""
    local = resolve_model_dir(model_id)
    if local != model_id:                      # 已在本地
        return local
    print("首次启动需下载模型（仅首次，请稍候…）\n"
          "First launch: downloading the model (one-time), please wait…", flush=True)
    try:
        from modelscope import snapshot_download
        cache = Path(os.environ.get("MODELSCOPE_CACHE") or config.MODELS_DIR).expanduser()
        # ModelScope download workers share an unsynchronized .msc index on Windows.
        path = snapshot_download(model_id, cache_dir=str(cache / "models"),
                                 max_workers=1 if os.name == "nt" else 8)
    except Exception as e:
        raise RuntimeError(
            "模型下载失败，请检查网络后重试。 "
            "Model download failed; check your network and retry. "
            f"(detail: {e})") from e
    print("模型已就绪。Model ready.", flush=True)
    _DOWNLOADED_DIRS[model_id] = path
    return path


def has_17b_downloaded() -> bool:
    return resolve_model_dir(config.MODEL_17B) != config.MODEL_17B


def is_gpu() -> bool:
    return _cuda_available()


def resolve_model_pref(pref):
    """pref: 'auto' | '0.6b' | '1.7b' → (device, model_id)。设备/默认档的唯一策略源。
    CPU 永远 0.6B(忽略 pref)；GPU: auto=有1.7B就用否则0.6B，显式档照选。
    不在此下载——下载由 _prep_generation 懒触发。"""
    if not _cuda_available():
        return ("cpu", config.MODEL_06B)
    if pref == "1.7b":
        return ("cuda", config.MODEL_17B)
    if pref == "0.6b":
        return ("cuda", config.MODEL_06B)
    return ("cuda", config.MODEL_17B if has_17b_downloaded() else config.MODEL_06B)


class _RequestRng:
    """固定种子请求的 Torch 随机状态，每个分段接着上一段采样。"""

    def __init__(self, seed, device):
        self._seed = seed
        self._cuda = device == "cuda"
        self._cpu_state = None
        self._cuda_state = None

    @contextmanager
    def activate(self):
        import torch

        # 调用方持有推理锁。仅交换 CPU 和模型使用的 cuda:0 的默认状态。
        with torch.random.fork_rng(devices=[0] if self._cuda else []):
            if self._cpu_state is None:
                self._cpu_state = torch.Generator().manual_seed(self._seed).get_state()
                if self._cuda:
                    self._cuda_state = torch.Generator(device="cuda:0").manual_seed(self._seed).get_state()
            torch.set_rng_state(self._cpu_state)
            if self._cuda:
                torch.cuda.set_rng_state(self._cuda_state, device=0)
            yield
            self._cpu_state = torch.get_rng_state()
            if self._cuda:
                self._cuda_state = torch.cuda.get_rng_state(device=0)


def _prep_generation(model_pref, seed):
    """两个合成入口（synthesize / synthesize_one）的公共前置：
    解析模型档位 → 仅 1.7B 懒下载（0.6B 是常驻基座、启动已 ensure，引擎路径不触碰 ensure_model，
    测试/CI 无下载风险）→ 若 seed>0 则构造隔离的 _RequestRng 保持跨分段/跨句采样连续性，0 则自然变化。
    返回 (device, source, rng)。"""
    device, model_id = resolve_model_pref(model_pref)
    source = ensure_model(model_id) if model_id == config.MODEL_17B else resolve_model_dir(model_id)
    seed = int(seed or 0)
    return device, source, _RequestRng(seed, device) if seed > 0 else None


_MODEL_CACHE = {}
# 跨 Tab 串行化前向和冷加载，两者都可能消耗 Torch 默认随机状态。
_INFER_LOCK = threading.Lock()


def _load(source: str, device: str):
    key = (source, device)
    if key in _MODEL_CACHE:
        return _MODEL_CACHE[key]
    with _INFER_LOCK:                      # 双检锁：预热线程与生成请求不会重复加载
        if key not in _MODEL_CACHE:
            import torch
            from qwen_tts import Qwen3TTSModel  # 见 SPIKE §3
            device_map = "cuda:0" if device == "cuda" else "cpu"
            dtype = torch.bfloat16 if device == "cuda" else torch.float32
            _MODEL_CACHE[key] = Qwen3TTSModel.from_pretrained(
                source, device_map=device_map, dtype=dtype)
    return _MODEL_CACHE[key]


def warmup() -> None:
    """后台预加载模型，避免首次生成时的加载等待；出错静默(真正生成时会再报)。"""
    try:
        device, model_id = resolve_model_pref("auto")
        _load(resolve_model_dir(model_id), device)
    except Exception:
        pass


def _raw_synthesize(text, lang, ref_audio_path, device, source,
                    temperature=0.9, top_p=0.9, top_k=50,
                    repetition_penalty=1.0, max_new_tokens=2048, ref_text=None, rng=None):
    model = _load(source, device)
    # 见 SPIKE §5a:返回 (List[np.ndarray], 24000)
    kwargs = dict(
        text=text, language=lang, ref_audio=ref_audio_path,
        non_streaming_mode=True, do_sample=True,
        temperature=temperature, top_p=top_p, top_k=top_k,
        repetition_penalty=repetition_penalty, max_new_tokens=max_new_tokens,
    )
    # 始终用 x-vector 克隆模式。ICL(x_vector_only_mode=False + ref_text) 实测会把参考文字稿
    # 诵进输出(+ref_text 时长)，已移除该路径；ref_text 参数保留但忽略。
    kwargs.update(x_vector_only_mode=True)
    with _INFER_LOCK, (rng.activate() if rng is not None else nullcontext()):
        wavs, sr = model.generate_voice_clone(**kwargs)
    return wavs, sr


def _ffmpeg_exe() -> str:
    """定位 ffmpeg：优先用随整合包附带的副本，其次系统 PATH。
    都没有时返回 'ffmpeg'，由 _apply_speed 的异常兜底优雅降级。"""
    for c in (config.ROOT / "ffmpeg" / "ffmpeg.exe",
              config.ROOT / "runtime" / "Library" / "bin" / "ffmpeg.exe"):
        if c.exists():
            return str(c)
    return shutil.which("ffmpeg") or "ffmpeg"


def add_bundled_ffmpeg_to_path() -> None:
    """把 ffmpeg 所在目录加进 PATH，让 pydub / gradio / torchaudio 等也能找到它。
    整合包里 ffmpeg 只在 ffmpeg\\ 子目录、不在 PATH，导致 gradio(pydub) 转码录音失败 →
    “录制音色后无法播放”。这里在启动时把它前置到 PATH。幂等；找不到具体 ffmpeg 则不动。"""
    import os
    exe = _ffmpeg_exe()
    if not os.path.isabs(exe) or not os.path.exists(exe):
        return
    d = os.path.dirname(exe)
    if d not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")


def _apply_speed(wav_path: str, speed: float) -> str:
    """Post-process WAV with ffmpeg atempo to change speed (pitch-preserving).

    speed is clamped to [0.5, 2.0]. Returns the output path (same dir, _spd suffix).
    On any error (ffmpeg missing, non-zero exit) returns original path unchanged.
    """
    speed = max(0.5, min(2.0, speed))
    import os
    base, ext = os.path.splitext(wav_path)
    out_path = f"{base}_spd{ext}"
    try:
        result = subprocess.run(
            [_ffmpeg_exe(), "-y", "-i", wav_path,
             "-filter:a", f"atempo={speed}", out_path],
            capture_output=True, timeout=60
        )
        if result.returncode != 0:
            return wav_path
        return out_path
    except Exception:
        return wav_path


_SPLIT_THRESHOLD = 200   # 超过此字符数则自动分段生成，避免单次超长截断/劣化


def _split_text(text: str, max_chars: int = _SPLIT_THRESHOLD) -> list:
    """按句末标点切句、贪心打包成 ≤max_chars 的小段；超长句再按逗号、最后按字数硬切。"""
    text = (text or "").strip()
    if not text:
        return []
    sents = [s for s in re.split(r'(?<=[。！？!?；;\n])', text) if s.strip()]
    pieces = []
    for s in sents:
        if len(s) <= max_chars:
            pieces.append(s)
            continue
        buf = ""                                       # 超长句：先按逗号切
        for x in re.split(r'(?<=[，,、])', s):
            if len(x) > max_chars:                     # 仍超长 → 按字数硬切
                if buf:
                    pieces.append(buf); buf = ""
                for i in range(0, len(x), max_chars):
                    pieces.append(x[i:i + max_chars])
            elif buf and len(buf) + len(x) > max_chars:
                pieces.append(buf); buf = x
            else:
                buf += x
        if buf:
            pieces.append(buf)
    chunks, cur = [], ""                                # 把碎句贪心拼回 ≤max_chars 的块
    for p in pieces:
        if cur and len(cur) + len(p) > max_chars:
            chunks.append(cur); cur = p
        else:
            cur += p
    if cur.strip():
        chunks.append(cur)
    return chunks or [text]


def _trim_silence(audio, sr, thresh=0.01, pad_ms=80):
    """去掉首尾异常长的静音(qwen-tts 偶发)；保留 pad_ms 余量，避免切到气口/弱音。"""
    if audio is None or audio.size == 0:
        return audio
    idx = np.nonzero(np.abs(audio) > thresh)[0]
    if idx.size == 0:
        return audio[:int(sr * 0.1)]            # 整段都是静音 → 留 0.1s 占位
    pad = int(sr * pad_ms / 1000)
    return audio[max(0, idx[0] - pad): min(audio.size, idx[-1] + 1 + pad)]


def synthesize(text, lang, ref_audio_path,
               temperature=0.9, top_p=0.9, speed=1.0,
               top_k=50, repetition_penalty=1.0, max_new_tokens=2048,
               ref_text=None, seed=0, model="auto", progress_cb=None) -> str:
    text = normalize_text(text, lang)
    device, source, rng = _prep_generation(model, seed)
    chunks = _split_text(text) if len(text) > _SPLIT_THRESHOLD else [text]
    if not chunks:                       # 全空白/纯标点超长 → 退回单段，避免 concatenate([]) 崩溃
        chunks = [text]
    total_chars = sum(len(c) for c in chunks) or 1
    done_chars, segs, sr = 0, [], 24000
    if progress_cb:
        progress_cb(0, total_chars)                     # 进度：先报总字数
    for ch in chunks:                                   # 逐段用同一音色生成
        wavs, sr = _raw_synthesize(ch, lang, ref_audio_path, device, source,
                                   temperature=temperature, top_p=top_p, top_k=top_k,
                                   repetition_penalty=repetition_penalty,
                                   max_new_tokens=max_new_tokens, ref_text=ref_text, rng=rng)
        segs.append(_trim_silence(np.asarray(wavs[0], dtype=np.float32), sr))   # 去首尾异常静音
        done_chars += len(ch)
        if progress_cb:
            progress_cb(done_chars, total_chars)
    if len(segs) == 1:
        audio = segs[0]
    else:                                               # 多段拼接，段间留 0.25s 停顿
        gap = np.zeros(int(sr * 0.25), dtype=np.float32)
        joined = []
        for i, w in enumerate(segs):
            if i:
                joined.append(gap)
            joined.append(w)
        audio = np.concatenate(joined)
    config.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out = config.OUTPUTS_DIR / f"out_{uuid.uuid4().hex[:8]}.wav"
    sf.write(str(out), audio, sr)
    wav_path = str(out)
    if speed != 1.0:
        wav_path = _apply_speed(wav_path, speed)
    return wav_path


# ── 字幕配音：解析字幕 + 按时间轴拼接 ─────────────────────────────────
def _parse_ts(s: str) -> float:
    """'HH:MM:SS,mmm' / 'MM:SS.mmm' → 秒。"""
    s = s.strip().replace(",", ".")
    parts = s.split(":")
    if len(parts) == 3:
        h, m, sec = parts
    elif len(parts) == 2:
        h, m, sec = "0", parts[0], parts[1]
    else:
        return 0.0
    ms = "0"
    if "." in sec:
        sec, ms = sec.split(".", 1)
    return int(h) * 3600 + int(m) * 60 + int(sec) + int((ms + "000")[:3]) / 1000.0


_MAX_TIMELINE_SEC = 6 * 3600   # 时间轴上限(6h)：挡住异常/恶意时间戳(如 99:00:00)导致的超大内存分配
_LRC_TIME = re.compile(r"\s*\[(\d{1,2}):(\d{2})(?:[.:](\d{1,3}))?\]")


def parse_subtitles(content: str) -> list:
    """解析 SRT / VTT / LRC → [{'start':秒,'end':秒,'text':str}]，按开始时间排序。"""
    return parse_subtitles_ex(content)[0]


def parse_subtitles_ex(content: str):
    """同 parse_subtitles，但额外返回因超出时间轴上限(_MAX_TIMELINE_SEC)被丢弃的条数，
    供 UI 提示，避免超长字幕被静默截断。返回 (cues, dropped)。"""
    content = (content or "").replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿").strip()
    cues = []
    if "-->" in content:                                   # SRT / VTT
        for block in re.split(r"\n[ \t]*\n", content):
            lines = block.split("\n")
            ti = next((i for i, l in enumerate(lines) if "-->" in l), None)
            if ti is None:
                continue
            try:
                a, b = lines[ti].split("-->")
                start = _parse_ts(a)
                end = _parse_ts(re.split(r"\s", b.strip())[0])   # 去掉 VTT 行尾 settings
            except Exception:
                continue
            text = " ".join(l.strip() for l in lines[ti + 1:] if l.strip())
            if text and end > start:
                cues.append({"start": start, "end": end, "text": text})
    else:                                                  # LRC
        raw = []
        for line in content.split("\n"):
            pos, starts = 0, []
            while match := _LRC_TIME.match(line, pos):
                minutes, seconds, fraction = match.groups()
                millis = int((fraction or "0").ljust(3, "0"))
                starts.append(int(minutes) * 60 + int(seconds) + millis / 1000)
                pos = match.end()
            text = line[pos:].strip()
            if text:
                raw.extend((start, text) for start in starts)
        raw.sort(key=lambda x: x[0])
        for i, (t, txt) in enumerate(raw):
            end = raw[i + 1][0] if i + 1 < len(raw) else t + 4.0
            if txt:
                cues.append({"start": t, "end": end, "text": txt})
    # 丢弃开始时间超出合理上限的字幕(异常/恶意时间戳)，否则时间轴缓冲会被撑到几十 GB
    kept = [c for c in cues if 0 <= c["start"] < _MAX_TIMELINE_SEC]
    dropped = len(cues) - len(kept)
    kept.sort(key=lambda c: c["start"])
    return kept, dropped


def _atempo_np(audio, sr, ratio):
    """对 numpy 音频做保音高变速(ffmpeg atempo)；失败则原样返回。"""
    ratio = max(0.5, min(2.0, float(ratio)))
    if abs(ratio - 1.0) < 0.02:
        return audio
    import os
    import tempfile
    d = tempfile.mkdtemp()
    tin, tout = os.path.join(d, "i.wav"), os.path.join(d, "o.wav")
    try:
        sf.write(tin, audio, sr)
        r = subprocess.run([_ffmpeg_exe(), "-y", "-i", tin, "-filter:a", f"atempo={ratio}", tout],
                           capture_output=True, timeout=60)
        if r.returncode == 0 and os.path.exists(tout):
            a, _ = sf.read(tout, dtype="float32")
            return np.asarray(a, dtype=np.float32)
        return audio
    except Exception:
        return audio
    finally:
        for f in (tin, tout):
            try:
                os.remove(f)
            except Exception:
                pass
        try:
            os.rmdir(d)
        except Exception:
            pass


def _cue_token_cap(text: str, user_max: int) -> int:
    """按文本长度给单条字幕的 max_new_tokens 封顶，防止某条没收到 EOS 而跑飞出几十秒杂音。
    中文约 2.8 token/字，这里给 ~1.8 倍余量(不会截断正常语音，又能挡住跑飞)。"""
    return min(int(user_max), max(80, len(text or "") * 5))


def _fmt_srt_ts(sec: float) -> str:
    total_ms = int(round(max(0.0, float(sec)) * 1000))
    h = total_ms // 3600000
    m = (total_ms // 60000) % 60
    s = (total_ms // 1000) % 60
    ms = total_ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def cues_to_srt(cues) -> str:
    """[(start_sec, dur_sec, text)] → SRT 文本(反映实际生成时长，便于配视频时校准)。"""
    out = []
    for i, (start, dur, text) in enumerate(cues, 1):
        out.append(str(i))
        out.append(f"{_fmt_srt_ts(start)} --> {_fmt_srt_ts(start + dur)}")
        out.append(str(text).strip())
        out.append("")
    return "\n".join(out)


def synthesize_one(text, lang, ref_audio_path, params=None):
    """单条合成原语：归一文本→按文本长度封顶 token→生成→去首尾异常静音。
    「生成全部」与「单条重录」共用此函数，保证行为一致。返回 (audio, sr)。"""
    params = params or {}
    text = normalize_text(text, lang)
    device, source, rng = _prep_generation(params.get("model", "auto"), params.get("seed", 0))
    cap = _cue_token_cap(text, int(params.get("max_new_tokens", 2048)))
    wavs, sr = _raw_synthesize(              # 复用统一推理包装(内含 _INFER_LOCK 与克隆模式 kwargs)
        text, lang, ref_audio_path, device, source,
        temperature=params.get("temperature", 0.9), top_p=params.get("top_p", 0.9),
        top_k=params.get("top_k", 50),
        repetition_penalty=params.get("repetition_penalty", 1.0),
        max_new_tokens=cap, rng=rng)
    return _trim_silence(np.asarray(wavs[0], dtype=np.float32), sr), sr


def assemble_timeline(items, max_speedup=1.5, sr=24000):
    """把若干已生成(已 trim)的单条音频按 start 放到时间轴；超时长则限速压缩贴轴；
    导出反映实际时长的对齐 SRT。items: [{'start','end','text','audio'}]。返回 (wav, srt)。"""
    placed, new_cues = [], []
    for c in items:
        audio = np.asarray(c["audio"], dtype=np.float32)
        slot = max(0.0, float(c["end"]) - float(c["start"]))
        dur = len(audio) / sr
        if slot > 0 and dur > slot:                    # 超时→保音高限速压缩
            audio = _atempo_np(audio, sr, min(max_speedup, dur / slot))
        placed.append((max(0, int(float(c["start"]) * sr)), audio))
        new_cues.append((float(c["start"]), len(audio) / sr, c["text"]))
    total = max((s + len(a) for s, a in placed), default=sr // 10)
    buf = np.zeros(total, dtype=np.float32)
    for s, a in placed:                                # 重叠则后者覆盖
        buf[s:s + len(a)] = a
    config.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    base = config.OUTPUTS_DIR / f"sub_{uuid.uuid4().hex[:8]}"
    wav_path, srt_path = str(base) + ".wav", str(base) + ".srt"
    sf.write(wav_path, buf, sr)
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(cues_to_srt(new_cues))
    return wav_path, srt_path

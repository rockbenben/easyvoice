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


def resolve_model_dir(model_id: str) -> str:
    """ModelScope 下载后目录名把 '.' 写成 '___'(Windows 符号链接失败),
    且嵌套在 <org>/ 下(见 SPIKE §1)。返回本地实际目录;
    不存在则原样返回 model_id(交给 from_pretrained 自行解析)。"""
    parts = model_id.split("/")
    name = parts[-1].replace(".", "___")
    if len(parts) >= 2:
        local = config.MODELS_DIR / parts[-2] / name
    else:
        local = config.MODELS_DIR / name
    return str(local) if local.exists() else model_id


def ensure_model(model_id: str) -> str:
    """确保模型权重在本地；缺失则从 ModelScope 下载(进度走控制台)。返回本地目录。
    幂等：已存在直接返回、不下载。下载失败抛带中英提示的 RuntimeError。"""
    local = resolve_model_dir(model_id)
    if local != model_id:                      # 已在本地
        return local
    print("首次启动需下载模型（约 1.8GB，仅首次），请稍候…\n"
          "First launch: downloading the model (~1.8 GB), please wait…", flush=True)
    try:
        from modelscope import snapshot_download
        path = snapshot_download(model_id)     # 自带 tqdm 进度
    except Exception as e:
        raise RuntimeError(
            "模型下载失败，请检查网络后重试。 "
            "Model download failed; check your network and retry. "
            f"(detail: {e})") from e
    print("模型已就绪。Model ready.", flush=True)
    return path


def has_17b_downloaded() -> bool:
    return resolve_model_dir(config.MODEL_17B) != config.MODEL_17B


def is_gpu() -> bool:
    return _cuda_available()


def select_device_and_model(has_17b: bool) -> tuple:
    if _cuda_available():
        return ("cuda", config.MODEL_17B if has_17b else config.MODEL_06B)
    return ("cpu", config.MODEL_06B)


_MODEL_CACHE = {}
_LOAD_LOCK = threading.Lock()


def _load(model_id: str, device: str):
    key = (model_id, device)
    if key in _MODEL_CACHE:
        return _MODEL_CACHE[key]
    with _LOAD_LOCK:                       # 双检锁：预热线程与生成请求不会重复加载
        if key not in _MODEL_CACHE:
            import torch
            from qwen_tts import Qwen3TTSModel  # 见 SPIKE §3
            device_map = "cuda:0" if device == "cuda" else "cpu"
            dtype = torch.bfloat16 if device == "cuda" else torch.float32
            _MODEL_CACHE[key] = Qwen3TTSModel.from_pretrained(
                resolve_model_dir(model_id), device_map=device_map, dtype=dtype)
    return _MODEL_CACHE[key]


def warmup() -> None:
    """后台预加载模型，避免首次生成时的加载等待；出错静默(真正生成时会再报)。"""
    try:
        device, model_id = select_device_and_model(has_17b_downloaded())
        _load(model_id, device)
    except Exception:
        pass


def _raw_synthesize(text, lang, ref_audio_path, device, model_id,
                    temperature=0.9, top_p=0.9, top_k=50,
                    repetition_penalty=1.0, max_new_tokens=2048, ref_text=None):
    model = _load(model_id, device)
    # 见 SPIKE §5a:返回 (List[np.ndarray], 24000)
    kwargs = dict(
        text=text, language=lang, ref_audio=ref_audio_path,
        non_streaming_mode=True, do_sample=True,
        temperature=temperature, top_p=top_p, top_k=top_k,
        repetition_penalty=repetition_penalty, max_new_tokens=max_new_tokens,
    )
    if ref_text and str(ref_text).strip():
        # ICL 高保真模式：提供参考音频的文字稿（SPIKE §5a）
        kwargs.update(x_vector_only_mode=False, ref_text=str(ref_text).strip())
    else:
        kwargs.update(x_vector_only_mode=True)
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


def synthesize(text, lang, ref_audio_path,
               temperature=0.9, top_p=0.9, speed=1.0,
               top_k=50, repetition_penalty=1.0, max_new_tokens=2048,
               ref_text=None, seed=0, progress_cb=None) -> str:
    text = normalize_text(text, lang)
    device, model_id = select_device_and_model(has_17b_downloaded())
    if seed and int(seed) > 0:                          # 固定种子 → 同参数可复现
        import torch
        torch.manual_seed(int(seed))
    chunks = _split_text(text) if len(text) > _SPLIT_THRESHOLD else [text]
    total_chars = sum(len(c) for c in chunks) or 1
    done_chars, segs, sr = 0, [], 24000
    if progress_cb:
        progress_cb(0, total_chars)                     # 进度：先报总字数
    for ch in chunks:                                   # 逐段用同一音色生成
        wavs, sr = _raw_synthesize(ch, lang, ref_audio_path, device, model_id,
                                   temperature=temperature, top_p=top_p, top_k=top_k,
                                   repetition_penalty=repetition_penalty,
                                   max_new_tokens=max_new_tokens, ref_text=ref_text)
        segs.append(np.asarray(wavs[0], dtype=np.float32))
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


def parse_subtitles(content: str) -> list:
    """解析 SRT / VTT / LRC → [{'start':秒,'end':秒,'text':str}]，按开始时间排序。"""
    content = (content or "").replace("\r\n", "\n").replace("\r", "\n").strip()
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
            mm = re.match(r"\s*\[(\d{1,2}):(\d{2})(?:[.:](\d{1,2}))?\]\s*(.+)", line)
            if mm:
                t = int(mm.group(1)) * 60 + int(mm.group(2)) + int(mm.group(3) or 0) / 100.0
                raw.append((t, mm.group(4).strip()))
        raw.sort(key=lambda x: x[0])
        for i, (t, txt) in enumerate(raw):
            end = raw[i + 1][0] if i + 1 < len(raw) else t + 4.0
            if txt:
                cues.append({"start": t, "end": end, "text": txt})
    cues.sort(key=lambda c: c["start"])
    return cues


def _atempo_np(audio, sr, ratio):
    """对 numpy 音频做保音高变速(ffmpeg atempo)；失败则原样返回。"""
    ratio = max(0.5, min(2.0, float(ratio)))
    if abs(ratio - 1.0) < 0.02:
        return audio
    import os
    import tempfile
    d = tempfile.mkdtemp()
    tin, tout = os.path.join(d, "i.wav"), os.path.join(d, "o.wav")
    sf.write(tin, audio, sr)
    try:
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
    sec = max(0.0, float(sec))
    h, m, s = int(sec // 3600), int(sec % 3600 // 60), int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms >= 1000:
        s += 1
        ms -= 1000
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


_SUB_GROUP = 6   # 字幕按小批生成：兼顾批量提速与"已合成 X 条"的进度反馈


def _gen_cue_group(model, texts, lang, ref_audio_path, icl, rt,
                   temperature, top_p, top_k, repetition_penalty, user_max):
    """一小批字幕：优先一次批量生成；失败则逐条(每条按自身长度更紧封顶)。返回音频数组列表。"""
    n = len(texts)
    common = dict(non_streaming_mode=True, do_sample=True, temperature=temperature,
                  top_p=top_p, top_k=top_k, repetition_penalty=repetition_penalty)
    try:                                                   # 批量：本批一次生成
        cap = max(_cue_token_cap(t, user_max) for t in texts)
        kw = dict(text=texts, language=[lang] * n, ref_audio=[ref_audio_path] * n,
                  max_new_tokens=cap, **common)
        kw.update(x_vector_only_mode=[False] * n, ref_text=[rt] * n) if icl \
            else kw.update(x_vector_only_mode=[True] * n)
        wavs, _ = model.generate_voice_clone(**kw)
        return [np.asarray(w, dtype=np.float32) for w in wavs]
    except Exception:                                      # 回退：逐条(每条更紧封顶)
        out = []
        for t in texts:
            kw = dict(text=t, language=lang, ref_audio=ref_audio_path,
                      max_new_tokens=_cue_token_cap(t, user_max), **common)
            kw.update(x_vector_only_mode=False, ref_text=rt) if icl \
                else kw.update(x_vector_only_mode=True)
            wavs, _ = model.generate_voice_clone(**kw)
            out.append(np.asarray(wavs[0], dtype=np.float32))
        return out


def synthesize_subtitles(cues, lang, ref_audio_path,
                         temperature=0.9, top_p=0.9, top_k=50,
                         repetition_penalty=1.0, max_new_tokens=2048,
                         ref_text=None, seed=0, max_speedup=1.5, progress_cb=None):
    """逐条字幕用同一音色生成(按小批批量、失败回退逐条)；按文本长度封顶防跑飞，超时则限速
    压缩，按开始时间拼到时间轴。返回 (wav 路径, 对齐后的 srt 路径)。"""
    device, model_id = select_device_and_model(has_17b_downloaded())
    if seed and int(seed) > 0:
        import torch
        torch.manual_seed(int(seed))
    valid = [c for c in cues if normalize_text(c.get("text", ""), lang).strip()]
    if not valid:
        raise ValueError("字幕没有可用内容")
    texts = [normalize_text(c["text"], lang) for c in valid]
    icl = bool(ref_text and str(ref_text).strip())
    rt = str(ref_text).strip() if icl else None
    model = _load(model_id, device)
    sr = 24000
    if progress_cb:
        progress_cb(0, len(texts))                         # 进度：先报总条数
    audios = []
    for g in range(0, len(texts), _SUB_GROUP):             # 按小批生成，逐批报进度
        audios.extend(_gen_cue_group(model, texts[g:g + _SUB_GROUP], lang, ref_audio_path,
                                     icl, rt, temperature, top_p, top_k,
                                     repetition_penalty, max_new_tokens))
        if progress_cb:
            progress_cb(min(g + _SUB_GROUP, len(texts)), len(texts))
    placed, new_cues = [], []
    for c, audio in zip(valid, audios):
        slot = max(0.0, float(c["end"]) - float(c["start"]))
        dur = len(audio) / sr
        if slot > 0 and dur > slot:                        # 超时 → 限速压缩贴轴
            audio = _atempo_np(audio, sr, min(max_speedup, dur / slot))
        placed.append((max(0, int(float(c["start"]) * sr)), audio))
        new_cues.append((float(c["start"]), len(audio) / sr, c["text"]))
    total = max(s + len(a) for s, a in placed)
    buf = np.zeros(total, dtype=np.float32)
    for s, a in placed:                                    # 放到时间轴(重叠则后者覆盖)
        buf[s:s + len(a)] = a
    config.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    base = config.OUTPUTS_DIR / f"sub_{uuid.uuid4().hex[:8]}"
    wav_path, srt_path = str(base) + ".wav", str(base) + ".srt"
    sf.write(wav_path, buf, sr)
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(cues_to_srt(new_cues))
    return wav_path, srt_path

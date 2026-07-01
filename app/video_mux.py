# app/video_mux.py
import subprocess
import uuid
from app import config, tts_engine


def build_mux_cmd(video_path, audio_path, out_path,
                  keep_original=False, original_volume=0.15):
    """构造 ffmpeg 命令：替换原声(默认) 或 保留原声压低后与配音混合。"""
    ff = tts_engine._ffmpeg_exe()
    if keep_original:
        return [ff, "-y", "-i", video_path, "-i", audio_path,
                "-filter_complex",
                f"[0:a]volume={original_volume}[a0];"
                f"[a0][1:a]amix=inputs=2:duration=longest[a]",
                "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-shortest", out_path]
    # 配音常短于视频(最后一句字幕多在片尾前结束)。apad 用静音把配音补到无限长，
    # 再由 -shortest 收到视频长度 → 输出恒等于视频时长：短则补静音到片尾(不截画面)，
    # 长则仍按视频截。缺 apad 时 -shortest 会把视频截到配音长度、丢尾部画面。
    return [ff, "-y", "-i", video_path, "-i", audio_path,
            "-map", "0:v", "-map", "1:a", "-c:v", "copy",
            "-af", "apad", "-shortest", out_path]


def mux(video_path, audio_path, keep_original=False, original_volume=0.15):
    """把配音合进视频，输出 mp4。ffmpeg 缺失/失败/输出目录不可写 → 返回 None（调用方降级为只给 wav+srt）。"""
    try:
        config.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = str(config.OUTPUTS_DIR / f"dub_{uuid.uuid4().hex[:8]}.mp4")
        cmd = build_mux_cmd(video_path, audio_path, out_path, keep_original, original_volume)
        r = subprocess.run(cmd, capture_output=True, timeout=1800)
        if r.returncode == 0:
            return out_path
    except Exception:
        pass
    return None

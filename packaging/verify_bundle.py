"""Exercise the extracted bundle with its own Python and DLLs."""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

import numpy as np
import soundfile as sf
import torch

import app_main
from app import config, tts_engine


def main(variant):
    if (torch.version.cuda is not None) != (variant == "gpu"):
        raise RuntimeError(f"Unexpected Torch build for {variant}: {torch.__version__}")
    bundled = tts_engine.resolve_model_dir(config.MODEL_06B) != config.MODEL_06B
    if bundled != (variant == "gpu"):
        raise RuntimeError(f"Unexpected bundled model state for {variant}")

    config.ensure_dirs()
    tts_engine.add_bundled_ffmpeg_to_path()
    model_dir = tts_engine.ensure_model(config.MODEL_06B)
    if variant == "cpu":
        subprocess.run(
            [sys.executable, "-E", "-s", "-B", "-c", """
import sys
from pathlib import Path
from app import config, tts_engine

local = tts_engine.resolve_model_dir(config.MODEL_06B)
if local == config.MODEL_06B or not Path(local).samefile(sys.argv[1]):
    raise RuntimeError("Downloaded model was not found in the cache after restart")
""", model_dir],
            check=True,
        )
    app_main.ui.build_ui("zh-Hans")
    reference = config.ROOT / "app/assets/demo_voices/voice_en1.wav"
    wav = tts_engine.synthesize("EasyVoice is ready.", "english", str(reference), seed=42, max_new_tokens=96)
    audio, rate = sf.read(wav)
    if rate != 24000 or not audio.size or not np.isfinite(audio).all() or not np.any(audio):
        raise RuntimeError("Bundled model failed to produce a playable WAV")

    tools = config.ROOT / "ffmpeg"
    subprocess.run([tools / "ffprobe.exe", "-v", "error", "-show_entries", "stream=codec_name", wav], check=True)
    subprocess.run([tools / "ffmpeg.exe", "-v", "error", "-i", wav, "-f", "null", "-"], check=True)


if __name__ == "__main__":
    main(sys.argv[1])

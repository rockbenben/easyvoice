# EasyVoice (易声)

[简体中文](README.md) | **English**

## Overview

**EasyVoice** is a local, **multilingual**, dead-simple dubbing / voice-cloning tool built on [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) (Chinese-first UI, works out of the box):

- **Multilingual TTS / cloning** — 10 languages: Chinese, English, Japanese, Korean, German, French, Russian, Portuguese, Spanish, Italian. Clone a voice from just ~3 seconds of reference audio.
- **Subtitle dubbing** — upload subtitles (SRT / VTT / LRC) and generate one continuous, timeline-aligned voice-over, with the aligned subtitles exported back.
- **Runs locally** — fully local inference, nothing uploaded to the cloud.
- **GPU-adaptive** — uses CUDA automatically when a GPU is present, falls back to CPU otherwise.
- **Zero-setup** — end users unzip the all-in-one bundle and double-click to launch; developers can run from source.

---

## For end users (3 steps)

### 1. Download & unzip
Download the all-in-one bundle and unzip it locally.

### 2. Double-click to launch
Run `Start EasyVoice.bat` in the folder. The first launch takes ~30s (model loading).

> **Note:** Double-click launch requires the bundle (which ships its own `runtime/` and model). You can build the bundle yourself with `build.ps1`; a prebuilt bundle, if provided, is on [Releases](../../releases). To run from source, see **For developers** below.

### 3. Use it in the browser
A browser opens automatically at `http://127.0.0.1:7860`, with four tabs:

- **Dubbing** — type text, pick a language and reference voice, click generate
- **Subtitle dubbing** — upload a subtitle file, generate timeline-aligned audio
- **My Voices** — manage reference voices (add / delete / rename / reorder)
- **Presets** — save frequently used parameter presets (language + voice) for quick reuse

---

## For developers (run from source)

### Requirements
- **Python 3.12** (the example uses a conda env named `easyvoice`)

### Setup

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install CUDA PyTorch** (if you have a GPU)
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
   ```
   (No GPU? Skip this — the CPU build installs in step 1.)

3. **(Optional) ffmpeg for speed control** — put `ffmpeg.exe` on PATH or in the project `ffmpeg/` folder. If missing, speed ≠ 1.0 gracefully degrades.

4. **Model** — downloaded automatically from ModelScope into `models/` on first run. Set `MODELSCOPE_CACHE` to customize the cache path.

### Run
```bash
python app_main.py
```
A browser opens at `http://127.0.0.1:7860`.

### Tests
```bash
python -m pytest -q
```
The full regression suite should pass.

---

## Project layout

```
easyvoice/
├── app/                  # Core modules
│   ├── config.py         # Global config (paths, model id, supported languages)
│   ├── i18n.py & i18n/   # UI localization (Simplified / Traditional Chinese / English)
│   ├── voice_library.py  # Voice library (CRUD + reorder)
│   ├── presets.py        # Preset management (save / load parameter sets)
│   ├── seed.py           # First-run sample voices / presets
│   ├── tts_engine.py     # TTS engine (load, synthesize, chunking, subtitle align, speed)
│   └── ui.py             # Gradio UI (four tabs)
├── app_main.py           # Entry point
├── build.ps1             # Bundle builder (conda-pack runtime + model + ffmpeg)
├── Start EasyVoice.bat   # Windows launcher
├── requirements.txt      # Python dependencies
├── pyproject.toml        # pytest config
└── tests/                # Automated tests
```

> `models/`, `voices/`, `presets/`, `outputs/`, `runtime/`, `ffmpeg/`, `dist/` are runtime / build artifacts and are gitignored.

---

## Building the bundle (optional)

`build.ps1` packs the validated conda env into an unzip-and-double-click bundle (bundled Python runtime + model weights + ffmpeg):

```powershell
pwsh -File build.ps1
```
It produces `dist/EasyVoice-vX.Y/` and a same-named `.zip`. Note the bundle is several GB — above GitHub's 2 GB per-release-asset limit — so split it into volumes or host it externally.

---

## Credits & License

- This project's own code is licensed under the **MIT License** (see [LICENSE](LICENSE)).
- Built on **[Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)** (model weights under Apache License 2.0).
- Licenses and sources of third-party components bundled in the all-in-one package (Qwen3-TTS model / FFmpeg / etc.) are documented in [THIRD-PARTY-NOTICES](assets/packaging/THIRD-PARTY-NOTICES.txt).

---

## Resources

- Qwen3-TTS: https://github.com/QwenLM/Qwen3-TTS
- ModelScope: https://modelscope.cn
- Gradio: https://www.gradio.app

# EasyVoice (易声)

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE) [![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/) [![Release](https://img.shields.io/github/v/release/rockbenben/easyvoice)](https://github.com/rockbenben/easyvoice/releases/latest) [![Powered by Qwen3-TTS](https://img.shields.io/badge/Powered%20by-Qwen3--TTS-orange.svg)](https://github.com/QwenLM/Qwen3-TTS)

[简体中文](README.md) | **English**

> 365 Open Source Plan #018 · a local, multilingual, dead-simple dubbing / voice-cloning tool built on Qwen3-TTS

## Overview

**EasyVoice** is a local, **multilingual**, dead-simple dubbing / voice-cloning tool built on [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) (Chinese-first UI, works out of the box):

- **3-second voice cloning** — upload or record ~3 seconds of reference audio to clone a voice for any text / subtitle dubbing.
- **Multilingual** — 10 languages: Chinese, English, Japanese, Korean, German, French, Russian, Portuguese, Spanish, Italian. Auto-detect by default, or pick manually.
- **Remembers your settings** — language / voice / style / speed etc. are saved and restored on next launch.
- **Subtitle dubbing (multi-speaker)** — upload subtitles (SRT / VTT / LRC); voices are auto-assigned per speaker from leading `Name:` prefixes, each line can be previewed / edited / re-rolled, generated timeline-aligned, and muxed straight into your video (dubbed video + aligned subtitles exported). Plain subtitles without prefixes work too (single voice); turn off the *Subtitles have speaker prefixes* toggle when the text contains colons to avoid mis-splitting.
- **Runs locally** — fully local inference, nothing uploaded to the cloud.
- **GPU-adaptive** — uses CUDA automatically when a GPU is present, falls back to CPU otherwise.
- **Quality switch (with an NVIDIA GPU)** — manually pick between **Fast 0.6B** and **High 1.7B** models (1.7B auto-downloads on first use); locked to 0.6B without a GPU.
- **Zero-setup** — end users unzip the all-in-one bundle and double-click to launch; developers can run from source.

---

## Download

Grab a bundle from **[Releases](../../releases/latest)** — two options:

| Bundle | Size | Best for | Model |
|---|---|---|---|
| **Full bundle** (GPU/CPU auto) | ~4.6 GB (3 volumes) | NVIDIA GPU / max speed | bundled |
| **CPU lite bundle** | **~0.5 GB (single file)** | no GPU / small download | downloaded in-app on first launch (~1.8 GB) |

- **Full bundle:** download `EasyVoice-v1.1.0.zip.01/.02/.03` + `merge-and-extract.bat` into one folder, double-click the bat to merge & extract.
- **CPU lite bundle:** download the single `EasyVoice-v1.1.0-cpu.zip` and unzip. ⚠️ **CPU generation is slow**: ~20–40 s per sentence (machine-dependent), minutes for long paragraphs — best for short clips/preview. For GPU speed, use the full bundle.

---

## For end users (3 steps)

### 1. Download & unzip
Pick a bundle from [Download](#download) above and unzip it locally.

### 2. Double-click to launch
Run `Start EasyVoice.bat` in the folder. The first launch takes ~30s (model loading).

> **Note:** Double-click launch requires the bundle (which ships its own `runtime/` and model). You can build the bundle yourself with `build.ps1`; a prebuilt bundle, if provided, is on [Releases](../../releases). To run from source, see **For developers** below.

### 3. Use it in the browser
A browser opens automatically at `http://127.0.0.1:7860`, with four tabs:

- **Dubbing** — type text, pick a language (Auto by default) and reference voice, click generate
- **Subtitle dubbing** — upload subtitles → assign a voice per speaker → fix lines (preview / edit / re-roll) → assemble & export (optionally muxed into your video)
- **My Voices** — upload or record reference voices and manage them (add / delete / rename / reorder / preview)
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
│   ├── tts_engine.py     # TTS engine (load, synthesize, chunking, subtitle align, speed, model select)
│   ├── dubbing_project.py# Subtitle-dubbing project state (speaker detect / per-cue gen·reroll / assemble)
│   ├── video_mux.py      # Mux dubbed audio into video (ffmpeg)
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

`build.ps1` packs the validated conda env into an unzip-and-double-click bundle:

```powershell
pwsh -File build.ps1                 # Full bundle: GPU/CPU auto, model bundled (~4.6 GB)
pwsh -File build.ps1 -Variant cpu    # CPU lite: no CUDA, no model (~0.5 GB; model downloaded in-app on first launch)
```
It produces `dist/EasyVoice-vX.Y[-cpu]/` and a same-named `.zip`. The full bundle exceeds GitHub's 2 GB per-asset limit — split it into volumes (with `merge-and-extract.bat`) or host externally; the CPU lite bundle is a single file.

---

## Changelog

The following fixes are in the source and will ship with the next bundle build (download bundles are still v1.1.0):

- **Dubbing · preset & style sync** — applying a preset now updates the style chip to match the preset's temperature (no longer diverging from the sliders), and that style is persisted, so the preset's temperature / top_p are reproduced after a reload.
- **Subtitle dubbing · speaker detection** — tightened the leading `Name:` prefix rule so multi-word phrases and pure-digit times (e.g. `12:30`) are no longer mistaken for a speaker and dropped from the dub; added a *Subtitles have speaker prefixes* toggle to disable splitting entirely for plain subtitles that contain colons.
- **Subtitle dubbing · replace-audio export** — the exported video now keeps its full length through the end. Previously, when the dub was shorter than the video (the last subtitle ends before the outro), trailing footage was silently truncated; it is now padded to the full video length.
- **Subtitle dubbing · concurrency** — operations on the same subtitle project (parse / edit / re-roll / generate-all / export) now run serially, preventing project-state corruption and broken exports from concurrent clicks.
- **Stability · GPU serialization** — generation across the Dubbing and Subtitle-dubbing tabs now runs serially, avoiding VRAM OOM or corrupted audio from simultaneous generation.
- **Dubbing · deleted voice** — a friendly message is shown when the selected voice is deleted mid-generation, instead of a raw error.

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

---

## About the 365 Open Source Plan

This is project #18 of the [365 Open Source Plan](https://github.com/rockbenben/365opensource).

One person + AI, 300+ open-source projects in a year. [Submit your idea →](https://my.feishu.cn/share/base/form/shrcnI6y7rrmlSjbzkYXh6sjmzb)

# Developer notes · EasyVoice

**English** · [简体中文](DEVELOPMENT.md)

End users do not need this page — download a bundle and double-click, see the [README](README.en.md). For architecture and module design, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

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

A browser opens at `http://127.0.0.1:7860`. If 7860 is taken or falls inside a Windows reserved port range, the app falls back to an alternate port (7861 / 8600 / 9000 / 5000) — trust the address printed in the console.

### Tests

```bash
python -m pytest -q
```

The full regression suite should pass.

---

## Project layout

```text
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
├── assets/               # Brand images (brand/) and packaging notices (packaging/)
├── docs/                 # Architecture & design docs (ARCHITECTURE.md, SPIKE-qwen-tts.md)
└── tests/                # Automated tests
```

> `models/`, `voices/`, `presets/`, `outputs/`, `runtime/`, `ffmpeg/`, `dist/` are runtime / build artifacts and are gitignored.

---

## Building the bundle (optional)

`build.ps1` packs the validated conda env into an unzip-and-double-click bundle:

```powershell
pwsh -File build.ps1 -Version v1.2.0                  # Full bundle: GPU/CPU auto, model bundled (~4.6 GB)
pwsh -File build.ps1 -Version v1.2.0 -Variant cpu     # CPU lite: no CUDA, no model (~0.5 GB; model downloaded in-app on first launch)
```

> ⚠️ **Always pass `-Version` when cutting a release.** The default is hardcoded in the `param` block of `build.ps1` and does not track the release. Omitting it produces a directory and zip named after whatever that default happens to be, overwriting an existing build in `dist/` and shipping mislabeled assets.
>
> The remaining parameters (`-EnvName` / `-CondaRoot` / `-ModelId`) are documented in the header comment of `build.ps1` and rarely need changing.

It produces `dist/EasyVoice-<Version>[-cpu]/` and a same-named `.zip`. The full bundle exceeds GitHub's 2 GB per-asset limit — split it into volumes (with `merge-and-extract.bat`) or host externally; the CPU lite bundle is a single file.

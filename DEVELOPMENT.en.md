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

3. **(Optional) FFmpeg for speed control & video muxing** — put `ffmpeg.exe` (and `ffprobe.exe`) on PATH or in the project `ffmpeg/` folder. If missing, speed ≠ 1.0 and video muxing gracefully degrade (falling back to 1.0x speed or exporting audio+subtitles only).

4. **Model** — downloaded automatically from ModelScope into `models/` on first run (`MODELSCOPE_CACHE` defaults to that folder; the SDK cache lands in a `models/` subdirectory under it, i.e. `models/models/` by default). Set `MODELSCOPE_CACHE` to change the cache root.

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
│   ├── dubbing_project.py# Subtitle-dubbing project state (speaker detect / per-cue gen·reroll·cancel / assemble)
│   ├── video_mux.py      # Mux dubbed audio into video (ffmpeg)
│   └── ui.py             # Gradio UI (four tabs)
├── AGENTS.md             # Working conventions — read before touching code
├── app_main.py           # Entry point
├── build.ps1             # Bundle builder (conda-pack runtime + model + FFmpeg tools)
├── Start EasyVoice.bat   # Windows launcher
├── requirements.txt      # Python dependencies
├── pyproject.toml        # pytest config
├── assets/               # Brand images (brand/) and packaging notices (packaging/)
├── docs/                 # Architecture & design docs (ARCHITECTURE.md, SPIKE-qwen-tts.md)
└── tests/                # Automated tests
```

> `models/`, `voices/`, `presets/`, `outputs/`, `ffmpeg/`, `dist/` are runtime / build artifacts and are gitignored.

---

## Building the bundle (optional)

`build.ps1` packs the validated conda env into an unzip-and-double-click bundle:

Before packing, run `python -s -m pip install --no-user -r requirements.txt` in the selected environment. The build checks imports in the source and the extracted runtime with `-E -s` (external Python environment variables and the user site are ignored).

```powershell
pwsh -File build.ps1 -Version v1.1.2                  # Full bundle: GPU/CPU auto, model bundled (~5 GiB)
pwsh -File build.ps1 -Version v1.1.2 -Variant cpu     # CPU lite: no CUDA, no model (~0.5 GB; model downloaded in-app on first launch)
```

> ⚠️ **Always pass `-Version` when cutting a release.** The default is hardcoded in the `param` block of `build.ps1` and does not track the release. Omitting it produces a directory and zip named after whatever that default happens to be, overwriting an existing build in `dist/` and shipping mislabeled assets.
>
> The remaining parameters (`-EnvName` / `-CondaRoot` / `-ModelId` / `-Variant`) are documented in the header comment of `build.ps1` and rarely need changing.

The local build produces `dist/EasyVoice-<Version>[-cpu]/` and a same-named `.zip`.

## Publishing with GitHub Actions

Move the release notes under the same `## vX.Y.Z` heading in both changelogs, then push the matching tag for that commit. **Package Windows** builds the CPU lite and CUDA full bundles and publishes a GitHub Release using both changelog sections as release notes. CI uses the built-in `GITHUB_TOKEN`.

CI uses Python 3.12 and the matching CPU or CUDA 12.8 PyTorch wheels on Windows. It extracts each ZIP to a fresh directory, relocates the runtime, and generates and decodes a WAV. The CPU bundle verifies the first-run 0.6B model download and cache reuse in a fresh process. The full bundle exercises the bundled model and CPU fallback on a runner without a GPU. If the full ZIP exceeds the asset size limit, CI produces `.zip.01`, `.zip.02`, and further volumes as needed, with `merge-and-extract.bat`. CI publishes the draft only after it verifies all uploaded assets and SHA-256 digests.

In Actions → **Package Windows** → **Run workflow**, leave `release_tag` blank to build `cpu`, `gpu`, or `both` as test artifacts retained for seven days. To retry publishing an existing tag, set `release_tag` and choose `both`. If only the release job failed, rerun the failed job in the original run to reuse the verified artifacts.

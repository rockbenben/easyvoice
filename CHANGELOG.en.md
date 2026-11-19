# Changelog

**English** · [简体中文](CHANGELOG.md)

Full notes for each release are on [Releases](../../releases).

## Unreleased

## v1.2.0

This update is for anyone who dubs text, edits subtitles one line at a time, or works offline. Download instructions for both Windows bundles are below.

### Changed

- Text dubbing puts the text box, Generate button, and preview on the left, with settings on the right. The columns stack in narrow windows. EasyVoice restores your last language, voice, style, speed, model, and manually adjusted sampling settings after a restart.
- The CPU lite bundle downloads the 0.6B model on first launch. The full bundle includes the model and supports NVIDIA acceleration with CPU fallback. To unpack the full bundle, put every volume next to the merge script and run it. Both bundles include SHA-256 checksum files.

### Fixed

- Subtitle import handles UTF-16, UTF-8 with a BOM, and LRC with multiple or millisecond timestamps. Select a row before editing. Reimporting clears previews and exports from the previous project, and saving an untouched line avoids regenerating it. If a re-recording fails, EasyVoice shows the reason and clears the stale audio preview.
- The interface loads offline with version checks and telemetry disabled. After a restart, EasyVoice uses the local ModelScope model cache. Source installs select interface dependencies compatible with Qwen3-TTS.
- With a fixed seed, splitting long text and running other jobs no longer disturb the result. Keeping the original audio uses the first track and preserves the full picture if that track ends early. Videos with no original track export with the dub alone.

[See Windows download and startup instructions](https://github.com/rockbenben/easyvoice/blob/v1.2.0/README.en.md#quick-start)

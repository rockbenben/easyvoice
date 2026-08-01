# Changelog

**English** · [简体中文](CHANGELOG.md)

Full notes for each release are on [Releases](../../releases).

## Unreleased

Nothing yet. Changes that are in the source but not yet in a bundle build get listed here — [run from source](DEVELOPMENT.en.md) to get them early.

## v1.2.0 · 2026-08-01

- **UI · Quit button** — a new "⏻ Quit" button (bottom-right) cleanly stops the server; the console window and the [README](README.en.md) also make clear that ⚠️ closing the browser alone won't quit (the server keeps running, holding memory and the port).
- **Launch · port fallback** — if 7860 is taken or falls inside a Windows reserved port range, the app no longer crashes on start; it automatically tries alternate ports (7861 / 8600 / 9000 / 5000) and the browser opens the actual one.
- **Dubbing · preset & style sync** — applying a preset now updates the style chip to match the preset's temperature (no longer diverging from the sliders), and that style is persisted, so the preset's temperature / top_p are reproduced after a reload.
- **Subtitle dubbing · speaker detection** — tightened the leading `Name:` prefix rule so multi-word phrases and pure-digit times (e.g. `12:30`) are no longer mistaken for a speaker and dropped from the dub; added a _Subtitles have speaker prefixes_ toggle to disable splitting entirely for plain subtitles that contain colons.
- **Subtitle dubbing · replace-audio export** — the exported video now keeps its full length through the end. Previously, when the dub was shorter than the video (the last subtitle ends before the outro), trailing footage was silently truncated; it is now padded to the full video length.
- **Subtitle dubbing · concurrency** — operations on the same subtitle project (parse / edit / re-roll / generate-all / export) now run serially, preventing project-state corruption and broken exports from concurrent clicks.
- **Stability · GPU serialization** — generation across the Dubbing and Subtitle-dubbing tabs now runs serially, avoiding VRAM OOM or corrupted audio from simultaneous generation.
- **Dubbing · deleted voice** — a friendly message is shown when the selected voice is deleted mid-generation, instead of a raw error.

# Changelog

**English** · [简体中文](CHANGELOG.md)

Full notes for each release are on [Releases](../../releases).

## Unreleased

### Improvements

- Redesigned interface: the Dub tab is now "Text dubbing", and the tab order is Text dubbing → Subtitle Dub → My Voices → Presets; the big banner and three-step strip are replaced by a single header line, text input, Generate and the result sit in the left column with settings on the right, and the two columns stack on narrow windows; hint copy throughout is shorter and plainer.
- More truly offline: the interface no longer loads fonts from Google Fonts, and Gradio's telemetry and online version check are switched off — the page works as usual without internet and no longer sends usage data out.
- Friendlier subtitle import: UTF-16 and UTF-8-with-BOM subtitle files now parse directly; when the encoding cannot be read, you are told to re-save the file as UTF-8 (or BOM-prefixed UTF-16) instead of only seeing "no subtitles parsed"; LRC lines with several timestamps or millisecond-precision times now line up correctly.
- Easier Subtitle Dub page: character voices get their own "Character voices" section, and the table hints that you should select a row to edit; until a row is selected the editor fields stay grey and inactive, so you cannot edit the wrong line; parsing a new subtitle file clears the previous preview audio, exported subtitles and dubbed video so old results cannot be mistaken for new ones.
- Settings are remembered better: after the service restarts, your language, voice, style, speed, model, and any hand-adjusted temperature/top_p are restored instead of being reset.

### Fixes

- Saving and re-recording in Subtitle Dub is more reliable: saving without actually changing the text or character no longer marks the line as pending (no wasted regeneration), and a failed single re-record shows a clear out-of-memory or generation error and no longer shows the previous clip as the new one.
- Fixed random seeds are now reliable: with a positive seed, the same text and settings produce the same audio, even across automatic long-text splitting or while other generation jobs are running.
- Exporting with "Keep original (ducked)" is more robust: videos without an audio track automatically fall back to dub-only, multi-track videos use the first track, and a short original track no longer truncates the final video.

Changes that are in the source but not yet in a bundle build get listed here — [run from source](DEVELOPMENT.en.md) to get them early.

# Changelog

**English** · [简体中文](CHANGELOG.md)

Full notes for each release are on [Releases](../../releases).

## Unreleased

- UI polish (batch1): the subtitle status table no longer shows raw internal values or a garbled header; the subtitle tab now reveals steps progressively (editing appears after parsing, export after generation); the voice library uses compact rows with ▶ to expand preview; "Save as preset" moved into a collapsible section; Quit joined the footer; "Max length" became time-based tiers; several hints reworded plainer.
- UI polish (batch2): the subtitle steps are numbered ①②③ and no empty shell bars remain before parsing; the read-only table no longer looks editable (green ring, handles and toolbar icons gone); preset summaries in English use half-width punctuation; typing shows a live character count and estimated duration (long text is now described as auto-split instead of falsely warning about the current tier); inline voice preview is more compact; footer and Quit are aligned on one rule.
- Stoppable subtitle batch: a Stop button appears while generating — the line in flight finishes, then the batch halts between lines; completed lines are kept and the rest can be generated later. The status table refreshes line by line instead of staying on "pending" for the whole batch, and partial failures now report how many lines failed and what to do next.
- Unsaved line edits are no longer silently ignored: if the text box holds edits you haven't saved, Generate all and Re-roll both ask you to save first (those buttons sit within one click of Save, and the cost of a mis-click was audio of the old line).
- Interface usability fixes: the per-speaker voice dropdowns in the subtitle tab and the inline rename box in the voice library were literally unclickable (Gradio 6 doesn't enable components created by gr.render on their own); narrow screens no longer squeeze the whole page or wrap voice names one character per line.
- Generation errors no longer show a raw traceback: out-of-memory gets an actionable hint (shorten the text, or pick Fast 0.6B under Quality), everything else a plain failure message, with the detail kept in the launcher console.
- The preset dropdown no longer lies about state: nothing is preselected (blank honestly means "current parameters don't come from a preset"), touching any parameter the preset owns clears the choice, and saving a preset confirms it and selects it.
- Copy now matches the actual flow: after uploading you're told to click Parse, and "parsed" only appears once it has happened; the subtitle editing state lives in the page only (a refresh loses it).
- Changes that are in the source but not yet in a bundle build get listed here — [run from source](DEVELOPMENT.en.md) to get them early.

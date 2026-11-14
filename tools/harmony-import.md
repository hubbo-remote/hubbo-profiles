# Importing the Harmony archive

[← Maintainer notes](README.md)

**Imported from the Harmony archive at spec version 1**, on 2026-11-13, by `tools/bin/import-harmony`
(`import_harmony.py`), from the public CC0 archive of Harmony IR codes
(`logitech-harmony-ir-archive`, generated 2026-09-02, archive schema version 2). 276,236 archive
devices in, 256,845 profiles out, every one valid at version 1.

The Harmony catalogue was imported into this repository once. The archive is read in place and never copied. After the import the
committed files are the source of truth: a fix is an edit to a file, and a change to the spec is a
migration (`migrations/`). This page records the rules the import followed, so the data can be
understood and, if ever needed, re-derived (`tools/bin/import-harmony --replace` refuses to run over
existing data without that flag, because it would lose every edit since).

Every imported profile passed the validator (joined) at import time. The run report is
`build/import-report.json`.

The output is in storage form (profiles/README.md): `profiles/harmony/<nnn>/<globalDeviceId>.json`
and `codesets/<xx>/<id>.json`.

**Identity.** `id` is `harmony:<globalDeviceId>`, Logitech's permanent id. Every imported profile
starts at `revision` 1.

**Dropped devices** (counted in the report): test manufacturers (Z-Harmony Test, Harmony Pro,
Harmony Beta, LogitechHarmony) and test device types (0, 49, 57, 60, 66); empty catalogue entries;
devices with no IR commands (radio, HID or IP only); placeholders (only the Saitek placeholder
code, or 3+ commands that all share one code: SHIELD, Fire TV sticks, Chromecast with Google TV and
the like use a generic Bluetooth profile instead); no model name. **Duplicates**: same manufacturer
and the same model ignoring case, spaces and punctuation; the one with the most commands (then the
lowest id) is kept. Regional variants and manufacturer spellings stay separate.

**Commands**

- Kept: `pronto`. Dropped: `keycode`, `protocol`, `prontoRepeat`, commands without Pronto, and the
  Saitek placeholder code.
- `pronto_toggle`: for toggle-bit protocols, the converter renders the code from Logitech's
  protocol definition (`tools/harmony_render.py`). It's written only when the bit-0 render is
  byte-identical to the archive's Pronto (true for all but one code).
- Names: whitespace collapsed; `-` `.` `+` `*` `#` → `Dash` `Dot` `Plus` `Star` `Hash`; spelling
  synonyms (`Up`/`ArrowUp`/`CursorUp` → `DirectionUp`, `Play/Pause` → `PlayPause`, `MuteToggle` →
  `Mute`, `SkipBackward` → `SkipBack`); then the archive's most common spelling of the same letters
  and digits (`Ok` → `OK`, `Epg` → `EPG`); otherwise punctuation is removed and the parts joined
  (`In-Start` → `InStart`). A name already in canonical form wins its name. Clashes get a number.
  The original goes in `label` when it had punctuation or was numbered.

**Steps**: strings → `{command}`, `durationMs` → `hold_ms`, `delayMs` → `delay_ms`; `{set, to}`
state records are skipped (they aren't transmissions). A list naming a missing command, holding
with no duration or over 16 steps is dropped whole.

**Power**: `discrete` and `toggle` as they are; `powerOnDelay` → `on_delay_ms`; `unknown`/`none`
have no power. Discrete with identical on and off steps becomes `toggle` (no automatic step).
`onReset` isn't carried.

**Inputs**: each entry with commands, with the device's `inputs.start`/`finish` added around its
steps. Inputs reached only by cycling (`next`/`previous`) aren't carried. **Channels**:
`fixedDigits` → `digits`, single-command `start`/`finish`; dropped without `0`-`9`; the `-/--`
prefix keys (`greaterTen`, `greaterHundred`) aren't carried. **Timing**: `interKeyDelay`,
`inputDelay`, `pressMinRepeats` (spec, Timing), clamped to range. **Kind** from `kinds.json`.
Not carried: `interDeviceDelay`, `connectedAppPowerOnDelay`, `minRepeats`, states, input ports.

**Hand-written replacements.** A profile in `profiles/hubbo/` whose `meta.harmony.global_device_id`
is N replaced `harmony:N` at import time (none did). After the import, replacing a device is an edit: delete
its Harmony file and add the hand-written one; the validator rejects two profiles that claim the
same Harmony device.

**Edits after the import**

- `harmony:274100` (Apple TV 4K over IR), revision 2: power `none`. The archive's on and off were
  both Home; Apple TV wakes on any key and sleeps on its own timer, as in the Bluetooth profile.

# Hubbo device profile spec (draft v0, schema_version 1)

A profile is a device: "Apple TV", "LG OLED55C1PUB". It says what the device is, which platform
drives it, its commands, power steps and timing. Adding a device to the hub is close to copying a
profile and adding a few local fields: the hub's own `id`, a `name` ("Family Room TV") and, for
Bluetooth, its pairing.

Profiles come from two places. The Bluetooth ones are hand-written in this repo. At scale, the rest
are converted from the Harmony archive. Either way the format is the same, and it's the only one
the hub accepts.

The schema is `schema/profile.schema.json`. `bin/validate` checks a file against it plus the rules
below. This is a draft: until the hub ships schema_version 1, it can change without a version bump.

## 1. Example

```json
{
  "schema_version": 1,
  "id": "hubbo:fire-tv",
  "revision": 1,
  "source": "hubbo",
  "manufacturer": "Amazon",
  "model": "Fire TV",
  "kind": "streamer",
  "platform": "ble_hid",
  "commands": {
    "Home": { "page": "consumer", "usage": "0x0223" },
    "QuickSettings": { "page": "consumer", "usage": "0x0223", "hold_ms": 1000 },
    "Sleep": { "page": "consumer", "usage": "0x0034" }
  },
  "buttons": { "menu": "Home" },
  "power": {
    "type": "discrete",
    "on": [{ "command": "Home" }],
    "off": [{ "command": "Home" }, { "delay_ms": 500 }, { "command": "Sleep" }],
    "on_delay_ms": 1500
  },
  "timing": { "key_delay_ms": 100 },
  "meta": { "confidence": "medium", "sources": ["..."] }
}
```

Field names are snake_case, like the hub's API. Durations are whole milliseconds ending in `_ms`.
There are no floats. Unknown fields are errors.

## 2. Identity

| Field | Required | Meaning |
|---|---|---|
| `schema_version` | yes | The format version, `1`. The hub rejects versions it doesn't know. |
| `id` | yes | Stable profile id, `<source>:<slug>`; the slug is 1-48 of `a-z 0-9 . -`. Examples: `hubbo:apple-tv`, `harmony:498661` (Harmony's `globalDeviceId`). Never changes once published. On the hub it's `profile.id`, not the device's own `id`. |
| `revision` | yes | Integer from 1, bumped whenever the profile changes. |
| `source` | yes | `hubbo` (written in this repo), `harmony` (converted) or `user` (made on a hub, later). Must match the `id` prefix. |
| `manufacturer`, `model` | yes | Display names, 1-64 characters. Search matches these two and nothing else. |
| `kind` | yes | An `id` from `kinds.json`: one kind per Harmony device type (`tv`, `streamer`, `receiver`, `projector`...), each with a display label, plus a few for Home Assistant devices with no Harmony type (`speaker`, `fan`, `cover`, `scene`, `script`). `switch` is a home-control switch; `hdmi_switch` is the AV one. A label, icon and browse category, never behaviour. |
| `platform` | yes | How the hub drives it, using the hub's platform names: `ble_hid` (Bluetooth keyboard), `ir`. `network` is reserved. |

One profile has one platform. An Apple TV over Bluetooth and over IR are two profiles, because the
commands, power steps and timing all differ.

**Generic profiles.** The four Bluetooth profiles describe a platform, not one product: "Apple TV",
"Android TV / Google TV" (SHIELD, Chromecast with Google TV, onn., Sony and TCL TVs...), "Fire TV",
and "Other" / "Bluetooth keyboard". They're generic on purpose. Someone who can't find their exact
device browses and picks one of these. A product with its own keys or power steps gets its own
complete profile (section 11); there's no inheritance and no aliases.

**Hash.** A profile's hash is the SHA-256 of its canonical form: the whole document, keys sorted at
every level, no whitespace, UTF-8, strings escaped only as JSON requires (RFC 8785 for our
integer-only subset; in Python, `json.dumps(doc, sort_keys=True, separators=(",", ":"),
ensure_ascii=False)`). The hash isn't stored in the document. The catalog lists `id`, `revision`
and `sha256` per profile; the hub records them for each device it adds, so it can show "update
available".

## 3. Commands

`commands` maps a name to how the command is sent, 1-512 per profile.

Names are 1-32 ASCII letters and digits (`DirectionUp`, `InputHdmi1`, `0`), unique ignoring case.
Use the vocabulary in section 8 where a name fits. A command may carry a `label` (1-32
characters) when the original name had punctuation, such as `SAP/*` → `SAP`.

A remote button passes straight through: its press is the key's press and its release is the
key's release (Bluetooth holds the key down; IR keeps sending the repeat-section). What a hold does
is up to the device. `hold_ms` on a command (1-10,000) makes it a long press of that length on its
own, as with Apple TV's Control Center (Home held 1 s); it's for steps and for binding the long
press to a button as a single command.

### `ble_hid`

```json
"Back":   { "page": "consumer", "usage": "0x0224" },
"Select": { "page": "keyboard", "usage": "0x58" }
```

- `page`: `keyboard` (HID page 0x07) or `consumer` (0x0C).
- `usage`: uppercase hex, two digits for keyboard, four for consumer. The ranges match Hubbo's HID
  descriptor: keyboard `0x04`-`0x65`, consumer `0x0001`-`0x03FF`. Anything else would need a new
  descriptor, which means re-pairing every host.
- Two commands may share a usage (Apple TV `Home` and `ControlCenter`).
- No modifiers (Ctrl, Shift) in this version, and no repeats: `timing.ir_repeats` is invalid here.
- The hub sends the page and usage from the profile; it doesn't need them in its own key table.

### `ir`

```json
"VolumeUp": { "pronto": "0000 006D 0024 0002 0156 00AB ... 0016 0E46" }
```

- `pronto`: raw Pronto hex (format `0000`), uppercase, single spaces. The validator checks the word
  count against the header. The carrier is in the header.
- A tap sends the once-section, then the repeat-section `timing.ir_repeats` times. Holding (or
  `hold_ms`) keeps sending the repeat-section. An empty once-section means the repeat-section is the
  whole frame.
- **Toggle bits.** About 14% of Harmony codes (RC5, RC6, MCE...) need a bit that flips on each new
  press, or the device ignores a repeated key. The archive stores them with the bit at 0. The
  converter renders a second copy with the bit at 1 as `pronto_toggle`. The hub keeps one toggle
  state per device, flips it on each new press and sends the matching copy. No IR protocol engine
  in firmware. (The sample converter doesn't render it yet.)

### `network`

Reserved for later (Roku, Sonos). Not defined; rejected in schema_version 1.

## 4. Steps

Power and inputs are lists of 1-16 steps:

| Step | Meaning |
|---|---|
| `{ "command": "Home" }` | Press the command, with its own `hold_ms` if it has one. |
| `{ "command": "Home", "hold_ms": 2000 }` | Hold for 2 s, then release. |
| `{ "delay_ms": 200 }` | Wait (1-60,000). |

The hub also waits `timing.key_delay_ms` between command steps. Every command named must exist.

## 5. Power

| Field | Meaning |
|---|---|
| `type` | `discrete` (needs `on` and `off`), `toggle` (needs `toggle`, no `on`/`off`) or `none`. Leaving out `power` means `none`. |
| `on`, `off`, `toggle` | Steps. |
| `on_delay_ms` | How long the device needs after power on before it takes commands (0-60,000). |

Power steps are offered, not imposed: the new-activity wizard adds them to the startup (on steps,
then a wait of `on_delay_ms`) and the shutdown (off steps), and the user keeps or changes them.

- Switching activities runs only the new activity's startup, so on steps must be **safe to repeat**
  on a device that's already on. Use `discrete` with a real on (`PowerOn`, or a wake key) whenever
  the device has one. A `toggle`-only device gets no automatic power step.
- **Bluetooth hosts:** `on` is the wake key (Home on Fire TV and Android TV). The hub first waits
  for the host to connect; that wait isn't a step. `off` is a sleep key (Sleep, 0x34).
- Don't write power steps that navigate a menu (open a menu, move to Sleep, select it): they break
  when the menu changes. A device without a direct sleep key gets `type: none`. Apple TV is one: it
  wakes on any key and sleeps on its own timer.

## 6. Timing

All optional.

| Field | Meaning | Harmony |
|---|---|---|
| `key_delay_ms` | Minimum gap between two commands to this device (0-5,000). | `interKeyDelay` |
| `input_delay_ms` | Wait after an input switch (0-60,000). | `inputDelay` |
| `ir_repeats` | IR only: repeat-sections per tap (0-20, default 1). | `pressMinRepeats` |

## 7. Inputs and channels

```json
"inputs": [{ "name": "HDMI 1", "steps": [{ "command": "InputHdmi1" }] }],
"channels": { "digits": 3, "finish": "OK" }
```

- `inputs`: up to 64, each a unique name (1-32 characters) and the steps that select it. Direct
  selection only; Harmony's cycling inputs (with state tracking) aren't supported.
- `channels`: how to dial a number. The digits are the commands `0`-`9`, which must all exist.
  `digits` pads with leading zeros (1-4; leave it out to send as typed). `start` and `finish` are
  commands sent before and after. A sub-channel dash uses the `Dash` command.

## 8. Command names and remote buttons

### Vocabulary

Names follow Logitech's Harmony vocabulary, since the archive uses it (its top 100 names cover 77%
of all commands). Harmony's spelling is consistent; the ambiguity is in meaning (Exit, Back and
Return are three keys on many remotes). So different meanings stay different names, and the
fallbacks below resolve them.

| Group | Names |
|---|---|
| Navigation | `DirectionUp` `DirectionDown` `DirectionLeft` `DirectionRight` `Select` `OK` `Enter` `Back` `Exit` `Return` `Home` `Menu` `Setup` `Settings` `Options` `Info` `Display` `Guide` `PageUp` `PageDown` `Search` |
| Playback | `Play` `Pause` `PlayPause` `Stop` `Record` `FastForward` `Rewind` `SkipForward` `SkipBack` `NextTrack` `PreviousTrack` `ChapterNext` `ChapterPrev` `Eject` |
| Volume | `VolumeUp` `VolumeDown` `Mute` |
| Channels | `ChannelUp` `ChannelDown` `ChannelPrev` `0`-`9` `Dash` `Dot` `NumberEnter` |
| Colours | `Red` `Green` `Yellow` `Blue` |
| Power | `PowerOn` `PowerOff` `PowerToggle` `Sleep` |
| Inputs | `Input` `InputNext` `InputPrevious` `InputHdmi1`… `InputTv` `InputAv` |
| Picture, sound | `Subtitle` `ClosedCaption` `Audio` `Aspect` `PictureMode` `SoundMode` |
| Keyboard | `KeyA`-`KeyZ` `F1`-`F12` `Escape` `Tab` `Space` `Backspace` `Delete` `Insert` `KeyHome` `KeyEnd` |

- `Back` goes back one screen, `Exit` leaves the menu or app, `Return` is many TVs' word for Back.
- `Home` is the home screen; `Menu` is the device's own menu.
- `PlayPause` is one key for both. Devices with separate keys keep `Play` and `Pause`.
- Keyboard letters are `KeyA`-`KeyZ` because `A`-`D` are function buttons on many remotes.
- Other names (`ControlCenter`, `Netflix`) are fine; they just don't pre-fill anything.

### Remote buttons

`buttons.json` (schema `schema/buttons.schema.json`) is the table the wizard uses to fill the
remote. One row per remote button that can be filled:

```json
{ "button": "back", "role": "watch", "candidates": ["Back", "Exit", "Return"] }
```

- `button`: the hub's button name (`core/src/remote/button.cpp`).
- `role`: `watch` (navigation, playback, colours, number pad, channels: the "what are you watching
  on?" device) or `volume` (volume up/down and mute).
- `candidates`: the device gets the first one its profile has, ignoring case; none means the button
  stays empty.

Every filled button passes through to the device (section 3), so a held d-pad repeats and a held
Menu (Home on streamers) opens Apple TV's Control Center or the Fire TV and Android TV quick menus,
unless a Long press is bound on that button.

Notes: the hub's skip buttons send HID Fast Forward and Rewind, so they try those first. Buttons not
in the table (`off`, `music`, `tv`, `movie`, `light_1`, `light_2`, `plus`, `minus`, `switch_1`,
`switch_2`) are never filled.

A profile's `buttons` overrides the table: `{ "menu": "Home", "info": null }`. A name means "use
this command", `null` means "leave it empty", and every key must be a button in `buttons.json`. The
streamer profiles set `"menu": "Home"`, because the Harmony Companion remote has no Home button.

## 9. `meta`

Notes for people; the hub may drop it. `confidence` (`high`: shipped profile or tested on hardware;
`medium`: test profile or a reliable mapping; `low`: a guess), `sources`, `notes`, `verify` (still
to test on hardware), and `harmony` (`global_device_id`, `device_type`, `codeset`) for converted
profiles.

## 10. On the hub

- **A device is an added profile.** The hub keeps the profile's fields at the top level of the
  device, except `id`, `revision`, `schema_version`, `platform` and `meta`:
  - the identity goes in `profile: {id, revision, sha256}`;
  - `platform` isn't stored, because it's always the device's provider type;
  - `schema_version` and `meta` are dropped.

  Plus the device's local fields: its own `id`, `name`, integration and, for Bluetooth, its
  pairing. Every command is kept, so any can be bound later without fetching the profile again.
- **Commands:** the hub caps a device at 128 commands (the format allows 512). Every Bluetooth
  profile has at most 75; IR may revisit the cap. The validator warns above 128.
- **Built-in profiles.** The hub keeps byte-for-byte copies of `profiles/*.json`, `kinds.json` and
  `buttons.json`, so the add flow and the wizard work offline. The sync writes an index of each
  profile's `id`, `revision` and `sha256` from `bin/validate --hashes`. The sha256 is over the
  canonical form (section 2), not the file's bytes.
- **Size** (stored: minified, without `meta`):

| Profile | Commands | Stored | Gzip |
|---|---|---|---|
| Apple TV | 17 | 1.1 KB | 0.4 KB |
| Android TV / Google TV | 35 | 1.9 KB | 0.5 KB |
| Fire TV | 17 | 1.2 KB | 0.4 KB |
| Bluetooth keyboard | 75 | 3.4 KB | 0.7 KB |
| Apple TV 4K (IR, converted) | 19 | 9.6 KB | 0.6 KB |
| LG OLED55C1PUB (IR, converted) | 68 | 29.7 KB | 1.3 KB |

Bluetooth profiles fit the few-KB budget. IR profiles are 10-40 KB as text (each Pronto string is
about 400 characters); the IR phase decides how the hub stores them. The validator warns above
32 KB and fails above 128 KB.

## 11. Specific devices and contributions

A product that differs from its generic profile (an extra key, different power steps) gets its own
profile: copy the generic one, change `id`, `manufacturer`, `model` and what differs, and note the
sources. Every profile is complete and stands alone. See `CONTRIBUTING.md`.

## 12. Converting from Harmony

The full converter comes later. The sample (`tools/harmony_sample.py`, run by
`bin/convert-sample`) follows these rules:

- **Names:** trim and collapse whitespace. Fold spelling-only synonyms when the canonical name isn't
  already there (`Up`/`ArrowUp`/`CursorUp` → `DirectionUp`, `Ok` → `OK`, `Play/Pause` →
  `PlayPause`, `MuteToggle` → `Mute`). `-` → `Dash`, `.` → `Dot`. Other punctuation is removed and
  the parts joined (`In-Start` → `InStart`), keeping the original as `label`. Clashes get a number.
- **Commands:** keep `pronto`; drop `keycode`, `protocol` and `prontoRepeat`. Commands without
  Pronto (Bluetooth, IP, RF) are dropped.
- **Steps:** strings → `{command}`, `durationMs` → `hold_ms`, `delayMs` → `delay_ms`. A list with a
  missing command or a state step (`{set, to}`) is dropped whole, with a note.
- **Power, timing, channels:** as in sections 5-7; `powerOnDelay` → `power.on_delay_ms`. Channels
  are dropped when the codeset has no digits.
- **Kind:** from the `harmony` codes in `kinds.json`; unlisted types are `other`.
- **Not carried:** `interDeviceDelay`, `connectedAppPowerOnDelay`, `minRepeats`, states,
  `power.onReset`.
- **Placeholders:** codesets that are all the Saitek placeholder are skipped; those devices use a
  generic Bluetooth profile.

## 13. Validation

`bin/validate [files or dirs]` (Docker; defaults to `profiles/` and `samples/`) first checks
`kinds.json` and `buttons.json` against their schemas (no duplicates; each Harmony type maps to one
kind; `other` exists). Then each profile: the schema; the `kind` and `buttons` keys exist in those
files; every named command exists; no names differ only in case; the `id` prefix matches `source`;
channels have `0`-`9`; Pronto lengths match their headers; size. It prints each profile's command
count, sizes and SHA-256.
`bin/validate --hashes [paths]` prints only `id<TAB>revision<TAB>sha256<TAB>path` per profile
(failures go to stderr and still fail the run), for the hub's sync script.

[← Docs](README.md) · Next: [Changelog](changelog.md) →

# Hubbo Device Profile Specification

| | |
|---|---|
| **Version** | 1, 2026-11-13 ([changelog](changelog.md)) |
| **Schema** | [`schema/v1/`](schema/README.md) |
| **License** | CC0 1.0 |

A **profile** is a JSON document describing one device on one platform: what it is, how to send
each command, how to power it, its timing, inputs and channel entry.

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
  "meta": { "confidence": "medium" }
}
```

## Conventions

JSON (RFC 8259), UTF-8, snake_case names. Durations are integer milliseconds ending in `_ms`; there
are no floats. Unknown fields are errors. A *consumer* is a program that uses profiles.

## Versioning

`schema_version` is the version a profile conforms to; each version is defined by
`schema/v<N>/`, which never changes. Consumers must reject unknown versions. See the
[changelog](changelog.md).

## Fields

| Key | Type | Required |
|---|---|---|
| [`schema_version`](#schema_version) | integer | yes |
| [`id`](#id) | string | yes |
| [`revision`](#revision) | integer | yes |
| [`source`](#source) | string | yes |
| [`manufacturer`](#manufacturer) | string | yes |
| [`model`](#model) | string | yes |
| [`kind`](#kind) | string | yes |
| [`platform`](#platform) | string | yes |
| [`commands`](#commands) | object | yes |
| [`buttons`](#buttons) | object | no |
| [`power`](#power) | object | no |
| [`timing`](#timing) | object | no |
| [`inputs`](#inputs) | array | no |
| [`channels`](#channels) | object | no |
| [`meta`](#meta) | object | no |

A profile has one platform and is complete on its own; there's no inheritance. Minified without
`meta`, a profile is at most 256 KB.

## `schema_version`

Integer, required. The spec version the profile conforms to: `1`.

## `id`

String, required. `<source>:<slug>`. The slug is 1-48 of `a-z 0-9 . -` and starts with a letter or
digit; for `harmony` it's digits only. An id never changes.

## `revision`

Integer, required, from 1. Raised on every change to the profile.

## `source`

String, required: `hubbo` (hand-written), `harmony` (from the Harmony catalog) or `user`. Matches
the `id` prefix.

## `manufacturer`

String, required, 1-64 characters. The display name of the maker.

## `model`

String, required, 1-64 characters. The display name of the model.

## `kind`

String, required. An `id` in the version's `kinds.json`.

## `platform`

String, required. How the device is controlled:

| Value | Meaning |
|---|---|
| `ble_hid` | Bluetooth HID: the device is a host for a Bluetooth keyboard. |
| `ir` | Infrared, as Pronto codes. |
| `network` | Reserved; invalid in version 1. |

The platform sets the shape of every command (see [`commands`](#commands)). `timing.ir_repeats`
applies only to `ir`.

## `commands`

Object, required: 1-512 names, each mapped to a command. Names are 1-32 ASCII letters and digits,
unique ignoring case, from the [vocabulary](#command-names) where one fits. Every command may have:

| Field | Type | Value |
|---|---|---|
| `label` | string | 1-32 characters: the original name, when it had punctuation. |
| `hold_ms` | integer | 1-10,000: the command is a long press of this length. |

A button press presses the key, and its release releases it.

### Bluetooth HID commands (`platform: ble_hid`)

```json
"Back": { "page": "consumer", "usage": "0x0224" }
```

| Field | Type | Value |
|---|---|---|
| `page` | string, required | `keyboard` (HID page 0x07) or `consumer` (0x0C). |
| `usage` | string, required | Uppercase hex: keyboard `0x04`-`0x65` (two digits), consumer `0x0001`-`0x03FF` (four digits). |

The key is held down from press to release. Usages may repeat. There are no modifiers.

### IR commands (`platform: ir`)

```json
"VolumeUp": { "pronto": "0000 006D 0024 0002 0156 00AB ... 0016 0E46" }
```

| Field | Type | Value |
|---|---|---|
| `pronto` | string, required | Raw Pronto (`0000`), uppercase hex, single spaces; length matches the header; no zero durations. |
| `pronto_toggle` | string | The same code with its toggle bit at 1. |

A Pronto code is hex words: `0000`, the frequency word F, the number of on/off pairs in the once
section, the number in the repeat section, then the pairs, once section first. The carrier is
1,000,000 / (F × 0.241246) Hz, and each duration counts carrier periods (F × 0.241246 µs). A
section's last off duration is the gap after it; frames are sent back to back.

The *repeat frame* is the repeat section, or the once section if that's empty. A tap sends the
once section, then repeat frames up to `timing.ir_repeats` frames in all (0 and 1 send the once
section alone). A hold sends what a tap sends, then repeat frames until release; with `hold_ms`,
until that time has passed. A frame in flight always finishes. With `pronto_toggle`, a consumer
keeps one toggle state per device, flips it on each new press of a command that has one (not per
frame) and sends the matching code.

## `buttons`

Object, optional. Overrides which command fills a remote button: `{ "menu": "Home", "info": null }`.
A command name fills the button with that command; `null` leaves it empty. Every key must be a
button in `buttons.json`, and every command named must exist.

Buttons not overridden get their default from `buttons.json`: the first of the button's
[candidates](#buttonsjson) that the profile has, ignoring case, or nothing.

## `power`

Object, optional; absent means `none`.

| Field | Type | Value |
|---|---|---|
| `type` | string, required | `discrete` (with `on` and `off`), `toggle` (with only `toggle`) or `none`. |
| `on`, `off`, `toggle` | [steps](#step) | The steps for each. |
| `on_delay_ms` | integer | 0-60,000: time after power on before the device takes commands. |

`on` should be safe to repeat, so prefer `discrete` with a real on or wake key. Power steps should
not navigate menus; a device with no direct sleep is `none`. For a Bluetooth host, `on` is a wake key
and `off` a sleep key.

## `timing`

Object, optional; every field is optional.

| Field | Type | Value |
|---|---|---|
| `key_delay_ms` | integer | 0-5,000: minimum gap from the end of one command to the next. |
| `input_delay_ms` | integer | 0-60,000: wait after an input switch. |
| `ir_repeats` | integer | 0-20, default 1: frames per tap ([IR commands](#ir-commands-platform-ir)). `ir` only. |

## `inputs`

Array, optional, up to 64. Each input selects one source directly:

```json
"inputs": [{ "name": "HDMI 1", "steps": [{ "command": "InputHdmi1" }] }]
```

| Field | Type | Value |
|---|---|---|
| `name` | string, required | 1-64 characters, unique ignoring case. |
| `steps` | [steps](#step), required | What selects it. |

## `channels`

Object, optional. How to dial a channel number; requires the commands `0`-`9`.

```json
"channels": { "digits": 3, "finish": "OK" }
```

| Field | Type | Value |
|---|---|---|
| `digits` | integer | 1-4: zero-pad to this many digits; absent sends the number as typed. |
| `start`, `finish` | string | Commands sent before and after the digits; they must exist. |

A sub-channel dash is the `Dash` command.

## `meta`

Object, optional. Notes for people; consumers may ignore them.

| Field | Type | Value |
|---|---|---|
| `confidence` | string | `high` (tested), `medium` (a reliable mapping) or `low` (a guess). |
| `sources` | array of strings | Where the information came from (each up to 300 characters). |
| `notes` | array of strings | Anything else (each up to 500). |
| `verify` | array of strings | What is still to be tested (each up to 300). |
| `harmony` | object | For Harmony profiles: `global_device_id`, `device_type` (integers), `codeset` (string). |

## Types

### Step

`power` and `inputs` use lists of 1-16 steps. Each step is one of:

| Step | Meaning |
|---|---|
| `{ "command": "Home" }` | Press the command (with its own `hold_ms`). |
| `{ "command": "Home", "hold_ms": 2000 }` | Hold it 1-10,000 ms. |
| `{ "delay_ms": 200 }` | Wait 1-60,000 ms. |

Named commands must exist. Consumers wait `timing.key_delay_ms` between commands.

## Appendix

### Command names

Use these names for these keys; other names are allowed.

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

`Back` is one screen back, `Exit` leaves the menu or app, `Return` is a TV's Back key. `Home` is
the home screen, `Menu` the device's menu. `PlayPause` is one key for both.

### `buttons.json`

The version's `buttons.json` lists the remote buttons, one row each:

```json
{ "button": "back", "role": "watch", "candidates": ["Back", "Exit", "Return"] }
```

| Field | Value |
|---|---|
| `button` | The remote button's name. |
| `role` | `watch` (the device you watch) or `volume`. |
| `candidates` | Command names to try, in order. |

## Profile hash

SHA-256 of the canonical form: keys sorted, no whitespace (RFC 8785 for this integer-only subset;
Python: `json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`). It isn't
stored in the profile.

## Validation

A profile conforms if it passes its version's `profile.schema.json` and every rule above; "should"
is advice.

---

[← Docs](README.md) · Next: [Changelog](changelog.md) →

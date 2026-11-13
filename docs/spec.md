[← Docs](README.md) · Previous: [Using the profiles](using.md) · Next: [Changelog](changelog.md) →

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

## Profile

| Field | Required | Value |
|---|---|---|
| `schema_version` | yes | `1` |
| `id` | yes | `<source>:<slug>`, slug 1-48 of `a-z 0-9 . -`, first a letter or digit; digits only for `harmony`. Never changes. |
| `revision` | yes | Integer from 1, raised on every change. |
| `source` | yes | `hubbo`, `harmony` or `user`; matches the `id` prefix. |
| `manufacturer`, `model` | yes | 1-64 characters. |
| `kind` | yes | An `id` in `kinds.json`. |
| `platform` | yes | `ble_hid` or `ir` (`network` is reserved). |
| `commands` | yes | [Commands](#commands) |
| `buttons` | no | [Remote buttons](#remote-buttons) |
| `power` | no | [Power](#power); absent means `none`. |
| `timing` | no | [Timing](#timing) |
| `inputs`, `channels` | no | [Inputs and channels](#inputs-and-channels) |
| `meta` | no | [`meta`](#meta) |

One profile, one platform. Profiles are complete; there's no inheritance. Minified without `meta`,
a profile is at most 256 KB.

**Hash:** SHA-256 of the canonical form (keys sorted, no whitespace; RFC 8785 for this integer-only subset; Python:
`json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`). It isn't stored.

## Commands

`commands` maps 1-512 names to commands. Names are 1-32 ASCII letters and digits, unique ignoring
case, from the [vocabulary](#command-names) where one fits. Every command may have:

| Field | Value |
|---|---|
| `label` | 1-32 characters: the original name, when it had punctuation. |
| `hold_ms` | 1-10,000: the command is a long press of this length. |

A button press presses the key, and its release releases it.

### `ble_hid`

```json
"Back": { "page": "consumer", "usage": "0x0224" }
```

| Field | Value |
|---|---|
| `page` | `keyboard` (HID page 0x07) or `consumer` (0x0C). |
| `usage` | Uppercase hex: keyboard `0x04`-`0x65` (two digits), consumer `0x0001`-`0x03FF` (four digits). |

Usages may repeat. No modifiers.

### `ir`

```json
"VolumeUp": { "pronto": "0000 006D 0024 0002 0156 00AB ... 0016 0E46" }
```

| Field | Value |
|---|---|
| `pronto` | Raw Pronto (`0000`), uppercase hex, single spaces; length matches the header; no zero durations. |
| `pronto_toggle` | Optional: the same code with its toggle bit at 1. |

The *repeat frame* is the repeat section, or the once section if that's empty. A tap sends
`timing.ir_repeats` frames (at least one): the once section, then repeat frames. A hold sends
repeat frames until release. With `pronto_toggle`, a consumer keeps one toggle state per device,
flips it on each new press (not per frame) and sends the matching code.

## Steps

Power and inputs are lists of 1-16 steps.

| Step | Meaning |
|---|---|
| `{ "command": "Home" }` | Press it (with its own `hold_ms`). |
| `{ "command": "Home", "hold_ms": 2000 }` | Hold 1-10,000 ms. |
| `{ "delay_ms": 200 }` | Wait 1-60,000 ms. |

Named commands must exist. Consumers wait `timing.key_delay_ms` between commands.

## Power

| Field | Value |
|---|---|
| `type` | `discrete` (with `on`, `off`), `toggle` (with only `toggle`) or `none`. |
| `on`, `off`, `toggle` | Steps. |
| `on_delay_ms` | 0-60,000: time after power on before the device takes commands. |

`on` should be safe to repeat, so prefer `discrete` with a real on or wake key. Power steps should
not navigate menus; a device with no direct sleep is `none`. For a Bluetooth host, `on` is a wake key
and `off` a sleep key.

## Timing

All optional.

| Field | Value |
|---|---|
| `key_delay_ms` | 0-5,000: minimum gap between commands. |
| `input_delay_ms` | 0-60,000: wait after an input switch. |
| `ir_repeats` | 0-20, default 1: frames per tap. IR only. |

## Inputs and channels

```json
"inputs": [{ "name": "HDMI 1", "steps": [{ "command": "InputHdmi1" }] }],
"channels": { "digits": 3, "finish": "OK" }
```

- `inputs`: up to 64, each a unique `name` (1-64 characters) and `steps` that select it.
- `channels`: requires commands `0`-`9`. `digits` (1-4) zero-pads; absent sends as typed.
  `start` and `finish` are commands sent before and after. A dash is `Dash`.

## Command names

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

## Remote buttons

`buttons.json` maps remote buttons to commands:

```json
{ "button": "back", "role": "watch", "candidates": ["Back", "Exit", "Return"] }
```

`role` is `watch` (the device you watch) or `volume`. The button gets the first candidate the
profile has, ignoring case, or stays empty. A profile's `buttons` overrides this:
`{ "menu": "Home", "info": null }` (`null` leaves it empty). Keys must be in `buttons.json`.

## `meta`

Notes for people; consumers may ignore them. `confidence` is `high` (tested), `medium` (a
reliable mapping) or `low` (a guess). Also `sources`, `notes`, `verify` (still to test) and, for
Harmony profiles, `harmony` (`global_device_id`, `device_type`, `codeset`).

## Validation

A profile conforms if it passes its version's `profile.schema.json` and every rule above; "should" is advice.

---

[← Docs](README.md) · Previous: [Using the profiles](using.md) · Next: [Changelog](changelog.md) →

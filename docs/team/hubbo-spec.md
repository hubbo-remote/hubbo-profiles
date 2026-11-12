# hubbo-spec: working notes

## State (2026-11-10, device profiles phase)

Spec draft v0 (schema_version 1). In the device profiles phase (brief:
`~/src/hubbo/docs/design/device-profiles.md`); hubbo-devices commits with the rest of the phase.
Nothing is committed; the repo has no remote. Everything validates.

- `docs/spec.md`; schemas in `schema/` (profile, kinds, buttons; draft 2020-12).
- `kinds.json`: 39 kinds, each `{id, label, harmony: [deviceType...]}`. The hub validates
  `device.kind` against it and serves it.
- `buttons.json`: 38 fillable remote buttons, each `{button, role: watch|volume, hold, candidates}`.
  The web admin's wizard reads it.
- `tools/validate.py` + `tools/Dockerfile` (python:3.12-slim, jsonschema 4.23.0), run by
  `bin/validate`. It checks both tables first, then profiles against them. `--hashes` prints
  `id revision sha256 path` per profile for the lead's sync script (index.json).
- `profiles/`: apple-tv (high), android-tv (medium), fire-tv (medium), generic-keyboard (high,
  "Other" / "Bluetooth keyboard"). All revision 1. The hub keeps byte-for-byte copies, plus
  kinds.json and buttons.json.
- `samples/harmony/`: Apple TV 4K/4th and LG OLED55C1PUB over IR (`bin/convert-sample`, throwaway;
  reads kinds.json for the kind mapping).
- `CONTRIBUTING.md`, `.github/ISSUE_TEMPLATE/key-doesnt-work.md`. No CI config (no remote).

## Decisions

- **A profile is a device.** On the hub, the profile's fields sit at the device's top level, except:
  identity in `profile: {id, revision, sha256}`; `platform` not stored (it's the provider type);
  `schema_version` and `meta` dropped (core, 2026-11-10). Hub cap: 128 commands per device.
- **snake_case fields, `platform`** (`ble_hid`, `ir`; `network` reserved and rejected).
- **Kinds: one per Harmony deviceType**, with merges only where two codes are the same thing:
  tv 1+13; streamer 35+51+52+63; console 9+23 (samples of both are mainstream consoles); computer
  8+10 (desktop vs laptop). `speaker` has no Harmony code (it's for HA speakers). 59 (Nest) →
  climate; 999 (Z-Wave switches and locks) → switch; test codes 0, 49, 57, 60, 66 → other.
- **Button holds:** d-pad, skip FF/Rew, channel up/down, volume up/down, and menu (user's board
  test, 2026-11-11: holding Menu = Home must reach the Apple TV to open Control Center and sleep
  it; same for the Fire TV/Android TV quick menus). Everything else taps
  (Select stays a tap: a held Select would trigger tvOS long-press menus and clash with hold
  triggers).
- **Generic platform profiles, no inheritance, no aliases, no pairing field** (user). Search uses
  manufacturer and model only. A specific device is a complete copy.
- **One platform per profile.** **Commands:** name → encoding (ble_hid `{page, usage}`, ir
  `{pronto, pronto_toggle?}`), optional `hold_ms`, `label`.
- **Power for the wizard:** on steps must be safe to repeat (switching runs only B's startup).
  Fire TV and Android TV: on = Home (wake), the hub waits for the connection first (not a step);
  off = Sleep 0x34. Apple TV: none. No menu-navigating power steps. Toggle-only: no automatic step.
- **Hash:** SHA-256 over canonical JSON of the whole document, not the file bytes.

## Gotchas

- Harmony HID keycodes put the page in the high word as `0C00`/`0700`.
- Logitech's BT Apple TV 5 has Menu = 0x223 = Back; left out so remote menu → Home.
- Archive Apple TV 4K (IR) has power on = off = `Home`; the converter notes it.
- `channelTuning` can exist without digit commands; the converter drops it.
- Core's skip buttons send HID FF/Rewind, so their fallbacks start with FastForward/Rewind.
- `switch` is home control; Harmony AV switches (30) are `hdmi_switch`.
- Harmony's deviceType buckets are noisy (VCRs in 2 and 25, PCs in 8 with a K400 keyboard); the
  labels name the main thing in each.
- `bin/validate` mounts the repo read-only; the converter needs `bin/convert-sample` (read-write).

## Settled by the user (2026-11-10)

- snake_case fields; the profile identity on the hub; one platform per profile; remote Menu → Home
  on streamers; skip buttons try FastForward/Rewind first; the hub waits for a Bluetooth host to
  reconnect after the wake key; IR storage form waits for the IR phase.

## Open items

- Pressing Home as the streamers' power-on also sends an already-on streamer to its home screen
  when switching between two activities that use it. Raised with the lead.
- Apple TV has no power control (user, 2026-11-11, revision 3): the only Bluetooth sleep path is
  Control Center's menu, which breaks with tvOS changes. It wakes on any key and sleeps on its own
  timer. Rule: no power steps that navigate a menu.
- Core/API spec questions arrive through the lead during the phase; fix the spec and profiles then.
- Board checks: each profile's `meta.verify`.
- Full converter: `pronto_toggle`, placeholder filtering, search index. Not started.

# Using the profiles

[← Docs](README.md) · Next: [The specification](spec.md) →

## Find a device

A profile's id gives its file:

| Id | File |
|---|---|
| `hubbo:apple-tv` | `profiles/hubbo/apple-tv.json` |
| `harmony:498661` | `profiles/harmony/498/498661.json` |
| `harmony:636` | `profiles/harmony/000/636.json` |

- `<source>:<slug>` is `profiles/<source>/<slug>.json`, except Harmony profiles, which sit in
  folders of 1,000: the folder is the number without its last three digits, zero-padded to three.
- **`hubbo:`** profiles are hand-written: generic Bluetooth profiles for Apple TV, Android TV /
  Google TV, Fire TV and any Bluetooth keyboard, plus devices people add.
- **`harmony:`** profiles come from the Harmony catalog: about 257,000 infrared devices, numbered
  by their Harmony id.

To look a device up by name, search the catalog site, or the index in each release
(`index/manufacturers.json`, then `index/m/<manufacturer>.json`, which lists each model with its
id).

## Read a profile

```json
{
  "schema_version": 1,
  "id": "harmony:498661",
  "revision": 1,
  "source": "harmony",
  "manufacturer": "LG",
  "model": "OLED55C1PUB",
  "kind": "tv",
  "platform": "ir",
  "codeset": "ef535cd331c00cb0",
  "power": { "type": "discrete", "on": [{ "command": "PowerOn" }], "off": [{ "command": "PowerOff" }] },
  "inputs": [{ "name": "HDMI 1", "steps": [{ "command": "InputHdmi1" }] }]
}
```

Many devices share the same commands, so this repository stores each set once, in `codesets/`. A
file with `"codeset": "<id>"` in place of `commands` uses `codesets/<first two characters>/<id>.json`.
**Join them** to get the profile the [specification](spec.md) describes: put that file's
`commands` where `codeset` was. Hand-written profiles already hold their `commands`.

```python
import json
device = json.load(open("profiles/harmony/498/498661.json"))
cs = device["codeset"]
commands = json.load(open(f"codesets/{cs[:2]}/{cs}.json"))["commands"]
profile = {("commands" if k == "codeset" else k): (commands if k == "codeset" else v)
           for k, v in device.items()}
```

- A codeset file is `{"commands": {...}}`. Its id is the first 16 hex digits of the SHA-256 of
  the commands' canonical form, so a codeset never changes in place. Every codeset is used.
- A profile's `revision` and hash are those of the joined profile.
- Every profile here is at the current spec version and sits where its id says. Ids are unique,
  and no two profiles claim the same Harmony device.
- Files are UTF-8 JSON, indented by 2 spaces, with a trailing newline.

## Download everything

- **Clone the repository:** `git clone https://github.com/maddox/hubbo-profiles`
- **Or download a release** from the
  [releases page](https://github.com/maddox/hubbo-profiles/releases): every profile, every
  codeset, the docs and a search index, in one archive.

Everything is public domain ([CC0 1.0](../LICENSE)).

## In Hubbo

[Hubbo](README.md#what-uses-these-profiles) is one consumer:

- It ships with the four generic Bluetooth profiles and the button and kind tables built in.
- Adding a device copies the whole joined profile and remembers its id, revision and hash, which is
  how it spots an update.
- A new activity starts with the device's power steps (the on steps, then `on_delay_ms`), and you
  can change them. For a Bluetooth host, it waits for the host to connect before the on steps.
- It keeps up to 128 commands per device.

---

[← Docs](README.md) · Next: [The specification](spec.md) →

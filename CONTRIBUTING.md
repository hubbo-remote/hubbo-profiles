# Contributing

Thank you for helping. Every fix makes a device work for everyone who owns one, long after the
remote that came with it is gone. You don't need to be a programmer: a clear report helps too.

- [Report a problem (no code needed)](#report-a-problem-no-code-needed)
- [Fix a profile](#fix-a-profile)
- [Add a device](#add-a-device)
- [Check your change](#check-your-change)
- [What makes a good profile](#what-makes-a-good-profile)
- [Propose a change to the spec](#propose-a-change-to-the-spec)

## Report a problem (no code needed)

[Open an issue](https://github.com/maddox/hubbo-profiles/issues/new/choose) and pick a template:
a button doesn't work, a device is missing, or something else is wrong. Give the manufacturer and
model (usually on a sticker on the back), the profile you used and what happened.

## Fix a profile

1. **Find the file.** The id gives the path: `hubbo:apple-tv` is `profiles/hubbo/apple-tv.json`,
   and `harmony:498661` is `profiles/harmony/498/498661.json`. No id? Search this repository for
   the model.
2. **Edit it**, on GitHub with the pencil button or in a clone.
3. **Raise its `revision` by one.**
4. **Say where the fix came from** in `meta.sources`, such as `"Tested on an LG OLED55C1, 2026-11"`.
5. **Open a pull request.**

Many Harmony devices share a codeset (`"codeset": "<id>"`, stored in
`codesets/<first two characters>/<id>.json`):

- to fix a code for **every device that shares it**, edit the codeset file and say so in the pull
  request; a maintainer renames it and updates its devices;
- to fix it for **one device**, replace `"codeset": "<id>"` in that device's file with
  `"commands": { ... }` copied from the codeset, and edit there.

**Files** are UTF-8 JSON with 2-space indentation and a trailing newline;
[`tools/bin/format`](tools/README.md) fixes one that isn't. A codeset's name is the hash of its
commands, so it never changes in place. Ids are unique, every codeset is used by some device, and
all data is at the current spec version.

## Add a device

1. **Copy the closest profile:** a generic one from `profiles/hubbo/` for a Bluetooth streamer, or
   a device of the same kind and manufacturer for infrared.
2. **Save it as `profiles/hubbo/<manufacturer>-<model>.json`**, lowercase with dashes.
3. **Set** `id` (`hubbo:<manufacturer>-<model>`), `revision` 1, `source` `"hubbo"`,
   `manufacturer`, `model` and `kind`.
4. **Change what differs:** commands, power, timing, inputs.
5. **Fill in `meta`:** `confidence` (`high` if tested on the device), `sources`, and in `verify`
   anything not yet tested.
6. **If it replaces a Harmony device,** delete that file and set `meta.harmony.global_device_id`.

## Check your change

Every pull request is checked automatically:

- the profile matches the [specification](docs/spec.md) and its schema;
- every command a step, input, channel or button names exists;
- the file is where its id says, in the file format, and the id is unique;
- a changed profile has a higher `revision`.

A failed check says what to fix. To run the checks yourself, see the
[maintainer notes](tools/README.md#validate) (they need only Docker).

## What makes a good profile

- **Standard command names** from the [vocabulary](docs/spec.md#command-names) (`DirectionUp`,
  `Select`, `Back`, `VolumeUp`, `InputHdmi1`), so remote buttons fill themselves. Different keys
  keep different names: `Back`, `Exit` and `Return` are three keys.
- **Other names** are fine for other keys: letters and digits, up to 32. Put the remote's own
  spelling in `label` if it has punctuation.
- **The kind** from [`kinds.json`](docs/schema/v1/kinds.json): the main thing the device is.
- **Power on that's safe to repeat:** a real on command or wake key if there is one; `toggle` if
  there's only a toggle; never steps that move through a menu.
- **Direct inputs** (`InputHdmi1`), not cycling.
- **Only what you know works,** with `confidence` and `sources` that say how you know.

## Propose a change to the spec

1. **Open an issue** with the "Spec change" template: the problem, a real device that needs it,
   and the change.
2. **Once agreed, one pull request carries it:**
   - the [specification](docs/spec.md) text, with the version raised by one;
   - a new `docs/schema/v<N+1>/` (earlier folders never change);
   - a [changelog](docs/changelog.md) entry: what changed, in a line or two;
   - the migration that moves every profile to the new version, and the migrated profiles.

Any change to what a valid profile is counts, however small. A rewording that keeps the meaning
doesn't, and needs no version or changelog entry.

## License

Contributions are released under [CC0 1.0](LICENSE), like our own work here (see the
[README](README.md#license)).

---

[← Docs](docs/README.md) · Previous: [Changelog](docs/changelog.md)

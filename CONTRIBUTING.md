# Contributing

Fixes and new device profiles are welcome. Profiles are released under CC0 (public domain), so by
sending one you agree to that.

## A key doesn't work

Open an issue with the "A key doesn't work" template: the device, the profile you picked, the key,
and what happened.

## Improve a profile

Edit the file in `profiles/`, bump its `revision`, and add where the fix came from to
`meta.sources` (for example "tested on a SHIELD TV Pro, 2026-11"). If you tested it on a device,
remove it from `meta.verify`.

## Add a device

The generic profiles (Apple TV, Android TV / Google TV, Fire TV, Bluetooth keyboard) cover most
devices. Add a device of its own only when it differs: an extra key, other power steps or timing.

1. Copy the closest generic profile to `profiles/<manufacturer>-<model>.json`.
2. Set `id` (`hubbo:<manufacturer>-<model>`, lowercase), `revision` 1, `manufacturer` and `model`.
3. Change what differs. Use command names from the vocabulary in `docs/spec.md` (section 8) where
   one fits.
4. Fill in `meta`: `confidence`, `sources`, and anything you couldn't test in `verify`.

Every profile is complete on its own; there's no inheritance.

## Check it

```sh
bin/validate                          # everything
bin/validate profiles/my-device.json  # one file
```

It runs in Docker, so nothing needs installing. CI will run the same check on every pull request.

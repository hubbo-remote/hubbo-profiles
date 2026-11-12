# hubbo-devices

Device profiles for Hubbo: the spec, the profiles and (later) the site that serves them.
Profiles are CC0.

- `docs/spec.md`: the profile format.
- `schema/profile.schema.json`: its JSON Schema.
- `profiles/`: the profiles. The generic Bluetooth ones (Apple TV, Android TV / Google TV, Fire TV,
  Bluetooth keyboard) are also bundled into the hub.
- `samples/harmony/`: sample conversions from the Harmony archive, to show the format holds IR.
- `bin/validate [paths]`: check profiles and the two tables (runs in Docker); `--hashes` lists each
  profile's id, revision and sha256.
- `kinds.json`, `buttons.json`: the device kinds and the remote button table (data, with schemas).
- `bin/convert-sample [devices/...json]`: the throwaway Harmony conversion (runs in Docker, reads
  the archive in place from `~/src/hubbo/logitech-harmony-ir-archive-main`).
- `CONTRIBUTING.md`: how to fix or add a profile.

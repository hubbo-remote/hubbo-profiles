# Schemas

[← Docs](../README.md)

Each spec version's files are in their own folder; [`v1/`](v1/) is the current one.

- [`profile.schema.json`](v1/profile.schema.json): the JSON Schema (2020-12) for a profile. The
  [specification](../spec.md#validation) adds the rules a schema can't express.
- [`kinds.json`](v1/kinds.json): the device kinds.
- [`buttons.json`](v1/buttons.json): the default command for each remote button.
- [`kinds.schema.json`](v1/kinds.schema.json): the shape of `kinds.json`.
- [`buttons.schema.json`](v1/buttons.schema.json): the shape of `buttons.json`.

`kinds.json` and `buttons.json` are data tables the spec refers to, not schemas; the
`*.schema.json` files describe their shape. In `kinds.json`, ids are unique, `other` exists, and
each Harmony device type maps to one kind. In `buttons.json`, buttons are unique, and no button
lists a candidate twice.

---

[← Docs](../README.md) · [The specification](../spec.md)

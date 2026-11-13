# Schemas

[← Docs](../README.md)

One folder per spec version. A folder never changes once its version is published.

| Version | Folder |
|---|---|
| 1 (current) | [`v1/`](v1/) |

- [`profile.schema.json`](v1/profile.schema.json): a profile's shape (JSON Schema 2020-12). The
  [specification](../spec.md#validation) lists the checks a schema can't express.
- [`kinds.json`](v1/kinds.json): the device kinds and their labels. Ids are unique, `other`
  exists, and each Harmony device type maps to one kind.
- [`buttons.json`](v1/buttons.json): the remote buttons and their candidate commands. Buttons are
  unique, and no button lists a candidate twice.
- `kinds.schema.json`, `buttons.schema.json`: the tables' shapes.

---

[← Docs](../README.md) · [The specification](../spec.md)

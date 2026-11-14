# Profiles

One file per device, at a path that follows from its id: `<source>:<slug>` is
`<source>/<slug>.json`, except Harmony devices, which sit in folders of 1,000 named by the number
without its last three digits.

- `hubbo:apple-tv` is [`hubbo/apple-tv.json`](hubbo/apple-tv.json). The hand-written profiles
  are all in [`hubbo/`](hubbo/).
- `harmony:498661` is [`harmony/498/498661.json`](harmony/498/498661.json), and `harmony:636`
  is `harmony/000/636.json`.

Most Harmony devices share their commands through [codesets](../codesets/README.md). The format
is the [specification](../docs/spec.md).

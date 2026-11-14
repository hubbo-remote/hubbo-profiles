# Codesets

Sets of commands shared by many devices, each stored once.

A device file with `"codeset": "<id>"` in place of `commands` uses the codeset at
`<first two characters of the id>/<id>.json`. Put that file's `commands` where the `codeset` key
was, and you have the profile the [specification](../docs/spec.md) describes.

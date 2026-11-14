# Maintainer notes

The tools that keep the library valid and build its downloads. Everything runs in Docker (the
image is `tools/Dockerfile`, tagged by its hash and built on first use), so nothing needs
installing. Run them from the repository root.

| Command | What it does |
|---|---|
| `tools/bin/validate` | Check everything: the tables, every profile (joined with its codeset), every codeset, the layout. |
| `tools/bin/validate <paths>` | Check those files or folders; a codeset brings in every profile that uses it. |
| `tools/bin/validate --since <ref>` | Check what changed since a git ref, plus the revision rule. CI runs this on pull requests. |
| `tools/bin/validate --hashes [paths]` | Print `id<TAB>revision<TAB>sha256<TAB>path` per profile (for a consumer's sync; Hubbo uses `--hashes profiles/hubbo`). |
| `tools/bin/format [paths]` | Rewrite codesets and split profiles in the file format (2-space indent, UTF-8, trailing newline); validate fails one that isn't. Hand-written profiles keep their layout. |
| `tools/bin/rehash` | After a codeset is edited by hand: move it to its new name, repoint the profiles that use it (raising their revisions), delete unused codesets. |
| `tools/bin/migrate tools/migrations/v<N>-to-v<N+1>.py` | Move every profile and codeset to a new spec version (see [migrations](migrations/README.md)). |
| `tools/bin/index [dir]` | Build the search index into `build/index/` (not committed). |
| `tools/bin/release [name]` | Build `build/release/<name>.tar.gz`: the committed tree plus a fresh index, for a GitHub release. |
| `tools/bin/import-harmony` | The one-time Harmony import ([notes](harmony-import.md)). Refuses to run over existing data. |

## Validate

`tools/bin/validate` is the reference validator (`validate.py`); the checks are listed in
[the spec](../docs/spec.md#validation), [the contributing guide](../CONTRIBUTING.md#fix-a-profile)
(the repository) and [the schemas page](../docs/schema/README.md) (the tables). It also warns,
without failing, above 32 KB and above the hub's 128 commands. A whole-tree run checks each codeset's commands once and
every profile against the spec version it claims. CI ([`.github/workflows/validate.yml`](../.github/workflows/validate.yml))
runs `--since` the base branch on every pull request, and the whole tree on pushes to main.
`--since` checks the changed profiles and codesets (and every profile using a changed codeset),
runs the whole-tree checks (unique ids and Harmony devices, codesets that exist and are used) over
a quick scan of every profile, and checks everything when `docs/schema/` or `tools/` changed.

## The search index

`tools/bin/index` writes:

| File | Contents |
|---|---|
| `manufacturers.json` | `[{n, s, c, k}]`: name, slug, device count, device counts by kind. |
| `m/<slug>.json` | One manufacturer's devices, `[{id, m, k, p, n}]`: id, model, kind, platform, command count. Sorted by model. The file path comes from the id ([profiles/README.md](../profiles/README.md)). |
| `catalog.json` | Counts and the build date. |

It's derived from the profiles, so it's built, never committed. The catalog site and each release
carry a copy.

## Releases

`tools/bin/release` on a clean, tagged commit makes one archive with the spec, schemas, changelog,
profiles (in storage form), codesets and the index. Attach it to the GitHub release for that tag.
GitHub allows release assets up to 2 GB; the archive is far smaller.

## Files

| Path | What |
|---|---|
| `tree.py` | The storage form: paths from ids, joining, content-addressed codesets, the file format. |
| `validate.py` | The validator. |
| `build_index.py`, `release.py` | The index and the release archive. |
| `migrate.py`, `migrations/` | Spec-version migrations and rehash. |
| `import_harmony.py`, `harmony_render.py` | The Harmony import, and its renderer for toggle-bit codes. |

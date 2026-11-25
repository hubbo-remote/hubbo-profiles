# hubbo-spec: working notes

## State (2026-11-13, two-repo phase)

`~/src/hubbo-profiles` (was hubbo-devices; origin github.com/maddox/hubbo-profiles, private,
nothing pushed): the open standard plus all profile data, CC0. Nothing committed this phase.
The site is `~/src/hubbo-site` (hubbo-site owns it).

**Layout**
- Root: README.md, LICENSE (CC0 legal code), CONTRIBUTING.md, profiles/, codesets/, docs/, tools/,
  .github/ (issue + PR templates, workflows/validate.yml for CI, unused until pushed).
- docs/: README.md (index), spec.md, changelog.md, schema/README.md,
  schema/v1/{profile,kinds,buttons}.schema.json + kinds.json + buttons.json. Pages have
  prev/next/docs nav. No tooling detail in docs/ or the README.
- profiles/hubbo/*.json (hand-written, whole); profiles/harmony/<nnn>/<n>.json (nnn = n // 1000,
  3 digits; 318 folders) with `codeset` in place of commands; codesets/<xx>/<id>.json
  (id = sha256(canonical commands)[:16]). Paths derive from ids (tree.profile_path).
  profiles/README.md and codesets/README.md explain the layout; tree.walk takes only *.json, and
  --since ignores non-JSON paths there.
- tools/: README.md (maintainer notes), notes/hubbo-spec.md (these notes; releases include only
  README, LICENSE, CONTRIBUTING, docs, profiles, codesets), bin/ (validate, rehash, migrate, index, release,
  import-harmony, format, tools-image; lib.sh shared), tree.py, validate.py, migrate.py, build_index.py, release.py,
  import_harmony.py, harmony_render.py, harmony-import.md, migrations/README.md, Dockerfile
  (python:3.12.8-slim-bookworm + git, jsonschema 4.23.0; image tagged by the Dockerfile's hash).

**Data**: imported once at spec v1 (256,845 Harmony profiles, 53,380 codesets) + 4 hand-written.
One edit since: harmony:274100 (Apple TV 4K IR) revision 2, power none. overrides/ is gone.
Full validate passes in about 2.5 min; `--since <ref>` checks changed files + revision rule.
Git: 310k files, pack 97 MB, status 0.2 s, local clone 13.5 s; an edit commit adds ~nothing.
Release archive (split form + index) 58 MB.

## Decisions

- **No reprocessing the catalog (user, 2026-11-13):** no full-tree validate, index rebuild,
  rehash or import unless the lead asks. Use targeted checks: `validate profiles/hubbo`,
  specific paths, `--since`, or a small throwaway repo. CI's push job also runs `--since` the
  push's `before` commit (the whole tree only for schema/tools changes or a first/force push).

- **Versioned spec** (user, 2026-11-13): every change bumps `schema_version`; each version's full
  definition lives in docs/schema/v<N>/ forever; data is always at the current version; a change
  ships as one PR/commit with text, schema folder, changelog, migration
  (tools/migrations/v<N>-to-v<N+1>.py) and migrated data. v1 = the state on 2026-11-13; earlier
  drafts are pre-history in git. The import is v1's starting data.
- **Committed data is the source of truth.** Fixes are edits (+ revision bump); the importer
  refuses to run over existing data without --replace.
- **Codesets are content-addressed and immutable**; editing one means `tools/bin/rehash`, or
  inlining `commands` into one device. The validator flags misnamed and orphan codesets.
- **Index is generated** (tools/bin/index → build/index/, rows {id,m,k,p,n}), never committed;
  releases and the site carry a copy.
- **Hub contract (lead, 2026-11-13):** `bin/hubbo profiles sync` runs `tools/bin/validate
  profiles/hubbo` and `--hashes profiles/hubbo`, and copies docs/schema/v1/{kinds,buttons}.json.
  Keep those paths and commands stable; tell the lead before any moves.
- **Publishing is settled** (user accepts the risk): transformed, never mirrored; no Logitech
  branding; a takedown contact. Rules: ~/src/hubbo/docs/design/catalog-site.md "Hosting and
  publishing".
- **Commit shape approved:** 1 the standard, 2 the Harmony import at v1, 3 the Apple TV 274100
  edit on its own. Waiting for the user's ask.
- Nothing removed (user): no age or kind trim. Age signal researched: globalDeviceId tracks entry
  date; obsolete kinds 25,913 devices.
- A profile is a device; one platform per profile; IR stays Pronto; sending rule = Harmony's
  pressMinRepeats; pronto_toggle rendered only when the bit-0 render matches the archive;
  hash = SHA-256 of canonical JSON. No aliases, no inheritance.

- **Docs style (user, 2026-11-13):** the README, the spec, the changelog and the folder READMEs
  are as short as they can be: no rationale, nothing that doesn't exist yet (no releases, index or
  site in public docs; tools/README may mention them). The spec is a per-key reference: Fields
  table, one section per top-level key in document order, Types (Step), Appendix (command names,
  buttons.json), Profile hash, Validation. Changelog entries are a line or two ("Initial
  version."). Process and the repository rules (file format, guarantees) live in CONTRIBUTING.

## Gotchas

- The archive renders durations against the Pronto period (word × 0.241246 µs).
- `{set, to}` steps are state records; skip them.
- Step names in the archive differ in case/punctuation from codeset names; resolve by key.
- `set()` inside a list comprehension over 310k files made validate quadratic once; watch for it.
- tools/bin scripts share tools/bin/lib.sh (`in_docker rw|ro|build`); keep the hub's entry points
  (`tools/bin/validate`) as thin wrappers.
- Revision rule reads old files through one `git cat-file --batch` (GitFiles); a migration PR
  touches every profile, so never one `git show` per file.
- build/catalog/ is a stale gitignored build from the old converter layout.

## Open items

- **IR phase (2026-11-24, hub design ~/src/hubbo/docs/design/ir.md):** spec's IR section now
  spells out Pronto parsing, tap/hold/hold_ms frames, 0 = 1 for ir_repeats, toggle flips only
  on commands with pronto_toggle, key_delay_ms measured end to start. `tools/bin/profile <id>`
  prints one joined profile (the site's Download is the same join). Test fixtures were made in
  the lead's scratchpad (NEC, RC5 toggle, SIRC x3), validated with check_doc.
  Open: hub plans a 15-500 kHz carrier check; 5 codesets (words 0131/019F/01CD, 9-13.6 kHz,
  164 codes) would be refused. ir_repeats 0 could become min 1 in a v2. Validator has no
  standalone mode for a file outside the tree (placement check fails); use check_doc.
  Also: input names up to 64; profiles up to 256 KB; 5,214 Harmony profiles exceed the hub's
  128-command cap.
- Streamers' Home-as-power-on sends an already-on streamer home on switches. Raised earlier.

# Migrations

Every change to the spec bumps its version, and moves the data with it. This folder keeps, forever,
how the data in this repository got from each version to the next, so anyone can follow a profile
through the history of the spec.

| File | What it is |
|---|---|
| [`../harmony-import.md`](../harmony-import.md) | Version 1's starting data: the Harmony catalog, imported at spec version 1. |
| `v<N>-to-v<N+1>.py` | The script that moved every profile and codeset from version N to N+1. |

## Writing one

A spec change lands as **one pull request (one commit on main)** holding all of it:

1. `docs/schema/v<N+1>/`: the new version's schemas and tables (copy `docs/schema/v<N>/`, then change it).
   `docs/schema/v<N>/` stays as it is, so documents that claim version N can still be checked.
2. `docs/spec.md`: the new text, with the version in its header.
3. `docs/changelog.md`: the version's entry: what changed, in a line or two.
4. `tools/migrations/v<N>-to-v<N+1>.py`, defining either or both of:
   - `migrate_profile(doc) -> doc`: every profile file as stored (a split device has `codeset` in
     place of `commands`);
   - `migrate_commands(commands, platform) -> commands`: every codeset, and the commands of whole
     profiles.

   Keep them pure. Its docstring says what it does, in a sentence or two.
5. The migrated data: `tools/bin/migrate tools/migrations/v<N>-to-v<N+1>.py`. It checks the data is at N, runs
   the script, sets `schema_version` to N+1 everywhere, bumps the revision of every profile that
   changed, and rehashes codesets.
6. `tools/bin/validate` passes on the whole tree.

Never edit a migration once it's merged.

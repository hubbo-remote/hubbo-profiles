"""Change the data tree: apply a migration, then rehash codesets.

Usage (inside the tools image; see tools/bin/migrate and tools/bin/rehash):
  migrate.py tools/migrations/v<N>-to-v<M>.py   move every profile and codeset from spec version N to M,
                                          then rehash. The data must be at N, and docs/schema/v<M>/
                                          must exist; every profile ends with schema_version M.
  migrate.py --rehash                     only rehash

A migration is a Python file with either or both of:
  migrate_profile(doc) -> doc            every profile file as stored (a split device has
                                         `codeset` in place of `commands`); return it changed or not
  migrate_commands(commands, platform) -> commands   every codeset's commands (and the inline
                                         commands of whole profiles)
The runner bumps `revision` on every profile whose joined content changed; a migration doesn't.

Rehash: a codeset file is named by the hash of its commands, so one edited by hand (or by a
migration) is in the wrong place. Rehash moves it to its new name, points every profile that used
it at the new one (bumping their revisions), and deletes codesets no profile uses.
"""

import importlib.util
import json
import os
import pathlib
import re
import sys
from multiprocessing import Pool

import tree

# Set before each pool forks, so workers inherit them.
MIGRATION = None
TARGET = None    # the version a migration moves the data to
PLATFORMS = {}   # codeset id -> platform of the first profile that uses it
MOVED = {}       # old codeset id -> new


def load_migration(path):
    spec = importlib.util.spec_from_file_location("migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rename_codeset(path):
    """(old id, new id) for one codeset file after migrating its commands; writes the new file.
    The old file is left for the orphan sweep."""
    commands = tree.load_codeset_file(path.stem)
    if MIGRATION and hasattr(MIGRATION, "migrate_commands"):
        commands = MIGRATION.migrate_commands(commands, PLATFORMS.get(path.stem))
    return path.stem, tree.write_codeset(commands)


def profile_ref(path):
    raw = json.loads(path.read_text())
    return str(path), raw.get("codeset"), raw.get("platform"), raw.get("schema_version")


def update_profile(path):
    """(changed, codeset id it ends with) for one profile file."""
    path = pathlib.Path(path)
    raw = json.loads(path.read_text())
    before = digest(raw)
    if MIGRATION and hasattr(MIGRATION, "migrate_profile"):
        raw = MIGRATION.migrate_profile(raw)
    if MIGRATION and hasattr(MIGRATION, "migrate_commands") and "commands" in raw:
        raw["commands"] = MIGRATION.migrate_commands(raw["commands"], raw.get("platform"))
    if TARGET is not None:
        raw["schema_version"] = TARGET
    if "codeset" in raw:
        raw["codeset"] = MOVED.get(raw["codeset"], raw["codeset"])
    if digest(raw) == before:
        return 0, raw.get("codeset")
    raw["revision"] = raw["revision"] + 1
    tree.write(path, raw)
    return 1, raw.get("codeset")


def digest(raw):
    """The joined content, as far as a change to it goes: the stored doc plus its codeset's id."""
    return tree.digest({k: v for k, v in raw.items() if k != "revision"})


def main(argv):
    global MIGRATION, TARGET
    if argv and argv[0] != "--rehash":
        match = re.fullmatch(r"v(\d+)-to-v(\d+)\.py", pathlib.Path(argv[0]).name)
        if not match:
            print("FAIL a migration is tools/migrations/v<N>-to-v<M>.py")
            return 1
        source, TARGET = int(match.group(1)), int(match.group(2))
        if TARGET not in tree.VERSIONS:
            print(f"FAIL docs/schema/v{TARGET}/ doesn't exist; write the new version's schemas first")
            return 1
        MIGRATION = load_migration(argv[0])
    profiles = tree.walk(tree.PROFILES)
    with Pool(os.cpu_count()) as pool:
        refs = pool.map(profile_ref, profiles, chunksize=2000)
        if TARGET is not None:
            behind = [p for p, _, _, v in refs if v != source]
            if behind:
                print(f"FAIL {len(behind)} profiles aren't at version {source}, e.g. {behind[0]}")
                return 1
        for _, cs, platform, _ in refs:
            if cs:
                PLATFORMS.setdefault(cs, platform)
    with Pool(os.cpu_count()) as pool:  # forked again so workers see PLATFORMS
        renames = pool.map(rename_codeset, tree.walk(tree.CODESETS), chunksize=200)
    MOVED.update((old, new) for old, new in renames if old != new)
    # A rehash alone touches only the profiles whose codeset moved.
    todo = [(p, cs) for p, cs, _, _ in refs if MIGRATION or cs in MOVED]
    with Pool(os.cpu_count()) as pool:  # forked again so workers see MOVED
        updates = pool.map(update_profile, [p for p, _ in todo], chunksize=2000)
    changed = sum(c for c, _ in updates)
    used = {cs for _, cs, _, _ in refs if cs} - set(MOVED) | {cs for _, cs in updates if cs}
    removed = 0
    for path in tree.walk(tree.CODESETS):
        if path.stem not in used:
            path.unlink()
            removed += 1
    print(f"codesets renamed {len(MOVED)}, removed {removed}; profiles changed {changed} (revisions bumped)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

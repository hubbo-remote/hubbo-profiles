"""The repository's data tree: where profiles and codesets live, and how a profile is joined.

docs/using.md ("Read a profile") describes the storage form:
  profiles/<source>/<slug>.json              one device, at the path its id gives (profile_path);
  profiles/harmony/<nnn>/<n>.json            `codeset: <id>` in place of `commands`, or the
                                             whole profile with its `commands`
  codesets/<id[:2]>/<id>.json                {"commands": {...}}; <id> is the first 16 hex digits
                                             of the SHA-256 of the commands' canonical form
"""

import hashlib
import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROFILES = ROOT / "profiles"
CODESETS = ROOT / "codesets"
SCHEMA = ROOT / "docs" / "schema"
# Every spec version has its own folder, docs/schema/v<N>/: its schemas and its kinds and buttons tables.
VERSIONS = sorted(int(d.name[1:]) for d in SCHEMA.glob("v*") if d.name[1:].isdigit())
CURRENT = VERSIONS[-1]


def version_dir(n):
    return SCHEMA / f"v{n}"


def canonical(obj):
    """Sorted keys, no whitespace, UTF-8 (RFC 8785 for our integer-only subset)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(obj):
    """SHA-256 of the canonical form: a profile's hash."""
    return hashlib.sha256(canonical(obj)).hexdigest()


def codeset_id(commands):
    return digest(commands)[:16]


def codeset_path(cs_id):
    return CODESETS / cs_id[:2] / f"{cs_id}.json"


def dumps(obj):
    """The repository's file format: 2-space indent, UTF-8, trailing newline."""
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(dumps(obj))
    tmp.replace(path)  # atomic; parallel writers of one codeset write identical bytes


def write_codeset(commands):
    cs_id = codeset_id(commands)
    path = codeset_path(cs_id)
    if not path.exists():
        write(path, {"commands": commands})
    return cs_id


def split(doc):
    """A profile in storage form: its commands go to a shared codeset, named in their place."""
    cs_id = write_codeset(doc["commands"])
    return {("codeset" if k == "commands" else k): (cs_id if k == "commands" else v) for k, v in doc.items()}


def join(stored, load_codeset):
    """The profile for a stored device. `load_codeset(id)` returns the codeset's commands."""
    if "codeset" not in stored:
        return stored
    commands = load_codeset(stored["codeset"])
    return {("commands" if k == "codeset" else k): (commands if k == "codeset" else v) for k, v in stored.items()}


def load_codeset_file(cs_id):
    return json.loads(codeset_path(cs_id).read_text())["commands"]


def walk(folder):
    """Every .json file under folder, sorted, skipping dotfiles."""
    out = []
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        out += [pathlib.Path(dirpath) / f for f in filenames if f.endswith(".json") and not f.startswith(".")]
    return sorted(out)


def profile_path(profile_id):
    """Where a profile lives, from its id alone (docs/using.md, "Find a device"):
    harmony:<n> -> profiles/harmony/<n without its last three digits>/<n>.json (498661 -> 498/);
    anything else -> profiles/<source>/<slug>.json."""
    source, slug = profile_id.split(":", 1)
    base = PROFILES / source
    if source == "harmony":
        return base / f"{int(slug) // 1000:03d}" / f"{slug}.json"
    return base / f"{slug}.json"

"""Validate Hubbo device profiles: the JSON Schema, then the checks a schema can't express.

Usage (inside the tools image; see tools/bin/validate):
  validate.py                  the whole tree: tables, every profile (joined), every codeset
  validate.py <paths>          only these profile or codeset files (or folders); a codeset brings
                               in every profile that uses it
  validate.py --since <ref>    what CI runs on a pull request: the profiles and codesets changed
                               since a git ref, the whole-tree checks (ids, Harmony devices,
                               codesets) and the revision rule; everything when docs/schema/ or
                               tools/ changed; nothing when no profile data changed
  --hashes                     print only id<TAB>revision<TAB>sha256<TAB>path per profile
Exit status 1 if anything fails. Rules: docs/spec.md "Validation", CONTRIBUTING.md "Files" (repository), docs/schema/README.md (tables).
"""

import collections
import json
import os
import pathlib
import re
import subprocess
import sys
from multiprocessing import Pool

from jsonschema import Draft202012Validator

import tree

ROOT = tree.ROOT


COMMAND_DEFS = {"ble_hid": "bleHidCommand", "ir": "irCommand"}
# A valid command of each platform, standing in for the real ones once they're checked.
STUB = {"ble_hid": {"page": "consumer", "usage": "0x0001"}, "ir": {"pronto": "0000 006D 0001 0000 0001 0001"}}


class Version:
    """One spec version's schemas and tables (docs/schema/v<N>/). check_tables() reports table errors."""

    def __init__(self, n):
        self.n = n
        self.dir = tree.version_dir(n)
        self.profile_schema = json.loads((self.dir / "profile.schema.json").read_text())
        self.validator = Draft202012Validator(self.profile_schema)
        self.commands_validators = {
            platform: Draft202012Validator({**self.profile_schema["properties"]["commands"],
                                            "additionalProperties": {"$ref": f"#/$defs/{d}"},
                                            "$defs": self.profile_schema["$defs"]})
            for platform, d in COMMAND_DEFS.items() if d in self.profile_schema["$defs"]}
        self.kinds = self.table_ids("kinds", "id")
        self.buttons = self.table_ids("buttons", "button")

    def table_ids(self, name, key):
        try:
            return {row[key] for row in json.loads((self.dir / f"{name}.json").read_text())[name]}
        except (OSError, ValueError, KeyError, TypeError):
            return set()  # check_tables() reports it

    def table_validator(self, name):
        return Draft202012Validator(json.loads((self.dir / f"{name}.schema.json").read_text()))


VERSIONS = {n: Version(n) for n in tree.VERSIONS}
CURRENT = VERSIONS[tree.CURRENT]

WARN_BYTES = 32 * 1024   # stored size (minified, without meta) the hub would keep
MAX_BYTES = 256 * 1024
DIGITS = [str(d) for d in range(10)]
HUB_MAX_COMMANDS = 128   # the hub's cap per device; the format allows 512
canonical = tree.canonical


def stored(doc):
    """What the hub keeps: the document minus `meta`."""
    return {k: v for k, v in doc.items() if k != "meta"}


def step_refs(steps):
    return [s["command"] for s in steps or [] if "command" in s]


def schema_errors(v, doc):
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}"
            for e in v.iter_errors(doc)]


def command_errors(commands, platform, version):
    """Checks on the commands alone: schema, case clashes, Pronto lengths."""
    if platform not in version.commands_validators:
        return []  # the profile schema reports the platform
    errors = [f"commands/{e}" for e in schema_errors(version.commands_validators[platform], commands)]
    if errors or not isinstance(commands, dict):
        return errors
    return command_extra(commands, platform)


def command_extra(commands, platform):
    """What the schema can't check on commands: case clashes and Pronto lengths."""
    errors = []
    folded = {}
    for name in commands:
        other = folded.setdefault(name.lower(), name)
        if other != name:
            errors.append(f"commands {other!r} and {name!r} differ only in case")
    if platform == "ir":
        for name, cmd in commands.items():
            for field in ("pronto", "pronto_toggle"):
                if field in cmd:
                    problem = pronto_problem(cmd[field])
                    if problem:
                        errors.append(f"commands.{name}.{field}: {problem}")
    return errors


def pronto_problem(pronto):
    words = [int(w, 16) for w in pronto.split()]
    freq, once, repeat = words[1], words[2], words[3]
    if freq == 0:
        return "carrier word is 0"
    if once + repeat == 0:
        return "no burst pairs"
    if len(words) != 4 + 2 * (once + repeat):
        return f"has {len(words) - 4} duration words; the header says {2 * (once + repeat)}"
    if 0 in words[4:]:
        return "has a zero duration"
    return None


def reference_errors(doc, version):
    """Checks across the document: kind, buttons, id prefix, every named command exists."""
    errors = []
    names = set(doc["commands"])
    if version.kinds and doc["kind"] not in version.kinds:
        errors.append(f"kind {doc['kind']!r} isn't in kinds.json")
    for button in doc.get("buttons", {}):
        if version.buttons and button not in version.buttons:
            errors.append(f"buttons.{button} isn't a button in buttons.json")
    prefix = doc["id"].split(":", 1)[0]
    if prefix != doc["source"]:
        errors.append(f"id prefix {prefix!r} doesn't match source {doc['source']!r}")

    def check(where, refs):
        for ref in refs:
            if ref not in names:
                errors.append(f"{where} names command {ref!r}, which isn't in commands")

    power = doc.get("power", {})
    for part in ("on", "off", "toggle"):
        check(f"power.{part}", step_refs(power.get(part)))
    seen_inputs = set()
    for i, entry in enumerate(doc.get("inputs", [])):
        check(f"inputs[{i}] {entry['name']!r}", step_refs(entry["steps"]))
        if entry["name"].lower() in seen_inputs:
            errors.append(f"input {entry['name']!r} is listed twice")
        seen_inputs.add(entry["name"].lower())
    channels = doc.get("channels")
    if channels is not None:
        check("channels", [channels[k] for k in ("start", "finish") if k in channels])
        missing = [d for d in DIGITS if d not in names]
        if missing:
            errors.append(f"channels needs digit commands 0-9; missing {', '.join(missing)}")
    for button, target in doc.get("buttons", {}).items():
        if target is not None:
            check(f"buttons.{button}", [target])
    return errors


def check_doc(doc, commands_checked=None):
    """(errors, info) for one whole profile. info is None when the schema fails.

    commands_checked: the result of command_errors() for these commands, when the caller has it
    already (a shared codeset); the schema then runs on the rest of the document only."""
    if not isinstance(doc, dict):
        return ["(root): a profile is a JSON object"], None
    version = VERSIONS.get(doc.get("schema_version"))
    if version is None:
        return [f"schema_version {doc.get('schema_version')!r} isn't a spec version "
                f"(known: {', '.join(map(str, VERSIONS))})"], None
    commands, platform = doc.get("commands"), doc.get("platform")
    if commands_checked is not None and isinstance(commands, dict) and platform in STUB:
        # The commands were checked with their codeset; one stand-in keeps the rest's check cheap.
        errors = list(commands_checked) + schema_errors(
            version.validator, {**doc, "commands": {"Stub": STUB[platform]}})
    else:
        errors = schema_errors(version.validator, doc)
        if not errors:
            errors = command_extra(commands, platform)
    errors.sort()
    if errors:
        return errors, None  # the reference checks assume a schema-valid document
    errors = reference_errors(doc, version)
    size = len(canonical(stored(doc)))
    if size > MAX_BYTES:
        errors.append(f"stored size {size} B is over the {MAX_BYTES} B limit")
    warnings = []
    if size > WARN_BYTES:
        warnings.append(f"over the {WARN_BYTES // 1024} KB warning line")
    if len(doc["commands"]) > HUB_MAX_COMMANDS:
        warnings.append(f"more than the hub's {HUB_MAX_COMMANDS} commands")
    info = {
        "id": doc["id"],
        "schema_version": doc["schema_version"],
        "revision": doc["revision"],
        "sha256": tree.digest(doc),
        "commands": len(doc["commands"]),
        "stored": size,
        "warnings": warnings,
    }
    return errors, info


def check_tables():
    """Validate every version's kinds.json and buttons.json.

    Returns {path: (doc, errors)}."""
    tables = {}
    for version in VERSIONS.values():
        for name in ("kinds", "buttons"):
            path = version.dir / f"{name}.json"
            label = str(path.relative_to(ROOT))
            try:
                doc = json.loads(path.read_text())
            except (OSError, ValueError) as e:
                tables[label] = (None, [f"can't read: {e}"])
                continue
            errors = schema_errors(version.table_validator(name), doc)
            tables[label] = (doc, errors)
            if errors:
                continue
            if name == "kinds":
                seen, codes = set(), {}
                for row in doc["kinds"]:
                    if row["id"] in seen:
                        errors.append(f"kind {row['id']!r} is listed twice")
                    seen.add(row["id"])
                    for code in row["harmony"]:
                        if code in codes:
                            errors.append(f"Harmony type {code} maps to both {codes[code]!r} and {row['id']!r}")
                        codes[code] = row["id"]
                if "other" not in seen:
                    errors.append("kind 'other' is missing (it's the fallback)")
            else:
                seen = set()
                for row in doc["buttons"]:
                    if row["button"] in seen:
                        errors.append(f"button {row['button']!r} is listed twice")
                    seen.add(row["button"])
                    lowered = [c.lower() for c in row["candidates"]]
                    if len(set(lowered)) != len(lowered):
                        errors.append(f"button {row['button']!r} lists a candidate twice (ignoring case)")
    return tables


# ---- the tree ---------------------------------------------------------------------------------

def rel(path):
    path = pathlib.Path(path).resolve()
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def read_json(path, strict=False):
    """(doc, problem). strict: the bytes must also be in the repository's file format (tree.dumps).
    Codesets and split profiles must be: a consumer may join them by splicing the codeset's text
    into the profile's. Hand-written whole profiles keep their own layout."""
    try:
        text = pathlib.Path(path).read_bytes().decode()
        doc = json.loads(text)
    except (OSError, ValueError) as e:
        return None, f"can't read: {e}"
    if strict(doc) if callable(strict) else strict:
        if text != tree.dumps(doc):
            return doc, ("isn't in the file format (2-space indent, UTF-8, trailing newline); "
                         f"run tools/bin/format {rel(path)}")
    return doc, None


def is_split(doc):
    return isinstance(doc, dict) and "codeset" in doc


def read_codeset_file(path):
    """(errors, codeset id, commands) for one codeset file."""
    doc, problem = read_json(path, strict=True)
    if problem:
        return [problem], None, None
    if not isinstance(doc, dict) or list(doc) != ["commands"] or not isinstance(doc["commands"], dict):
        return ['a codeset file is {"commands": {...}} and nothing else'], None, None
    cs_id = tree.codeset_id(doc["commands"])
    if pathlib.Path(path).resolve() != tree.codeset_path(cs_id).resolve():
        return [f"its content belongs at {rel(tree.codeset_path(cs_id))}; run tools/bin/rehash"], None, None
    return [], cs_id, doc["commands"]


def check_codeset_file(path):
    """(errors, codeset id) for one codeset file."""
    return read_codeset_file(path)[:2]


def check_profile_file(path, codeset_cache):
    """(errors, info, stored doc) for one profile file, joined with its codeset."""
    raw, problem = read_json(path, strict=is_split)
    if problem:
        return [problem], None, None
    checked = None
    doc = raw
    if isinstance(raw, dict) and "codeset" in raw:
        version = VERSIONS.get(raw.get("schema_version"))
        if version is None:
            return check_doc(raw)[0], None, raw  # reports the unknown version
        cs_id = raw["codeset"]
        if "commands" in raw:
            return ["has both codeset and commands"], None, raw
        if not isinstance(cs_id, str) or not re.fullmatch(r"[0-9a-f]{16}", cs_id):
            return [f"codeset {cs_id!r} isn't a codeset id (16 lowercase hex digits)"], None, raw
        key = (cs_id, raw.get("platform"), raw.get("schema_version"))
        if key not in codeset_cache:
            cs_path = tree.codeset_path(cs_id)
            cs_errors, _, commands = read_codeset_file(cs_path) if cs_path.exists() else (
                [f"codeset {cs_id} doesn't exist"], None, None)
            codeset_cache[key] = (commands, [f"codeset {cs_id}: {e}" for e in cs_errors] or
                                  command_errors(commands, raw.get("platform"), version))
        commands, checked = codeset_cache[key]
        if commands is None:
            return checked, None, raw
        doc = tree.join(raw, lambda _: commands)
    errors, info = check_doc(doc, commands_checked=checked)
    if info:
        expected = tree.profile_path(doc["id"])
        if pathlib.Path(path).resolve() != expected.resolve():
            errors.append(f"id {doc['id']} belongs at {rel(expected)}")
    return errors, info, raw


def check_group(paths):
    """Profiles that share a codeset, so its commands are checked once."""
    cache = {}
    return [(str(path), *check_profile_file(path, cache)[:2]) for path in paths]


def scan(path):
    """(path, id, codeset, Harmony device id) for one profile file, read without trusting its shape:
    what the whole-tree checks need. Anything malformed is None here; the profile check reports it."""
    raw, _ = read_json(path)
    raw = raw if isinstance(raw, dict) else {}

    def text(v):
        return v if isinstance(v, str) else None

    meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    harmony = meta.get("harmony") if isinstance(meta.get("harmony"), dict) else {}
    gid = harmony.get("global_device_id")
    return str(path), text(raw.get("id")), text(raw.get("codeset")), gid if isinstance(gid, int) else None


def tree_errors(refs):
    """Checks across every profile: ids and Harmony devices claimed once, every codeset named
    exists, every codeset is used."""
    errors, ids, gids, used = collections.defaultdict(list), {}, {}, set()
    for path, pid, cs, gid in sorted(refs):
        for key, seen, what in ((pid, ids, "id"), (gid, gids, "Harmony device")):
            if key is None:
                continue
            if key in seen:
                errors[rel(path)].append(f"{what} {key} is also {seen[key]}")
            seen.setdefault(key, rel(path))
        if cs:
            used.add(cs)
            if re.fullmatch(r"[0-9a-f]{16}", cs) and not tree.codeset_path(cs).exists():
                errors[rel(path)].append(f"codeset {cs} doesn't exist")
    for f in tree.walk(tree.CODESETS):
        if f.stem not in used:
            errors[rel(f)].append("no profile uses this codeset; run tools/bin/rehash")
    return list(errors.items())


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True, capture_output=True, text=True).stdout


def changed_since(ref):
    """Every path changed since a git ref, committed or not, deletions included."""
    names = git("diff", "--name-only", "--no-renames", f"{ref}...HEAD").split()
    names += git("diff", "--name-only", "--no-renames", "HEAD").split()  # uncommitted edits
    names += git("ls-files", "--others", "--exclude-standard").split()
    return sorted(set(names))


# A change to any of these can change the verdict on any profile: check the whole tree.
WHOLE_TREE = ("docs/schema/", "tools/")


class GitFiles:
    """Files at a git ref, read through one `git cat-file --batch` (a migration PR touches every profile)."""

    def __init__(self, ref):
        self.ref = ref
        self.proc = subprocess.Popen(["git", "-C", str(ROOT), "cat-file", "--batch"],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def json(self, name):
        self.proc.stdin.write(f"{self.ref}:{name}\n".encode())
        self.proc.stdin.flush()
        header = self.proc.stdout.readline().split()
        if header[-1] == b"missing":
            return None
        data = self.proc.stdout.read(int(header[2]) + 1)  # the blob and its newline
        return json.loads(data)

    def close(self):
        self.proc.stdin.close()
        self.proc.wait()


def revision_errors(ref, results):
    """A profile whose joined content changed since <ref> must have a higher revision."""
    errors, old_codesets = [], {}
    files = GitFiles(ref)

    def old_codeset(cs):
        if cs not in old_codesets:
            old_codesets[cs] = (files.json(rel(tree.codeset_path(cs))) or {}).get("commands")
        return old_codesets[cs]

    for path, errs, info in results:
        if errs or not info:
            continue
        name = rel(path)
        old_raw = files.json(name)
        if old_raw is None:
            continue  # new file
        old = tree.join(old_raw, old_codeset)
        if old.get("commands") is None:
            continue
        if tree.digest(old) != info["sha256"] and info["revision"] <= old["revision"]:
            errors.append((name, [f"changed since {ref} but revision is still {info['revision']}; bump it"]))
    files.close()
    return errors


def main(args):
    hashes = "--hashes" in args
    args = [a for a in args if a != "--hashes"]
    since = None
    if "--since" in args:
        i = args.index("--since")
        since = args[i + 1]
        args = args[:i] + args[i + 2:]
    log = sys.stderr if hashes else sys.stdout
    failures = []

    for label, (doc, errors) in check_tables().items():
        if errors:
            failures.append((label, errors))
        elif not hashes:
            key = "kinds" if "kinds" in doc else "buttons"
            print(f"ok   {label}: {len(doc[key])} {key}")

    full = not args and since is None
    if since is not None:
        changed = changed_since(since)
        full = any(n.startswith(WHOLE_TREE) for n in changed)
        data = [n for n in changed if n.endswith(".json") and n.startswith(("profiles/", "codesets/"))]
        args = [] if full else [n for n in data if (ROOT / n).exists()]
        if not full and not data:
            print(f"ok   nothing changed since {since} that profiles depend on")
            return 1 if failures else 0
    targets = [pathlib.Path(a) if pathlib.Path(a).is_absolute() else ROOT / a for a in args] if args or not full \
        else [d for d in (tree.PROFILES, tree.CODESETS) if d.exists()]
    files = [f for t in targets for f in (tree.walk(t) if t.is_dir() else [t])]
    codesets_dir = tree.CODESETS.resolve()
    codeset_files = [] if full else [f for f in files if f.resolve().is_relative_to(codesets_dir)]
    profile_files = [f for f in files if not f.resolve().is_relative_to(codesets_dir)]
    whole_tree = full or since is not None

    with Pool(os.cpu_count()) as pool:
        # The whole-tree checks need every profile's id, codeset and Harmony device; so does
        # finding the profiles that use a changed codeset.
        refs = pool.map(scan, tree.walk(tree.PROFILES), chunksize=2000) if whole_tree or codeset_files else []
        if whole_tree:
            failures += tree_errors(refs)
        if codeset_files:
            # A changed codeset is checked through every profile that uses it.
            wanted = {check_codeset_file(f)[1] or f.stem for f in codeset_files}
            profile_files = sorted(set(profile_files) | {pathlib.Path(p) for p, _, cs, _ in refs if cs in wanted})
        for f, (errors, _) in zip(codeset_files, pool.map(check_codeset_file, codeset_files, chunksize=200)):
            if errors:
                failures.append((rel(f), errors))

        codeset_of = {p: cs for p, _, cs, _ in refs}
        if not refs:
            codeset_of = {p: cs for p, _, cs, _ in pool.map(scan, profile_files, chunksize=2000)}
        groups = collections.defaultdict(list)
        for path in profile_files:
            groups[codeset_of.get(str(path)) or str(path)].append(path)
        results = [r for batch in pool.imap_unordered(check_group, list(groups.values()), chunksize=20) for r in batch]

    results.sort()
    counts = collections.Counter()
    for path, errors, info in results:
        if info and whole_tree and info["schema_version"] != CURRENT.n:
            errors = errors + [f"is at spec version {info['schema_version']}; the data must be at version "
                               f"{CURRENT.n} (tools/bin/migrate)"]
        if errors:
            failures.append((rel(path), errors))
            continue
        counts["profiles"] += 1
        for w in info["warnings"]:
            counts[w] += 1
        if hashes:
            print(f"{info['id']}\t{info['revision']}\t{info['sha256']}\t{rel(path)}")
        elif not full and len(results) <= 50:
            note = "".join(f"  ({w})" for w in info["warnings"])
            print(f"ok   {rel(path)}: {info['commands']} commands, stored {info['stored']} B, "
                  f"sha256 {info['sha256'][:16]}{note}")
    if whole_tree:
        counts["codesets"] = len({cs for _, _, cs, _ in refs if cs})
    if since is not None:
        failures += revision_errors(since, results)

    for label, errors in failures:
        print(f"FAIL {label}", file=log)
        for e in errors:
            print(f"     {e}", file=log)
    if not hashes:
        summary = ", ".join(f"{v} {k}" for k, v in counts.items())
        print(f"{'FAIL' if failures else 'ok'}   {summary or 'nothing to check'}; {len(failures)} failing")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

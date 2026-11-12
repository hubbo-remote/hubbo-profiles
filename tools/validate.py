"""Validate Hubbo device profiles: the JSON Schema, then the checks a schema can't express.

Usage (inside the tools image; see bin/validate): validate.py [file-or-dir ...]
With no arguments it checks profiles/ and samples/. Exit status 1 if any file fails.
"""

import gzip
import hashlib
import json
import pathlib
import sys

from jsonschema import Draft202012Validator

ROOT = pathlib.Path(__file__).resolve().parent.parent


def validator(name):
    return Draft202012Validator(json.loads((ROOT / "schema" / f"{name}.schema.json").read_text()))


VALIDATOR = validator("profile")
# Filled by check_tables(); profiles are checked against them.
KINDS = set()
BUTTONS = set()

# Size budget (minified JSON, as the hub would store it without meta).
WARN_BYTES = 32 * 1024
MAX_BYTES = 128 * 1024
DIGITS = [str(d) for d in range(10)]
HUB_MAX_COMMANDS = 128  # the hub's cap per device; the format allows 512


def canonical(doc):
    """The hash form: sorted keys, no whitespace, UTF-8 (RFC 8785 for our integer-only subset)."""
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def stored(doc):
    """What the hub keeps: the document minus `meta`."""
    return {k: v for k, v in doc.items() if k != "meta"}


def step_refs(steps):
    return [s["command"] for s in steps or [] if "command" in s]


def semantic_errors(doc):
    errors = []
    commands = doc["commands"]
    names = set(commands)

    folded = {}
    for name in commands:
        other = folded.setdefault(name.lower(), name)
        if other != name:
            errors.append(f"commands {other!r} and {name!r} differ only in case")

    if KINDS and doc["kind"] not in KINDS:
        errors.append(f"kind {doc['kind']!r} isn't in kinds.json")
    for button in doc.get("buttons", {}):
        if BUTTONS and button not in BUTTONS:
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
    for i, entry in enumerate(doc.get("inputs", [])):
        check(f"inputs[{i}] {entry['name']!r}", step_refs(entry["steps"]))
    seen_inputs = set()
    for entry in doc.get("inputs", []):
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

    if doc["platform"] == "ir":
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


def check_file(path):
    try:
        doc = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        return [f"can't read: {e}"], None
    errors = sorted(schema_errors(VALIDATOR, doc))
    if errors:
        return errors, None  # semantic checks assume a schema-valid document
    errors = semantic_errors(doc)
    body = canonical(stored(doc))
    size = len(body)
    if size > MAX_BYTES:
        errors.append(f"stored size {size} B is over the {MAX_BYTES} B limit")
    warnings = []
    if size > WARN_BYTES:
        warnings.append(f"over the {WARN_BYTES // 1024} KB warning line")
    if len(doc["commands"]) > HUB_MAX_COMMANDS:
        warnings.append(f"more than the hub's {HUB_MAX_COMMANDS} commands")
    info = {
        "id": doc["id"],
        "revision": doc["revision"],
        "sha256": hashlib.sha256(canonical(doc)).hexdigest(),
        "commands": len(doc["commands"]),
        "stored": size,
        "gzip": len(gzip.compress(body, 9)),
        "warnings": warnings,
    }
    return errors, info


def files(args):
    targets = [pathlib.Path(a) for a in args] or [ROOT / "profiles", ROOT / "samples"]
    for target in targets:
        if target.is_dir():
            yield from sorted(target.rglob("*.json"))
        else:
            yield target


def schema_errors(v, doc):
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}"
            for e in v.iter_errors(doc)]


def check_tables():
    """Validate kinds.json and buttons.json and load them for the profile checks.

    Returns {name: (doc, errors)}."""
    tables = {}
    for name in ("kinds", "buttons"):
        try:
            doc = json.loads((ROOT / f"{name}.json").read_text())
        except (OSError, ValueError) as e:
            tables[name] = (None, [f"can't read: {e}"])
            continue
        tables[name] = (doc, schema_errors(validator(name), doc))

    kinds, errors = tables["kinds"]
    if kinds and not errors:
        seen, codes = set(), {}
        for row in kinds["kinds"]:
            if row["id"] in seen:
                errors.append(f"kind {row['id']!r} is listed twice")
            seen.add(row["id"])
            for code in row["harmony"]:
                if code in codes:
                    errors.append(f"Harmony type {code} maps to both {codes[code]!r} and {row['id']!r}")
                codes[code] = row["id"]
        if "other" not in seen:
            errors.append("kind 'other' is missing (it's the fallback)")
        KINDS.update(seen)

    buttons, errors = tables["buttons"]
    if buttons and not errors:
        for row in buttons["buttons"]:
            if row["button"] in BUTTONS:
                errors.append(f"button {row['button']!r} is listed twice")
            BUTTONS.add(row["button"])
            lowered = [c.lower() for c in row["candidates"]]
            if len(set(lowered)) != len(lowered):
                errors.append(f"button {row['button']!r} lists a candidate twice (ignoring case)")
    return tables


def report(label, errors, out):
    print(f"FAIL {label}", file=out)
    for e in errors:
        print(f"     {e}", file=out)


def main(args):
    hashes = "--hashes" in args
    args = [a for a in args if a != "--hashes"]
    # With --hashes, stdout is only "id<TAB>revision<TAB>sha256<TAB>path" per profile;
    # failures still go to stderr and still fail the run.
    log = sys.stderr if hashes else sys.stdout
    failed = 0
    for name, (doc, errors) in check_tables().items():
        if errors:
            failed += 1
            report(f"{name}.json", errors, log)
        elif not hashes:
            print(f"ok   {name}.json: {len(doc[name])} {name}")
    for path in files(args):
        errors, info = check_file(path)
        shown = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        if errors:
            failed += 1
            report(shown, errors, log)
        elif hashes:
            print(f"{info['id']}\t{info['revision']}\t{info['sha256']}\t{shown}")
        else:
            note = "".join(f"  ({w})" for w in info["warnings"])
            print(f"ok   {shown}: {info['commands']} commands, stored {info['stored']} B, "
                  f"gzip {info['gzip']} B, sha256 {info['sha256'][:16]}{note}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

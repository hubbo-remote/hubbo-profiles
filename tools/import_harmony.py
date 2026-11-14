"""Import the Harmony archive into this repository's data tree, once.

Usage (inside the tools image; see tools/bin/import-harmony): import_harmony.py <archive-root> [--replace]
The archive is read in place and never copied. It writes, in storage form (profiles/README.md):

  profiles/harmony/<nnn>/<globalDeviceId>.json   one device each (<nnn>: the id without its last 3 digits)
  codesets/<xx>/<id>.json                                 each set of commands once

After the import, the committed data is the source of truth: fixes are edits to those files, and
spec changes are migrations (tools/bin/migrate). So this refuses to run when profiles/harmony/ exists,
unless --replace, which deletes profiles/harmony/ and codesets/ first and loses every edit since.
Rules: tools/harmony-import.md. The run report goes to stdout and build/import-report.json.
Every profile is validated whole (joined) with tools/validate.py's checks; any failure fails the run.
"""

import collections
import json
import os
import pathlib
import re
import shutil
import sys
import time
from multiprocessing import Pool

import harmony_render
import tree
import validate

# The revision of every imported profile.
IMPORT_REVISION = 1

ROOT = tree.ROOT
HANDWRITTEN = tree.PROFILES / "hubbo"

TEST_MANUFACTURERS = {"Z-Harmony Test", "Harmony Pro", "Harmony Beta", "LogitechHarmony"}
TEST_DEVICE_TYPES = {0, 49, 57, 60, 66}
PLACEHOLDER_KEYCODE = "G:Saitek 11 Bit:()(0x000)():3"

# Spelling-only synonyms (key: lowercase letters and digits). Meanings (Exit/Back/Return,
# OK/Select/Enter) stay distinct; buttons.json's fallbacks resolve them.
SYNONYMS = {
    "up": "DirectionUp", "arrowup": "DirectionUp", "cursorup": "DirectionUp",
    "down": "DirectionDown", "arrowdown": "DirectionDown", "cursordown": "DirectionDown",
    "left": "DirectionLeft", "arrowleft": "DirectionLeft", "cursorleft": "DirectionLeft",
    "right": "DirectionRight", "arrowright": "DirectionRight", "cursorright": "DirectionRight",
    "ok": "OK", "playpause": "PlayPause", "mutetoggle": "Mute", "skipbackward": "SkipBack",
}
PUNCT_NAMES = {"-": "Dash", ".": "Dot", "+": "Plus", "*": "Star", "#": "Hash"}
VALID_NAME = re.compile(r"[A-Za-z0-9]{1,32}")
PRONTO = re.compile(r"0000 [0-9A-F]{4} [0-9A-F]{4} [0-9A-F]{4}( [0-9A-F]{4} [0-9A-F]{4})+")

# Imported at the current spec version, against its tables.
KINDS = {code: row["id"]
         for row in json.loads((tree.version_dir(tree.CURRENT) / "kinds.json").read_text())["kinds"]
         for code in row["harmony"]}
BUTTONS = json.loads((tree.version_dir(tree.CURRENT) / "buttons.json").read_text())["buttons"]

# Set in the parent before the pool forks.
ARCHIVE = None
PROTOCOLS = {}      # toggle-bit protocols only: name -> harmony_render.Protocol
SPELLING = {}       # name key -> the archive's most common valid spelling


def collapse(text):
    return " ".join((text or "").split())


def name_key(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def usable(command):
    """An IR command with valid Pronto that isn't the placeholder code."""
    pronto = command.get("pronto", "").upper()
    return (command.get("keycode") != PLACEHOLDER_KEYCODE and PRONTO.fullmatch(pronto) is not None
            and validate.pronto_problem(pronto) is None)


# ---- pass 1: scan devices and codesets --------------------------------------------------------

def scan_device(path):
    d = json.loads(path.read_text())
    return {"path": str(path.relative_to(ARCHIVE)), "gid": d["globalDeviceId"],
            "manufacturer": collapse(d.get("manufacturer"))[:64], "model": collapse(d.get("model"))[:64],
            "type": d.get("deviceType"), "codeset": d.get("codeset")}


def scan_codeset(path):
    commands = json.loads(path.read_text())["commands"]
    real = [c for c in commands if usable(c)]
    placeholder = (any(c.get("keycode") == PLACEHOLDER_KEYCODE for c in commands) and not real) or (
        len(real) >= 3 and len({c["pronto"] for c in real}) == 1)
    names = collections.Counter(collapse(c["name"]) for c in commands)
    return str(path.relative_to(ARCHIVE)), len(real), placeholder, names


def spelling_table(name_counts):
    best = {}
    for name, count in name_counts.items():
        if VALID_NAME.fullmatch(name):
            key = name_key(name)
            if key not in best or count > best[key][1]:
                best[key] = (name, count)
    return {k: v[0] for k, v in best.items()}


# ---- pass 2: convert ----------------------------------------------------------------------------

def preferred_names(raw):
    """Names to try for a Harmony command name, best first."""
    name = collapse(raw)
    if name in PUNCT_NAMES:
        return [PUNCT_NAMES[name]]
    key = name_key(name)
    out = []
    if key in SYNONYMS:
        out.append(SYNONYMS[key])
    if key in SPELLING:
        out.append(SPELLING[key])
    # `Zoom+`/`Zoom-` and `10+` are keys of their own, not spellings of `Zoom` or `10`.
    spelled = re.sub(r"-$", " Minus", name.replace("+", " Plus "))
    camel = "".join(p[:1].upper() + p[1:] for p in re.split(r"[^A-Za-z0-9]+", spelled) if p)[:32]
    out.append(camel or "Command")
    return out


def convert_codeset(rel, issues):
    """{harmony name: profile name} and the profile's commands, shared by every device with this set."""
    commands = json.loads((ARCHIVE / rel).read_text())["commands"]
    kept = [c for c in commands if usable(c)]
    if len(kept) < len(commands):
        issues["commands dropped (no IR, invalid Pronto, or the placeholder code)"] += 1
    taken, names, out = set(), {}, {}
    # Names already in canonical form claim first, so `Up` can't take `DirectionUp` from itself.
    for c in sorted(kept, key=lambda c: (preferred_names(c["name"])[0] != collapse(c["name"]), c["name"])):
        raw = c["name"]
        if raw in names:
            continue  # the same name twice in one set: keep the first
        options = preferred_names(raw)
        name = next((n for n in options if n.lower() not in taken), None)
        numbered = name is None
        if numbered:
            base, i = options[-1][:30], 2
            while f"{base}{i}".lower() in taken:
                i += 1
            name = f"{base}{i}"
            issues["command names numbered to avoid a clash"] += 1
        taken.add(name.lower())
        names[raw] = name
        cmd = {"pronto": c["pronto"].upper()}
        proto = PROTOCOLS.get(c.get("protocol"))
        if proto:
            try:
                ok = proto.render(c["keycode"], 0) == cmd["pronto"]
            except (KeyError, ValueError, IndexError):
                ok = False
            if ok:
                flipped = proto.render(c["keycode"], 1)
                if flipped != cmd["pronto"]:
                    cmd["pronto_toggle"] = flipped
            else:
                issues["toggle-bit copy not rendered"] += 1
        if collapse(raw) and (numbered or not VALID_NAME.fullmatch(collapse(raw))):
            cmd["label"] = collapse(raw)[:32]
        out[name] = cmd
    # Steps sometimes spell a command differently from the set (`InputCD` for `InputCd`): resolve
    # them by exact name, then ignoring case and punctuation.
    for raw, name in sorted(names.items()):
        names.setdefault(KEY_PREFIX + name_key(raw), name)
    return names, out


KEY_PREFIX = "\0"  # marks the case-and-punctuation-free entries in a names map


def resolve(names, raw):
    return names.get(raw) or names.get(KEY_PREFIX + name_key(raw))


def convert_steps(steps, names, issues, where):
    """Harmony action list -> profile steps, or None (with an issue) if it can't be carried."""
    out = []
    for step in steps or []:
        if isinstance(step, str):
            step = {"command": step}
        if "set" in step:
            continue  # a state record, not a transmission
        if "delayMs" in step:
            if step["delayMs"] > 0:
                out.append({"delay_ms": min(step["delayMs"], 60000)})
        elif "command" in step:
            name = resolve(names, step["command"])
            if name is None:
                issues[f"{where} dropped: names a command the set doesn't have"] += 1
                return None
            s = {"command": name}
            if step.get("durationMs"):
                s["hold_ms"] = min(step["durationMs"], 10000)
            out.append(s)
        else:
            issues[f"{where} dropped: hold with no duration"] += 1
            return None
    if len(out) > 16:
        issues[f"{where} dropped: more than 16 steps"] += 1
        return None
    return out or None


def convert_device(dev, names, commands, issues):
    d = json.loads((ARCHIVE / dev["path"]).read_text())
    t = d.get("timing") or {}
    doc = {
        "schema_version": tree.CURRENT,
        "id": f"harmony:{dev['gid']}",
        "revision": IMPORT_REVISION,
        "source": "harmony",
        "manufacturer": dev["manufacturer"],
        "model": dev["model"],
        "kind": KINDS.get(dev["type"], "other"),
        "platform": "ir",
        "commands": commands,
    }

    power = d.get("power") or {}
    ptype = power.get("type")
    if ptype in ("discrete", "toggle"):
        parts = ("on", "off") if ptype == "discrete" else ("toggle",)
        p = {"type": ptype}
        for part in parts:
            steps = convert_steps(power.get(part), names, issues, "power")
            if steps is None:
                p = None
                break
            p[part] = steps
        if p and ptype == "discrete" and p["on"] == p["off"]:
            issues["power on equals off: made a toggle"] += 1
            p = {"type": "toggle", "toggle": p["on"]}
        if p:
            if "powerOnDelay" in t:
                p["on_delay_ms"] = min(t["powerOnDelay"], 60000)
            doc["power"] = p
    if power.get("onReset"):
        issues["power.onReset (state steps) not carried"] += 1

    timing = {}
    if "interKeyDelay" in t:
        timing["key_delay_ms"] = min(t["interKeyDelay"], 5000)
    if "inputDelay" in t:
        timing["input_delay_ms"] = min(t["inputDelay"], 60000)
    if "pressMinRepeats" in t:
        timing["ir_repeats"] = max(0, min(t["pressMinRepeats"], 20))
    if timing:
        doc["timing"] = timing

    block = d.get("inputs") or {}
    inputs, seen, cycling = [], set(), False
    for entry in block.get("list", []):
        if not entry.get("commands"):
            cycling = True
            continue
        steps = convert_steps((block.get("start") or []) + entry["commands"] + (block.get("finish") or []),
                              names, issues, "input")
        name = collapse(entry["name"])[:64]
        if steps and name and name.lower() not in seen:
            seen.add(name.lower())
            inputs.append({"name": name, "steps": steps})
    if cycling:
        issues["inputs reached only by cycling not carried"] += 1
    if inputs:
        doc["inputs"] = inputs[:64]

    tuning = d.get("channelTuning")
    if tuning:
        if all(str(n) in commands for n in range(10)):
            ch = {}
            if tuning.get("fixedDigits"):
                ch["digits"] = tuning["fixedDigits"]
            for part in ("start", "finish"):
                steps = convert_steps(tuning.get(part), names, issues, "channels") if tuning.get(part) else None
                if steps and len(steps) == 1 and list(steps[0]) == ["command"]:
                    ch[part] = steps[0]["command"]
                elif tuning.get(part):
                    issues[f"channels.{part} not carried: more than one step"] += 1
            if tuning.get("greaterTen") or tuning.get("greaterHundred"):
                issues["channels: the -/-- prefix key not carried"] += 1
            doc["channels"] = ch
        else:
            issues["channels dropped: no digit commands"] += 1

    doc["meta"] = {
        "sources": [f"Harmony archive (CC0): {dev['path']}"],
        "harmony": {"global_device_id": dev["gid"], "device_type": dev["type"],
                    "codeset": pathlib.Path(dev["codeset"]).stem},
    }
    return doc


def fill(doc):
    names = {n.lower() for n in doc["commands"]}
    return [row["button"] for row in BUTTONS if any(c.lower() in names for c in row["candidates"])]


def convert_group(task):
    """Convert every kept device that shares one codeset."""
    rel, devices = task
    issues = collections.Counter()
    names, commands = convert_codeset(rel, issues)
    results = []
    for dev in devices:
        dev_issues = collections.Counter()
        doc = convert_device(dev, names, commands, dev_issues)
        errors, info = validate.check_doc(doc)
        if errors:
            results.append({"id": doc["id"], "errors": errors[:5]})
            continue
        dev_issues.update(issues)
        for w in info["warnings"]:
            dev_issues[f"hub note: {w}"] += 1
        tree.write(tree.profile_path(doc["id"]), tree.split(doc))
        results.append({"issues": sorted(dev_issues), "fill": fill(doc), "kind": doc["kind"]})
    return results


# ---- main ---------------------------------------------------------------------------------------

def load_handwritten(errors):
    docs = []
    for path in sorted(HANDWRITTEN.glob("*.json")):
        doc = json.loads(path.read_text())
        problems, _ = validate.check_doc(doc)
        if problems:
            errors.append(f"profiles/hubbo/{path.name}: {problems[:3]}")
        else:
            docs.append(doc)
    return docs


def main(argv):
    global ARCHIVE, SPELLING
    started = time.monotonic()
    ARCHIVE = pathlib.Path(argv[0])
    replace = "--replace" in argv[1:]
    target = tree.PROFILES / "harmony"
    if target.exists() and not replace:
        print("FAIL profiles/harmony/ exists. The committed data is the source of truth; "
              "re-importing loses every edit since. Pass --replace to do it anyway.")
        return 1
    errors = [f"{n}: {e}" for n, (_, e) in validate.check_tables().items() if e]
    for path in (ARCHIVE / "protocols").glob("*.json"):
        if path.name == "index.json":
            continue
        doc = json.loads(path.read_text())
        if any(f.get("toggleBit") is not None for f in (doc.get("keycodeFields") or {}).values()):
            PROTOCOLS[doc["name"]] = harmony_render.Protocol(doc)
    handwritten = load_handwritten(errors)
    if errors:
        print("\n".join(["FAIL"] + errors))
        return 1
    for folder in (target, tree.CODESETS):
        if folder.exists():
            shutil.rmtree(folder)

    device_paths = [p for p in (ARCHIVE / "devices").glob("*/*.json") if p.name != "index.json"]
    codeset_paths = list((ARCHIVE / "codesets").glob("*/*.json"))
    with Pool(os.cpu_count()) as pool:
        devices = pool.map(scan_device, device_paths, chunksize=500)
        codesets = {}
        name_counts = collections.Counter()
        for rel, real, placeholder, names in pool.imap_unordered(scan_codeset, codeset_paths, chunksize=200):
            codesets[rel] = (real, placeholder)
            name_counts.update(names)
    SPELLING = spelling_table(name_counts)
    scanned = time.monotonic()

    # Drops, then duplicates.
    drops = collections.Counter()
    replaced = {doc["meta"]["harmony"]["global_device_id"] for doc in handwritten
                if doc.get("meta", {}).get("harmony", {}).get("global_device_id") is not None}
    candidates = []
    for dev in devices:
        cs = codesets.get(dev["codeset"]) if dev["codeset"] else None
        if dev["manufacturer"] in TEST_MANUFACTURERS:
            drops["test manufacturer"] += 1
        elif dev["type"] in TEST_DEVICE_TYPES:
            drops["test device type"] += 1
        elif cs is None:
            drops["no commands (empty catalogue entry)"] += 1
        elif cs[1]:
            drops["placeholder codes only"] += 1
        elif cs[0] == 0:
            drops["no usable IR commands (radio, HID or IP only, or invalid Pronto)"] += 1
        elif not dev["model"] or not dev["manufacturer"]:
            drops["no model name"] += 1
        elif dev["gid"] in replaced:
            drops["replaced by a hand-written profile"] += 1
        else:
            candidates.append(dev)
    groups = collections.defaultdict(list)
    for dev in candidates:
        groups[(dev["manufacturer"].lower(), name_key(dev["model"]))].append(dev)
    kept = []
    for group in groups.values():
        group.sort(key=lambda d: (-codesets[d["codeset"]][0], d["gid"]))
        kept.append(group[0])
        drops["duplicate of another model's name"] += len(group) - 1

    tasks = collections.defaultdict(list)
    for dev in kept:
        tasks[dev["codeset"]].append(dev)
    tasks = sorted(tasks.items(), key=lambda t: -len(t[1]))  # big groups first

    issues, fills, failures = collections.Counter(), collections.Counter(), []
    unclean, out_count = 0, 0
    kind_fills = collections.defaultdict(collections.Counter)
    kind_counts = collections.Counter()
    with Pool(os.cpu_count()) as pool:
        for results in pool.imap_unordered(convert_group, tasks, chunksize=20):
            for r in results:
                if "errors" in r:
                    failures.append(r)
                    continue
                out_count += 1
                unclean += bool([i for i in r["issues"] if not i.startswith("hub note")])
                issues.update(r["issues"])
                fills.update(r["fill"])
                kind_counts[r["kind"]] += 1
                kind_fills[r["kind"]].update(r["fill"])

    report = {
        "devices_in": len(devices), "imported": out_count, "drops": dict(drops.most_common()),
        "validation_failures": failures[:50], "validation_failure_count": len(failures),
        "devices_not_clean": unclean, "issues": dict(issues.most_common()),
        "button_fill": {b["button"]: round(fills[b["button"]] / max(1, out_count), 3) for b in BUTTONS},
        "button_fill_by_kind": {k: {"devices": kind_counts[k], **{
            b["button"]: round(kind_fills[k][b["button"]] / kind_counts[k], 3) for b in BUTTONS}}
            for k, _ in kind_counts.most_common(6)},
        "manufacturers": len({d["manufacturer"] for d in kept}),
        "codesets": sum(1 for _ in tree.walk(tree.CODESETS)),
        "seconds": {"scan": round(scanned - started, 1), "total": round(time.monotonic() - started, 1)},
    }
    tree.write(ROOT / "build" / "import-report.json", report)
    print(json.dumps({k: v for k, v in report.items() if k != "validation_failures"}, indent=2))
    for f in failures[:10]:
        print("FAIL", f["id"], f["errors"])
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

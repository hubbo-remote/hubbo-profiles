"""Throwaway: convert a few Harmony archive devices into Hubbo profiles, to prove the format holds IR.

This is not the catalog converter. It handles what the samples need and says what it drops.
Usage (see bin/convert-sample): harmony_sample.py <archive-root> <out-dir> <devices/...json> ...
The archive is read in place and never copied.
"""

import json
import pathlib
import re
import sys

# Harmony deviceType -> kind, from kinds.json (the codes were decoded in research-archive.md).
KINDS = {code: row["id"]
         for row in json.loads((pathlib.Path(__file__).resolve().parent.parent / "kinds.json").read_text())["kinds"]
         for code in row["harmony"]}

# Spelling-only synonyms (key: lowercase alphanumerics). Applied only when the canonical name
# isn't already in the codeset; semantic variants (Exit/Back/Return, OK/Select) stay distinct.
SYNONYMS = {
    "up": "DirectionUp", "arrowup": "DirectionUp", "cursorup": "DirectionUp",
    "down": "DirectionDown", "arrowdown": "DirectionDown", "cursordown": "DirectionDown",
    "left": "DirectionLeft", "arrowleft": "DirectionLeft", "cursorleft": "DirectionLeft",
    "right": "DirectionRight", "arrowright": "DirectionRight", "cursorright": "DirectionRight",
    "ok": "OK", "playpause": "PlayPause", "mutetoggle": "Mute",
}
PUNCT_NAMES = {"-": "Dash", ".": "Dot", "+": "Plus", "*": "Star", "#": "Hash"}


def kind_of(device_type):
    return KINDS.get(device_type, "other")


def base_name(raw):
    name = " ".join(raw.split())
    if name in PUNCT_NAMES:
        return PUNCT_NAMES[name]
    key = re.sub(r"[^a-z0-9]", "", name.lower())
    if key in SYNONYMS:
        return SYNONYMS[key]
    parts = re.split(r"[^A-Za-z0-9]+", name)
    out = "".join(p[:1].upper() + p[1:] for p in parts if p)
    return out[:32] or "Command"


def normalize_names(raw_names):
    """Map each Harmony name to a unique profile name. Exact canonical names are claimed first."""
    mapping, taken = {}, set()
    ordered = sorted(raw_names, key=lambda n: (base_name(n) != n, n))
    for raw in ordered:
        name = base_name(raw)
        candidate, i = name, 2
        while candidate.lower() in taken:
            candidate, i = f"{name[:30]}{i}", i + 1
        mapping[raw] = candidate
        taken.add(candidate.lower())
    return mapping


def convert_steps(steps, names, dropped, where):
    out = []
    for step in steps or []:
        if isinstance(step, str):
            step = {"command": step}
        if "delayMs" in step:
            if step["delayMs"] > 0:
                out.append({"delay_ms": min(step["delayMs"], 60000)})
        elif "command" in step:
            if step["command"] not in names:
                dropped.append(f"{where}: command {step['command']!r} isn't in the codeset")
                return None
            s = {"command": names[step["command"]]}
            if step.get("durationMs"):
                s["hold_ms"] = min(step["durationMs"], 10000)
            out.append(s)
        else:
            dropped.append(f"{where}: unsupported step {json.dumps(step)}")
            return None
    return out[:16] or None


def toggle_protocols(archive, protocols):
    found = set()
    for name in protocols:
        path = archive / "protocols" / (name.replace(" ", "_") + ".json")
        if not path.exists():
            continue
        fields = json.loads(path.read_text()).get("keycodeFields") or {}
        if any(f.get("toggleBit") is not None for f in fields.values()):
            found.add(name)
    return found


def convert(archive, rel):
    dev = json.loads((archive / rel).read_text())
    codeset = json.loads((archive / dev["codeset"]).read_text())["commands"]
    dropped, notes = [], []

    names = normalize_names([c["name"] for c in codeset])
    commands = {}
    for c in codeset:
        if not c.get("pronto"):
            dropped.append(f"command {c['name']!r}: no pronto ({c.get('protocol')})")
            continue
        cmd = {"pronto": c["pronto"].upper()}
        if names[c["name"]] != base_name(c["name"]) or not re.fullmatch(r"[A-Za-z0-9]+", c["name"]):
            cmd["label"] = c["name"][:32]
        commands[names[c["name"]]] = cmd
    names = {raw: n for raw, n in names.items() if n in commands}

    toggles = toggle_protocols(archive, {c.get("protocol") for c in codeset})
    if toggles:
        notes.append(f"Toggle-bit protocol(s) {sorted(toggles)}: prontoToggle isn't rendered by this "
                     "sample converter, so repeated presses may be ignored.")

    t = dev.get("timing", {})
    doc = {
        "schema_version": 1,
        "id": f"harmony:{dev['globalDeviceId']}",
        "revision": 1,
        "source": "harmony",
        "manufacturer": dev["manufacturer"].strip()[:64],
        "model": (dev.get("model") or "").strip()[:64] or "Unknown",
        "kind": kind_of(dev.get("deviceType")),
        "platform": "ir",
        "commands": commands,
    }

    power = dev.get("power") or {}
    ptype = power.get("type")
    if ptype in ("discrete", "toggle"):
        parts = ("on", "off") if ptype == "discrete" else ("toggle",)
        p = {"type": ptype}
        for part in parts:
            steps = convert_steps(power.get(part), names, dropped, f"power.{part}")
            if steps is None:
                p = None
                break
            p[part] = steps
        if p is not None:
            p["on_delay_ms"] = min(t.get("powerOnDelay", 0), 60000)
            if ptype == "discrete" and p["on"] == p["off"]:
                notes.append("The archive's power on and off steps are the same, so off likely "
                             "doesn't turn the device off.")
            doc["power"] = p
        else:
            dropped.append("power: incomplete after dropping steps")
    if power.get("onReset"):
        dropped.append("power.onReset (state steps) isn't in the format")

    doc["timing"] = {
        "key_delay_ms": min(t.get("interKeyDelay", 0), 5000),
        "input_delay_ms": min(t.get("inputDelay", 0), 60000),
        "ir_repeats": min(t.get("pressMinRepeats", 1), 20),
    }

    inputs = []
    for entry in (dev.get("inputs") or {}).get("list", []):
        steps = convert_steps(entry.get("commands"), names, dropped, f"input {entry['name']!r}")
        if steps:
            inputs.append({"name": entry["name"].strip()[:32], "steps": steps})
        elif not entry.get("commands"):
            dropped.append(f"input {entry['name']!r}: no steps")
    if inputs:
        doc["inputs"] = inputs[:64]

    tuning = dev.get("channelTuning")
    if tuning:
        if all(str(d) in names for d in range(10)):
            ch = {}
            if tuning.get("fixedDigits"):
                ch["digits"] = tuning["fixedDigits"]
            for part in ("start", "finish"):
                steps = convert_steps(tuning.get(part), names, dropped, f"channelTuning.{part}")
                if steps and len(steps) == 1 and "command" in steps[0] and len(steps[0]) == 1:
                    ch[part] = steps[0]["command"]
                elif steps:
                    dropped.append(f"channelTuning.{part}: more than one step")
            doc["channels"] = ch
        else:
            dropped.append("channelTuning: the codeset has no digit commands")

    dropped.append("timing.interDeviceDelay, connectedAppPowerOnDelay and the prontoRepeat/keycode/protocol "
                   "fields aren't in the format")
    doc["meta"] = {
        "confidence": "medium",
        "sources": [f"Harmony archive (CC0): {rel}, {dev['codeset']}"],
        "notes": notes + [f"Dropped in conversion: {d}" for d in dropped],
        "harmony": {
            "global_device_id": dev["globalDeviceId"],
            "device_type": dev.get("deviceType"),
            "codeset": pathlib.Path(dev["codeset"]).stem,
        },
    }
    return doc


def main(argv):
    archive, out = pathlib.Path(argv[0]), pathlib.Path(argv[1])
    for rel in argv[2:]:
        doc = convert(archive, rel)
        slug = re.sub(r"[^a-z0-9]+", "-", f"{doc['manufacturer']} {doc['model']}".lower()).strip("-")
        path = out / f"{slug}.json"
        path.write_text(json.dumps(doc, indent=2) + "\n")
        print(f"{rel} -> {path.name}: {len(doc['commands'])} commands")


if __name__ == "__main__":
    main(sys.argv[1:])

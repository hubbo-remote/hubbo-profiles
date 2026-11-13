"""Render a Harmony keycode to Pronto from Logitech's protocol definition.

The converter uses this only for toggle-bit protocols: it renders each code with the toggle bit
at 0, checks that the result is byte-identical to the archive's Pronto, and only then renders the
bit-1 copy as `pronto_toggle`. The algorithm is the archive README's "Rendering a keycode yourself".
"""

import re

KEYCODE = re.compile(r"G:(.*):\((.*?)\)\((.*?)\)\((.*?)\):(.*)")


class Protocol:
    def __init__(self, doc):
        definition = doc["definition"]
        self.name = doc["name"]
        self.carrier = definition["CarrierFrequency"]
        self.segments = {}
        for seg in (definition.get("IRSegments") or []) + (definition.get("CodeSegments") or []):
            self.segments[self._segment_id(seg["Name"])] = seg

    def _segment_id(self, name):
        if name == self.name:
            return "0"
        if "KeyCode" in name:
            return name.split("KeyCode", 1)[1]
        if name.startswith(self.name + " "):
            return name[len(self.name) + 1:]
        return name

    def render(self, keycode, toggle):
        """Pronto for `keycode` with every toggle bit set to `toggle`. Raises on a bad keycode."""
        match = KEYCODE.fullmatch(keycode)
        if not match:
            raise ValueError("unparsable keycode")
        start, repeat, finish = (self._group(match.group(i), toggle) for i in (2, 3, 4))
        if start or finish:
            once, again = _merge(start + repeat + finish), _merge(repeat)
        else:
            once, again = _merge(repeat), []
        return _pronto(once, again, self.carrier)

    def _group(self, group, toggle):
        out = []
        for token in filter(None, group.split("_")):
            if len(token) > 1 and token[1] == "x":
                seg_id, value = token[0], token[2:]
            else:
                seg_id, value = token, None
            out += _play(self.segments[seg_id], value, toggle)
        return out


def _play(seg, value, toggle):
    out = [(a["Type"], a["Value"]) for a in seg.get("Header") or []]
    payload = seg.get("Payload")
    if payload:
        n = payload["NumberOfBits"]
        encodings = {e["BitType"]: e["Atoms"] for e in payload["Encodings"]}
        if payload["EncodingType"] in (0, 1):
            symbols = [int(b) for b in bin(int(value or "0", 16))[2:].zfill(n)[-n:]]
        else:  # quad: one symbol per hex digit
            symbols = ([0] * n + [int(c, 16) for c in value or ""])[-n:]
        if payload.get("ToggleBit") is not None:
            symbols[payload["ToggleBit"]] = toggle
        for s in symbols:
            out += [(a["Type"], a["Value"]) for a in encodings[s]]
    out += [(a["Type"], a["Value"]) for a in seg.get("Trailer") or []]
    gap = (seg.get("TotalLength") or 0) - sum(v for _, v in out)
    if gap > 0:
        out.append((0, gap))
    return out


def _merge(atoms):
    """Join adjacent runs at the same level and drop any leading space."""
    out = []
    for level, us in atoms:
        if us <= 0:
            continue
        if out and out[-1][0] == level:
            out[-1] = (level, out[-1][1] + us)
        else:
            out.append((level, us))
    while out and out[0][0] == 0:
        out.pop(0)
    return out


def _pronto(once, again, carrier):
    word = round(1e6 / (carrier * 0.241246))
    period = word * 0.241246  # the archive rounds durations against the Pronto period

    def units(seq):
        if seq and seq[-1][0] == 1:
            seq = seq + [(0, 0)]
        return [max(1, round(us / period)) if us else 0 for _, us in seq]

    o, r = units(once), units(again)
    return " ".join(f"{w:04X}" for w in [0, word, len(o) // 2, len(r) // 2] + o + r)

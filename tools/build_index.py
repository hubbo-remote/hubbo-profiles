"""Build the catalog's search index from the profiles in this repository.

Usage (inside the tools image; see tools/bin/index): build_index.py <out-dir>   (default build/index)

  manufacturers.json   [{n, s, c, k}]: name, slug, device count, device counts by kind
  m/<slug>.json        one manufacturer's devices, [{id, m, k, p, n}]: id, model, kind, platform
                       and command count, sorted by model. A profile's path comes from its id
                       (profiles/README.md)
  catalog.json         counts and the build date

The index is generated, never committed: it's derived from the profiles, so a build makes it.
"""

import collections
import datetime
import functools
import json
import os
import pathlib
import re
import shutil
import sys
from multiprocessing import Pool

import tree


@functools.cache  # per worker; ~53k codesets, ids arrive in random order
def command_count(cs_id):
    return len(tree.load_codeset_file(cs_id))


def entry(path):
    raw = json.loads(path.read_text())
    n = command_count(raw["codeset"]) if "codeset" in raw else len(raw["commands"])
    return raw["manufacturer"], {"id": raw["id"], "m": raw["model"], "k": raw["kind"], "p": raw["platform"],
                                 "n": n}


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def main(argv):
    out = pathlib.Path(argv[0]) if argv else tree.ROOT / "build" / "index"
    if out.exists():
        shutil.rmtree(out)
    (out / "m").mkdir(parents=True)
    paths = tree.walk(tree.PROFILES)
    with Pool(os.cpu_count()) as pool:
        rows = pool.map(entry, paths, chunksize=1000)
    index = collections.defaultdict(list)
    for manufacturer, e in rows:
        index[manufacturer].append(e)

    manufacturers, slugs = [], set()
    for name in sorted(index):  # by name, so a slug never moves between rebuilds
        base = slugify(name) or "unnamed"
        slug, i = base, 2
        while slug in slugs:
            slug, i = f"{base}-{i}", i + 1
        slugs.add(slug)
        devices = sorted(index[name], key=lambda e: (e["m"].casefold(), e["id"]))
        (out / "m" / f"{slug}.json").write_text(json.dumps(devices, separators=(",", ":"), ensure_ascii=False))
        kinds = collections.Counter(e["k"] for e in devices)
        manufacturers.append({"n": name, "s": slug, "c": len(devices), "k": dict(sorted(kinds.items()))})
    manufacturers.sort(key=lambda m: (m["n"].casefold(), m["s"]))
    (out / "manufacturers.json").write_text(json.dumps(manufacturers, separators=(",", ":"), ensure_ascii=False))
    catalog = {"schema_version": 1, "built": datetime.date.today().isoformat(),
               "counts": {"manufacturers": len(manufacturers), "profiles": len(rows),
                          "codesets": sum(1 for _ in tree.walk(tree.CODESETS))}}
    tree.write(out / "catalog.json", catalog)
    print(json.dumps(catalog["counts"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

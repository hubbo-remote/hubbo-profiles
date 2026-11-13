"""Rewrite codesets and split profiles in the repository's file format (tree.dumps): 2-space indent,
UTF-8, trailing newline. Content and key order are kept, so no revision changes. Hand-written whole
profiles (no `codeset`) keep their own layout.

Usage (inside the tools image; see tools/bin/format): format.py [paths]   (default: the whole tree)
"""

import json
import os
import pathlib
import sys
from multiprocessing import Pool

import tree


def format_file(path):
    text = path.read_bytes().decode()
    doc = json.loads(text)
    is_codeset = path.resolve().is_relative_to(tree.CODESETS.resolve())
    if not (is_codeset or "codeset" in doc) or text == tree.dumps(doc):
        return 0
    tree.write(path, doc)
    return 1


def main(argv):
    targets = [tree.ROOT / a for a in argv] or [tree.PROFILES, tree.CODESETS]
    files = [f for t in targets for f in (tree.walk(t) if t.is_dir() else [t])]
    with Pool(os.cpu_count()) as pool:
        changed = sum(pool.map(format_file, files, chunksize=2000))
    print(f"{changed} of {len(files)} files reformatted")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

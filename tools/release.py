"""Make the bulk-download archive: the standard and all its data, as one tarball.

Usage (inside the tools image; see tools/bin/release): release.py <name>
Writes build/release/<name>.tar.gz holding the committed tree (git archive HEAD: README.md,
LICENSE, CONTRIBUTING.md, docs/ (spec, schemas, changelog), profiles/, codesets/) plus a freshly
built index/. Profiles stay in storage form; codesets/README.md says how to join them.
Only committed data goes in, so run it on a clean, tagged commit.
"""

import subprocess
import sys
import tarfile

import build_index
import tree

INCLUDE = ["README.md", "LICENSE", "CONTRIBUTING.md", "docs", "profiles", "codesets"]


def tree_dirty():
    """Released paths that differ from HEAD, untracked ones included."""
    def git(*args):
        return subprocess.run(["git", "-C", str(tree.ROOT), *args], check=True, capture_output=True,
                              text=True).stdout.split()
    return git("diff", "--name-only", "HEAD", "--", *INCLUDE) + git("ls-files", "--others", "--exclude-standard", "--", *INCLUDE)


def main(argv):
    name = argv[0]
    dirty = tree_dirty()
    if dirty:
        print(f"FAIL uncommitted changes (e.g. {dirty[0]}); the index is built from the working tree and the "
              "archive from HEAD, so commit or stash first")
        return 1
    out = tree.ROOT / "build" / "release"
    out.mkdir(parents=True, exist_ok=True)
    index = out / "index"
    build_index.main([str(index)])
    path = out / f"{name}.tar.gz"
    git = subprocess.Popen(["git", "-C", str(tree.ROOT), "archive", "--format=tar", f"--prefix={name}/",
                            "HEAD", *INCLUDE], stdout=subprocess.PIPE)
    with tarfile.open(path, "w:gz", compresslevel=6) as dst:
        with tarfile.open(fileobj=git.stdout, mode="r|") as src:  # streamed, never held in memory
            for member in src:
                dst.addfile(member, src.extractfile(member) if member.isfile() else None)
        for f in sorted(index.rglob("*")):
            if f.is_file():
                dst.add(f, arcname=f"{name}/index/{f.relative_to(index)}")
    if git.wait():
        raise SystemExit("git archive failed")
    print(f"{path.relative_to(tree.ROOT)}: {path.stat().st_size} B")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

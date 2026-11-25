"""Print one device's complete profile: its stored file joined with its codeset.

Usage (inside the tools image; see tools/bin/profile): profile.py <id>
"""

import json
import sys

import tree


def main(args):
    if len(args) != 1:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    try:
        path = tree.profile_path(args[0])
    except ValueError:
        path = None
    if path is None or not path.exists():
        print(f"no profile {args[0]}", file=sys.stderr)
        return 1
    sys.stdout.write(tree.dumps(tree.join(json.loads(path.read_text()), tree.load_codeset_file)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""
Compare two saved normalized JSON responses and show a unified diff.

Usage:
  python tools\compare_responses.py before.json after.json

This prints a quick equality summary and, if different, a unified diff of the
pretty-printed JSON files.
"""

import sys
import json
import difflib


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def pretty_json(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)


def main():
    if len(sys.argv) < 3:
        print("Usage: python tools\\compare_responses.py before.json after.json")
        sys.exit(1)

    a_path = sys.argv[1]
    b_path = sys.argv[2]

    a = load_json(a_path)
    b = load_json(b_path)

    a_pretty = pretty_json(a).splitlines(keepends=True)
    b_pretty = pretty_json(b).splitlines(keepends=True)

    if a == b:
        print("Responses are IDENTICAL.")
        sys.exit(0)

    print("Responses DIFFER. Showing unified diff:\n")
    diff = difflib.unified_diff(a_pretty, b_pretty, fromfile=a_path, tofile=b_path)
    sys.stdout.writelines(diff)
    sys.exit(2)


if __name__ == "__main__":
    main()

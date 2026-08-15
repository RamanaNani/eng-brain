#!/usr/bin/env python3
"""Refuse to hand an agent a file it cannot safely edit.

A slice that owns a 5,000-line file burns two or three agent attempts before
anyone notices the *file*, not the agent, was the problem. This gate turns that
discovery into a design decision made before any worktree exists: either the
file gets split, or the slice declares a surgical strategy and the brief names
the exact symbols to touch.

Usage:
    tractable.py <slices.json> <repo_root>
    tractable.py --selfcheck
"""
import glob
import json
import os
import sys

WARN_LINES = 800
FAIL_LINES = 1500


def line_count(path):
    """Lines in the file, or None when it cannot be read.

    Returning 0 for an unreadable file declared a 3,000-line mode-000 file
    tractable and printed TRACTABILITY: OK. A size this gate could not measure
    is not a small size.
    """
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return None


def main(manifest_path, root):
    manifest = json.load(open(manifest_path))
    os.chdir(root)
    failed = False

    for slice_ in manifest["slices"]:
        # "surgical" is an explicit opt-out: the author has accepted the file is
        # large and the brief names the regions to touch. Not a free pass —
        # concepts.py and the brief's Interfaces section still apply.
        surgical = slice_.get("edit_strategy") == "surgical"
        for pattern in slice_["owns"]:
            for path in sorted(glob.glob(pattern, recursive=True)):
                if not os.path.isfile(path):
                    continue
                n = line_count(path)
                if n is None:
                    # Not exempted by "surgical": that setting asserts the author
                    # read the file and named the regions to touch, which nobody
                    # can have done for a file that will not open.
                    failed = True
                    print(
                        f"UNREADABLE {slice_['id']} {path}: cannot be opened, so its size "
                        f"is unknown\n"
                        f"         fix the permissions or drop it from owns — an unmeasured "
                        f"file is not a small one"
                    )
                elif n >= FAIL_LINES and not surgical:
                    failed = True
                    print(
                        f"TOO BIG  {slice_['id']} {path}: {n} lines (>= {FAIL_LINES})\n"
                        f"         split the file, or set \"edit_strategy\": \"surgical\" "
                        f"and name the exact functions in the brief"
                    )
                elif n >= WARN_LINES:
                    print(
                        f"  large  {slice_['id']} {path}: {n} lines — the brief must name "
                        f"the exact functions or regions to touch"
                    )

    print("TRACTABILITY: FAIL" if failed else "TRACTABILITY: OK")
    return 1 if failed else 0


def selfcheck():
    import io
    import tempfile
    from contextlib import redirect_stdout
    from pathlib import Path

    d = tempfile.mkdtemp()
    manifest = Path(d, "slices.json")

    # Every fixture below is an ABSOLUTE line count, never FAIL_LINES + n. Sizing
    # them off the constants made them move with the constants, so setting
    # FAIL_LINES to 999999 — switching the gate off outright — still passed this
    # selfcheck. A threshold nothing pins is not a threshold.
    for name, n in (("at_fail.ts", 1500), ("under_fail.ts", 1499),
                    ("at_warn.ts", 800), ("under_warn.ts", 799)):
        Path(d, name).write_text("x\n" * n)
    moved = ("thresholds moved: WARN_LINES/FAIL_LINES are pinned at 800/1500 by the "
             "line counts of these fixtures. If you moved one on purpose, resize them.")

    def run(slices):
        manifest.write_text(json.dumps({"slices": slices}))
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(str(manifest), d)
        out = buf.getvalue()
        print(out, end="")
        return code, out

    code, out = run([{"id": "01", "owns": ["at_fail.ts"]}])
    assert (code, "TOO BIG" in out) == (1, True), f"exactly 1500 lines must fail. {moved}"

    code, out = run([{"id": "01", "owns": ["under_fail.ts"]}])
    assert (code, "TOO BIG" in out) == (0, False), f"1499 lines must not fail. {moved}"
    assert "large" in out, f"1499 lines is still past the warn line. {moved}"

    code, out = run([{"id": "01", "owns": ["at_warn.ts"]}])
    assert (code, "large" in out) == (0, True), f"exactly 800 lines must warn. {moved}"

    code, out = run([{"id": "01", "owns": ["under_warn.ts"]}])
    assert (code, "large" in out) == (0, False), f"799 lines must be silent. {moved}"

    code, out = run([{"id": "01", "owns": ["at_fail.ts"], "edit_strategy": "surgical"}])
    assert code == 0, "an explicit surgical strategy must pass"

    code, out = run([
        {"id": "01", "owns": ["at_fail.ts"]},
        {"id": "02", "owns": ["under_warn.ts"]},
    ])
    assert code == 1, "one oversized file must fail the whole manifest"

    # A glob matches directories too, and a directory has no line count. Without
    # the isfile guard this raised IsADirectoryError mid-run: a gate that dies on
    # a legal manifest teaches the operator to stop running it.
    Path(d, "sub").mkdir()
    code, out = run([{"id": "01", "owns": ["*"]}])
    assert (code, "TOO BIG" in out) == (1, True), \
        "a glob spanning a directory must skip it and still judge the files"

    # A file the gate cannot read has an unknown size, and line_count returning 0
    # for it declared 3,000 lines tractable at exit 0 — the silence-is-a-pass
    # failure this module's header names. Refuse it instead, surgical or not.
    unreadable = Path(d, "locked.ts")
    unreadable.write_text("x\n" * 3000)
    unreadable.chmod(0o000)
    try:
        assert line_count(str(unreadable)) is None, \
            "an unreadable file has no line count (are you running as root?)"
        code, out = run([{"id": "01", "owns": ["locked.ts"]}])
        assert (code, "UNREADABLE" in out) == (1, True), "an unreadable file must fail closed"
        code, out = run([{"id": "01", "owns": ["locked.ts"], "edit_strategy": "surgical"}])
        assert code == 1, \
            "surgical asserts the author read the file, which is impossible here"
        # The directory skip is the neighbouring case and must not be swept in:
        # a directory is not unreadable, it is not a file at all.
        code, out = run([{"id": "01", "owns": ["sub"]}])
        assert (code, out.strip()) == (0, "TRACTABILITY: OK"), \
            "a directory is skipped before it is ever opened"
    finally:
        unreadable.chmod(0o644)

    print("selfcheck OK")
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--selfcheck":
        sys.exit(selfcheck())
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))

#!/usr/bin/env python3
"""Prove no two slices can write the same file.

Two slices whose globs match the same file WILL collide in /fleet, and parallel
agents cannot be careful about each other. This used to be an untested heredoc
written to /tmp from inside slice/SKILL.md, which meant nobody could run it on
its own and nothing proved it still worked.

It makes two comparisons, because the obvious one is blind exactly when it
matters most:

  resolved files   intersect the files each slice's globs match on disk today
  declared globs   compare the patterns to each other, disk or no disk

The second exists because the first proves NOTHING on a greenfield repo. Every
glob matches zero files, no intersection is possible, and the gate printed
"OWNERSHIP: OK" having verified nothing at all. Two slices both owning
`src/api/**` collide on the day that directory fills up, and by then they are
already running in parallel worktrees.

Usage:
    owns.py <slices.json> <repo_root>
    owns.py --selfcheck
"""
import fnmatch
import glob
import itertools
import json
import os
import sys


def resolve(patterns, root):
    """The existing files a slice's globs match, relative to root."""
    cwd = os.getcwd()
    os.chdir(root)
    try:
        files = set()
        for pattern in patterns:
            files |= {os.path.normpath(p) for p in glob.glob(pattern, recursive=True)
                      if os.path.isfile(p)}
        return files
    finally:
        os.chdir(cwd)


def _dir_prefix(pattern):
    """The literal directory prefix of a glob: 'src/api/' for 'src/api/**/*.ts'."""
    head = pattern
    for wildcard in "*?[":
        head = head.split(wildcard)[0]
    return head[: head.rfind("/") + 1]


def patterns_collide(a, b):
    """Can these two globs ever match the same path, on any filesystem?"""
    a, b = os.path.normpath(a), os.path.normpath(b)
    if a == b:
        return True
    # Either pattern may be literal enough for the other to match it directly:
    # 'src/api/**' matches the string 'src/api/routes/*.ts'.
    if fnmatch.fnmatch(a, b) or fnmatch.fnmatch(b, a):
        return True
    # Only ** crosses a directory boundary, so only a ** pattern can swallow
    # another slice's subtree. 'src/*.ts' does NOT reach into src/ui/.
    pa, pb = _dir_prefix(a), _dir_prefix(b)
    return ("**" in a and pb.startswith(pa)) or ("**" in b and pa.startswith(pb))


def bare_dirs(patterns, root):
    """owns entries naming a directory instead of the files inside it.

    'src/api' is invisible to both halves of this gate: it resolves to zero files
    because a directory is not a file, and it collides with nothing textually
    because normpath strips the trailing slash and there is no wildcard for the
    ** rule to see. Two slices owning 'src/api' and 'src/api/**' therefore passed
    this gate — reported as a clean new-file slice — while both agents edited the
    same tree. Refuse the input instead of guessing what it meant.
    """
    out = []
    for pattern in patterns:
        if any(c in pattern for c in "*?["):
            continue
        if pattern.endswith("/") or os.path.isdir(os.path.join(root, pattern)):
            out.append(pattern)
    return out


def main(manifest_path, root):
    slices = json.load(open(manifest_path))["slices"]

    resolved = {}
    for s in slices:
        resolved[s["id"]] = resolve(s["owns"], root)
        print(f"  slice {s['id']} {s.get('name', '')}: {len(resolved[s['id']])} existing files")

    bad = False
    for s in slices:
        for pattern in bare_dirs(s["owns"], root):
            bad = True
            clean = pattern.rstrip("/")
            print(f"BARE DIRECTORY {s['id']}: {pattern!r} names a directory, not files. "
                  f"Write {clean + '/**'!r}\n"
                  f"          — as written it matches zero files and overlaps no other "
                  f"slice's pattern, so this gate cannot prove anything about it either way.")
    for a, b in itertools.combinations(slices, 2):
        overlap = resolved[a["id"]] & resolved[b["id"]]
        if overlap:
            bad = True
            print(f"COLLISION {a['id']} <-> {b['id']}: {sorted(overlap)[:8]}")
            continue  # the files already prove it; naming the patterns adds nothing
        pairs = sorted({f"{pa} ~ {pb}" for pa in a["owns"] for pb in b["owns"]
                        if patterns_collide(pa, pb)})
        if pairs:
            bad = True
            print(f"COLLISION {a['id']} <-> {b['id']}: {pairs[:8]}")

    for s in slices:
        if not resolved[s["id"]]:
            print(f"  note: slice {s['id']} matches no existing files (new-file slice — "
                  f"its globs were still compared against every other slice's)")

    if bad:
        print("  fix: re-cut the slices. Do not proceed with a known collision and do not")
        print("       'just be careful in fleet' — parallel agents cannot see each other.")
    print("OWNERSHIP: FAIL" if bad else "OWNERSHIP: OK")
    return 1 if bad else 0


def selfcheck():
    import io
    import tempfile
    from contextlib import redirect_stdout
    from pathlib import Path

    d = tempfile.mkdtemp()
    Path(d, "src", "api").mkdir(parents=True)
    Path(d, "src", "ui").mkdir(parents=True)
    Path(d, "src", "api", "routes.ts").write_text("export const routes = [];\n")
    Path(d, "src", "ui", "panel.tsx").write_text("export const Panel = () => null;\n")
    empty = tempfile.mkdtemp()  # nothing on disk: every glob resolves to zero files

    def run(slices, root=d):
        """Run the gate, returning (exit code, last line of stdout)."""
        manifest = Path(root, "slices.json")
        manifest.write_text(json.dumps({"slices": slices}))
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(str(manifest), root)
        out = buf.getvalue()
        print(out, end="")
        return code, out.strip().splitlines()[-1]

    # --- resolved-file intersection: the behaviour that already worked ---
    code, last = run([
        {"id": "01", "name": "api", "owns": ["src/api/*.ts"]},
        {"id": "02", "name": "ui", "owns": ["src/**/*.ts"]},
    ])
    assert (code, last) == (1, "OWNERSHIP: FAIL"), "two slices on one existing file must fail"

    code, last = run([
        {"id": "01", "name": "api", "owns": ["src/api/*.ts"]},
        {"id": "02", "name": "ui", "owns": ["src/ui/*.tsx"]},
    ])
    assert (code, last) == (0, "OWNERSHIP: OK"), "disjoint existing files must pass"

    # The case above is ALSO caught by the pattern check ('src/**/*.ts' swallows
    # 'src/api/'), so deleting the file intersection entirely still passed this
    # selfcheck. This one it cannot: 'user*.ts' and '*sync.ts' share no text and
    # neither contains **, so nothing but the resolved files knows they both land
    # on src/models/usersync.ts.
    assert not patterns_collide("src/models/user*.ts", "src/models/*sync.ts"), \
        "this fixture only proves anything while those two patterns do NOT overlap textually"
    Path(d, "src", "models").mkdir(parents=True)
    Path(d, "src", "models", "usersync.ts").write_text("export const sync = 1;\n")
    code, last = run([
        {"id": "01", "name": "user", "owns": ["src/models/user*.ts"]},
        {"id": "02", "name": "sync", "owns": ["src/models/*sync.ts"]},
    ])
    assert (code, last) == (1, "OWNERSHIP: FAIL"), \
        "globs that overlap only on disk must fail — the file intersection is the only witness"

    # --- the greenfield vacuity this script exists to close ---
    # Every case below runs against an empty repo, where the file intersection
    # above is structurally incapable of finding anything.
    code, last = run([
        {"id": "01", "name": "routes", "owns": ["src/api/**"]},
        {"id": "02", "name": "handlers", "owns": ["src/api/**"]},
    ], empty)
    assert (code, last) == (1, "OWNERSHIP: FAIL"), \
        "identical globs must collide even with zero files on disk"

    code, last = run([
        {"id": "01", "name": "everything", "owns": ["src/**"]},
        {"id": "02", "name": "ui", "owns": ["src/ui/**"]},
    ], empty)
    assert (code, last) == (1, "OWNERSHIP: FAIL"), "a ** parent must collide with its subtree"

    code, last = run([
        {"id": "01", "name": "api", "owns": ["src/api/**"]},
        {"id": "02", "name": "ui", "owns": ["src/ui/**"]},
    ], empty)
    assert (code, last) == (0, "OWNERSHIP: OK"), "sibling subtrees must not collide"

    # A single * does not cross a directory boundary, so this is not a collision.
    code, last = run([
        {"id": "01", "name": "top", "owns": ["src/*.ts"]},
        {"id": "02", "name": "ui", "owns": ["src/ui/**"]},
    ], empty)
    assert (code, last) == (0, "OWNERSHIP: OK"), "'src/*.ts' must not reach into src/ui/"

    code, last = run([
        {"id": "01", "name": "db", "owns": ["db/migrations/**", "src/models/sync*.ts"]},
        {"id": "02", "name": "api", "owns": ["src/api/**", "src/models/user.ts"]},
    ], empty)
    assert (code, last) == (0, "OWNERSHIP: OK"), "a realistic disjoint cut must pass"

    # A bare directory is refused rather than silently passed. Before this check,
    # these two slices printed "OWNERSHIP: OK" and called 01 a new-file slice.
    code, last = run([
        {"id": "01", "name": "routes", "owns": ["src/api"]},
        {"id": "02", "name": "handlers", "owns": ["src/api/**"]},
    ])
    assert (code, last) == (1, "OWNERSHIP: FAIL"), \
        "an owns entry naming an existing directory must be refused, not passed as zero files"

    # Greenfield: nothing is on disk, so only the trailing slash marks a directory.
    code, last = run([{"id": "01", "name": "a", "owns": ["src/api/"]}], empty)
    assert (code, last) == (1, "OWNERSHIP: FAIL"), "a trailing slash means a directory"
    code, last = run([{"id": "01", "name": "a", "owns": ["src/api/routes.ts"]}], empty)
    assert (code, last) == (0, "OWNERSHIP: OK"), \
        "an extensionless-looking literal that is not a directory on disk must still pass"
    code, last = run([{"id": "01", "name": "a", "owns": ["db/migrations/**/"]}], empty)
    assert (code, last) == (0, "OWNERSHIP: OK"), \
        "a real glob written with a trailing slash is a glob, not a bare directory"

    # --- one case per rule in patterns_collide, each decidable by that rule alone ---
    # fnmatch reads '[ab]' as a character class, not as five literal characters, so
    # it does not match the identical pattern. Only the equality test catches this.
    code, last = run([
        {"id": "01", "name": "a", "owns": ["src/api/[ab].ts"]},
        {"id": "02", "name": "b", "owns": ["src/api/[ab].ts"]},
    ], empty)
    assert (code, last) == (1, "OWNERSHIP: FAIL"), \
        "two identical character-class globs must collide"

    # A literal path inside another slice's glob. Only fnmatch sees it, and only in
    # one direction — so the declaration order must not decide the verdict.
    for first, second in (("src/api/routes.ts", "src/api/*.ts"),
                          ("src/api/*.ts", "src/api/routes.ts")):
        code, last = run([{"id": "01", "name": "one", "owns": [first]},
                          {"id": "02", "name": "two", "owns": [second]}], empty)
        assert (code, last) == (1, "OWNERSHIP: FAIL"), \
            f"a literal file inside another slice's glob must collide: {first} ~ {second}"

    # A ** slice owns its whole subtree even where the extensions cannot overlap:
    # the next .ts file added under src/ui/ belongs to two slices. fnmatch cannot
    # see this (.tsx never matches *.ts), so only the ** rule can — in both
    # directions, and only if _dir_prefix strips the wildcard off 'src/**/*.ts'.
    for first, second in (("src/**/*.ts", "src/ui/*.tsx"),
                          ("src/ui/*.tsx", "src/**/*.ts")):
        code, last = run([{"id": "01", "name": "one", "owns": [first]},
                          {"id": "02", "name": "two", "owns": [second]}], empty)
        assert (code, last) == (1, "OWNERSHIP: FAIL"), \
            f"a ** slice owns the subtree it spans: {first} ~ {second}"

    print("selfcheck OK")
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--selfcheck":
        sys.exit(selfcheck())
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))

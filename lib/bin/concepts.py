#!/usr/bin/env python3
"""Exclusive file ownership is not exclusive concept ownership.

check_owns.py proves no two slices write the same file. Necessary, not
sufficient. A slice can own every file it writes and still break the build,
because the type it widens has three other definitions in files it does not
own — and the type checker sees all four.

This is the four-copy bug: an attachment-kind union defined in a Python
allowlist, a TypeScript literal union, a schema, and a component prop. The slice
owned two of them. Widening those two broke tsc in the other two.

Each slice declares the concepts it will change:

    "concepts": ["CatalystMentionKind", "ATTACHMENT_KINDS"]

This gate finds every definition site for each concept, across every repo in the
feature, and fails if one lives outside the declaring slice's `owns`.

The gate can only check what a slice declares, so "declared nothing" must not be
allowed to look like "checked and clean". A slice with no cross-slice concepts
says so with an empty list:

    "concepts": []

A slice with no "concepts" key at all has not answered the question, and the run
ends UNVERIFIED (exit 3), not OK.

Usage:
    concepts.py <slices.json> <repo_root> [additional_repo_root ...]
    concepts.py --selfcheck

Exit 0 = OK, 1 = FAIL, 2 = wrong usage, 3 = UNVERIFIED (a slice never declared).
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys

SKIP_DIRS = (
    "node_modules", ".git", "dist", "build", ".next", "__pycache__", ".venv",
    # Worktrees are full copies of the repo: counting them would report the same
    # definition N+1 times. Docs mention concepts constantly without defining them.
    ".worktrees", "worktrees", "docs",
)

# A definition, not a mention. Covers TS/JS, Python, Go, Rust, Kotlin.
DEF_TEMPLATE = (
    r"(?:type|interface|enum|class|const|let|var|def|struct|val|fun|func)\s+{sym}\b"
    r"|^\s*{sym}\s*(?::[^=]*)?="
    r"|^\s*[\"']{sym}[\"']\s*:"
)


def candidate_files(symbol, roots):
    """Cheap wide filter: every file mentioning the bare word at all.

    A whole-word literal search is near-instant even on a large monorepo. The
    expensive definition regex then runs in Python over this small candidate
    set, instead of the regex engine backtracking across every file in the tree.
    """
    # rg is often a shell function or alias rather than a real binary (Claude Code
    # installs one). subprocess does not see those, so resolve it explicitly and
    # fall back to a *pruned* grep — an unpruned grep -r walks node_modules and
    # never returns on a monorepo.
    rg_bin = shutil.which("rg")
    if rg_bin:
        globs = []
        for d in SKIP_DIRS:
            globs += ["--glob", f"!**/{d}/**"]
        cmd_head = [rg_bin, "-l", "-w", "--fixed-strings", "--no-messages", *globs]
    else:
        cmd_head = ["grep", "-rlwF"] + [f"--exclude-dir={d}" for d in SKIP_DIRS]

    found = set()
    for root in roots:
        try:
            proc = subprocess.run(
                [*cmd_head, symbol, root], capture_output=True, text=True, timeout=90,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            print(f"  warn  search failed or timed out under {root}", file=sys.stderr)
            continue
        for line in proc.stdout.splitlines():
            if line and not any(f"/{d}/" in line for d in SKIP_DIRS):
                found.add(os.path.realpath(line))
    return found


def definition_files(symbol, roots):
    """Every file under roots that *defines* symbol, not merely mentions it."""
    rx = re.compile(DEF_TEMPLATE.format(sym=re.escape(symbol)))
    found = set()
    for path in candidate_files(symbol, roots):
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    if rx.search(line):
                        found.add(path)
                        break
        except OSError:
            continue
    return found


def owned_files(slice_, root):
    owned = set()
    cwd = os.getcwd()
    os.chdir(root)
    try:
        for pattern in slice_["owns"]:
            for path in glob.glob(pattern, recursive=True):
                if os.path.isfile(path):
                    owned.add(os.path.realpath(path))
    finally:
        os.chdir(cwd)
    return owned


def main(manifest_path, roots):
    manifest = json.load(open(manifest_path))
    primary = roots[0]
    failed = False
    undeclared = []

    for slice_ in manifest["slices"]:
        # An absent key is not an empty list. The four-copy bug this gate exists
        # to prevent was only ever prevented for authors who already remembered
        # the risk, because a manifest with no "concepts" key printed SKIPPED and
        # exited 0 — the gate opting itself out, silently, on exactly the slices
        # nobody had thought about.
        if "concepts" not in slice_:
            undeclared.append(slice_["id"])
            print(f"UNVERIFIED  {slice_['id']}: no \"concepts\" key in the manifest")
            print(
                "    this slice never answered the question, so nothing was checked. Add "
                "the\n    shared types, enums or allowlists it widens — or \"concepts\": [] "
                "to record\n    on purpose that it shares none."
            )
            continue
        concepts = slice_["concepts"]
        if not concepts:
            print(f"  ok  {slice_['id']}: \"concepts\": [] — author recorded no shared concepts")
            continue
        owned = owned_files(slice_, primary)
        for concept in concepts:
            sites = definition_files(concept, roots)
            outside = sorted(sites - owned)
            inside = len(sites) - len(outside)
            if not sites:
                # Zero definition sites used to print "0 site(s), all owned" — a pass
                # that proved nothing. A misspelled concept looks exactly like a
                # perfectly-owned one. Silence is never a pass.
                failed = True
                print(f"UNVERIFIED  {slice_['id']} \"{concept}\"")
                print(f"    no definition site anywhere under: {', '.join(roots)}")
                print(
                    "    this gate proved nothing. Either the name is misspelled or cased "
                    "differently\n    than the source, or the concept does not exist yet — and a "
                    "concept with no\n    definition cannot be checked for a second one. Fix the "
                    "spelling, or drop it\n    from \"concepts\" until the slice that creates it "
                    "has landed."
                )
            elif outside:
                failed = True
                print(f"UNOWNED DEFINITION  {slice_['id']} \"{concept}\"")
                print(f"    owns {inside} definition site(s); {len(outside)} live elsewhere:")
                for path in outside:
                    print(f"      {path}")
                print(
                    "    fix: widen this slice's owns to cover them, give one slice sole "
                    "ownership of the concept, or promote it to a cross-repo contract"
                )
            else:
                print(f"  ok  {slice_['id']} \"{concept}\": {inside} definition site(s), all owned")

    if failed:
        print("CONCEPTS: FAIL")
        return 1
    if undeclared:
        print(f"CONCEPTS: UNVERIFIED (exit 3) — {len(undeclared)} slice(s) never declared "
              f"a \"concepts\" key: {', '.join(undeclared)}")
        print("  This is NOT a pass. Nothing was proved about those slices. Either list the "
              "shared\n  concepts each one widens, or write \"concepts\": [] to record that "
              "it shares none.")
        return 3

    print("CONCEPTS: OK")
    return 0


def selfcheck():
    import tempfile
    from pathlib import Path

    d = tempfile.mkdtemp()
    Path(d, "owned.ts").write_text("export type Kind = 'a' | 'b';\n")
    Path(d, "stray.py").write_text("Kind = ['a', 'b']\n")
    Path(d, "mention.ts").write_text("import { Kind } from './owned';\n")
    manifest = Path(d, "slices.json")

    manifest.write_text(json.dumps({"slices": [
        {"id": "01", "owns": ["owned.ts"], "concepts": ["Kind"]},
    ]}))
    assert main(str(manifest), [d]) == 1, "a definition outside owns must fail"

    manifest.write_text(json.dumps({"slices": [
        {"id": "01", "owns": ["owned.ts", "stray.py"], "concepts": ["Kind"]},
    ]}))
    assert main(str(manifest), [d]) == 0, "owning every definition site must pass"

    manifest.write_text(json.dumps({"slices": [{"id": "01", "owns": ["owned.ts"]}]}))
    assert main(str(manifest), [d]) == 3, \
        "a missing \"concepts\" key is UNVERIFIED (exit 3), never a silent exit 0"

    manifest.write_text(json.dumps({"slices": [
        {"id": "01", "owns": ["owned.ts"], "concepts": []},
    ]}))
    assert main(str(manifest), [d]) == 0, \
        "an explicit empty list is a declaration of none, and must pass"

    # Mixed manifest: one slice declares, the other forgot. The declared one being
    # clean must not launder the one that never answered.
    manifest.write_text(json.dumps({"slices": [
        {"id": "01", "owns": ["owned.ts", "stray.py"], "concepts": ["Kind"]},
        {"id": "02", "owns": ["mention.ts"]},
    ]}))
    assert main(str(manifest), [d]) == 3, \
        "one clean slice must not turn another slice's silence into a pass"

    # A real failure still outranks an undeclared slice: FAIL, not UNVERIFIED.
    manifest.write_text(json.dumps({"slices": [
        {"id": "01", "owns": ["owned.ts"], "concepts": ["Kind"]},
        {"id": "02", "owns": ["mention.ts"]},
    ]}))
    assert main(str(manifest), [d]) == 1, "an unowned definition must still FAIL (exit 1)"

    manifest.write_text(json.dumps({"slices": [
        {"id": "01", "owns": ["owned.ts"], "concepts": ["Knid"]},
    ]}))
    assert main(str(manifest), [d]) == 1, \
        "a concept with zero definition sites is UNVERIFIED, not a pass"

    print("selfcheck OK")
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--selfcheck":
        sys.exit(selfcheck())
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2:]))

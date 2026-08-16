#!/usr/bin/env python3
"""Requirements traceability: every acceptance criterion reaches a slice.

`gate.py` proves the tests that exist are green. `owns.py` proves no two slices
write the same file. Neither can prove the thing a story actually asks for got
built at all — because the test that *should* exist for an unbuilt requirement was
simply never written, and a suite of the tests that do exist passes without it.
"All requirements satisfied" was, until this gate, an assertion nobody could check.

This closes that gap by making the story→slice mapping explicit and then checking
it both directions:

  1. STORY.md gives every acceptance criterion a stable id — `AC-1`, `AC-2`, …
  2. Each slice in slices.json declares which criteria it covers:

         { "id": "01-sync", "owns": [...], "covers": ["AC-1", "AC-3"] }

  3. This gate fails if any criterion is covered by no slice (a requirement nobody
     built), or if a slice claims a criterion the story does not define (a typo, or
     a criterion deleted from the story but not from the slice).

The mapping is the point. It is what lets `/sdlc` loop a feature until coverage is
complete instead of stopping when the work merely *feels* done — the exit condition
is "every AC maps to a slice", which is a fact, not a feeling.

Green-ness stays `gate.py`'s job: coverage proves the requirement is *claimed* by a
slice; `gate.py testout` proves that slice's tests actually ran and passed. Run both
in `/before-pr` and a criterion is covered only when some slice both claims it and is
green.

A slice with no "covers" key has not answered the question. That is UNVERIFIED
(exit 3), never a silent pass — the same rule concepts.py uses, and for the same
reason: the four-copy bug and the unbuilt-requirement bug are both bugs of *silence*,
of a check quietly opting itself out on exactly the slice nobody thought about. An
explicit `"covers": []` is a real answer ("this slice implements no acceptance
criterion — it is scaffolding, config, or docs") and passes.

Usage:
    coverage.py map <arch_dir>        story ACs <-> slice coverage, both directions
    coverage.py selfcheck             verify this file against its own spec

Exit 0 = OK, 1 = FAIL (uncovered or dangling), 2 = usage/IO, 3 = UNVERIFIED.
"""
import json
import re
import sys
from pathlib import Path

# An acceptance-criterion id: AC-1, AC-12, ac-3 (folded to upper). Anchored so a
# stray "AC-1" inside prose two columns over cannot register as a criterion — the
# id must be the whole first table cell, nothing else in it.
_AC_ID = re.compile(r"^AC-(\d+)$", re.I)
_TABLE_ROW = re.compile(r"^\|(.+)\|\s*$", re.M)
_SECTION = re.compile(r"^##\s+(.+?)\s*$", re.M)


def _section_body(text, title_pred):
    """Body of the first '## ' section whose lowercased title satisfies title_pred."""
    marks = list(_SECTION.finditer(text))
    for i, m in enumerate(marks):
        if title_pred(m.group(1).strip().lower()):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            return text[m.end():end]
    return None


def story_criteria(arch_dir):
    """The set of AC ids declared in STORY.md's acceptance-criteria table.

    Returns (ids, error). Exactly one is truthy: a list of ids on success, or a
    diagnostic string when the section or its ids are missing. An empty section is
    an error, not an empty success — a story with no acceptance criterion has not
    been written, and passing it would let a featureless feature through.
    """
    story = Path(arch_dir) / "STORY.md"
    if not story.exists():
        return None, f"{story}: missing. Run /story before gating coverage."
    text = story.read_text(errors="replace")
    body = _section_body(text, lambda t: t.startswith("acceptance criteria"))
    if body is None:
        return None, (f"{story}: no '## Acceptance criteria' section. /story must write "
                      f"one, with an AC-<n> id in the first column of every row.")

    ids = []
    seen = set()
    for row in _TABLE_ROW.finditer(body):
        first = row.group(1).split("|", 1)[0].strip()
        m = _AC_ID.match(first)
        if not m:
            continue
        cid = f"AC-{int(m.group(1))}"
        if cid in seen:
            # Two rows numbered AC-3 is a story bug: a slice covering "AC-3" would
            # satisfy an ambiguous target. Names must be unique to be traceable.
            return None, (f"{story}: acceptance criterion {cid} is defined on more than "
                          f"one row. Each AC-<n> id must be unique.")
        seen.add(cid)
        ids.append(cid)

    if not ids:
        return None, (f"{story}: the '## Acceptance criteria' section has no AC-<n> ids. "
                      f"Give each criterion a stable id in the first column: "
                      f"| AC-1 | given/when/then | how proven |")
    return ids, None


def slice_coverage(arch_dir):
    """Per-slice declared coverage from slices.json.

    Returns (covers_by_slice, undeclared, error): a dict {slice_id: [AC ids]} for
    every slice that declared a "covers" key, a list of slice ids that did not, and
    an error string if the manifest itself is unreadable.
    """
    manifest = Path(arch_dir) / "slices.json"
    if not manifest.exists():
        return None, None, f"{manifest}: missing. Run /slice before gating coverage."
    try:
        data = json.loads(manifest.read_text(errors="replace"))
    except json.JSONDecodeError as e:
        return None, None, f"{manifest}: not valid JSON ({e})."
    slices = data.get("slices")
    if not isinstance(slices, list):
        return None, None, f"{manifest}: no \"slices\" array."

    covers_by_slice = {}
    undeclared = []
    for s in slices:
        sid = s.get("id", "<no id>")
        if "covers" not in s:
            undeclared.append(sid)
            continue
        covers = s["covers"]
        if not isinstance(covers, list):
            return None, None, (f"{manifest}: slice {sid!r} has a \"covers\" that is not a "
                                f"list. Use [\"AC-1\", ...] or [] for none.")
        norm = []
        for c in covers:
            m = _AC_ID.match(str(c).strip())
            # Keep the raw token when it is not an AC id at all, so the dangling
            # report can name exactly what the author typed.
            norm.append(f"AC-{int(m.group(1))}" if m else str(c).strip())
        covers_by_slice[sid] = norm
    return covers_by_slice, undeclared, None


def check_map(arch_dir):
    """Return (exit_code, lines). 0 OK, 1 FAIL, 2 IO, 3 UNVERIFIED."""
    ids, err = story_criteria(arch_dir)
    if err:
        return 2, [err]
    covers_by_slice, undeclared, err = slice_coverage(arch_dir)
    if err:
        return 2, [err]

    story_set = set(ids)
    covered = set()
    for cs in covers_by_slice.values():
        covered |= set(cs)

    lines = []
    fail = False

    # Direction 1: asked for but not built. Every story AC must be some slice's job.
    uncovered = [c for c in ids if c not in covered]  # keep story order
    if uncovered:
        fail = True
        for c in uncovered:
            lines.append(
                f"UNCOVERED  {c}: no slice claims it. Add it to a slice's \"covers\", or "
                f"delete it from STORY.md if it is genuinely out of scope."
            )

    # Direction 2: built for, but never asked. A covers-ref with no matching AC is a
    # typo or a criterion removed from the story but not the slice — either way the
    # slice is chasing a target that no longer exists.
    dangling = {}
    for sid, cs in covers_by_slice.items():
        for c in cs:
            if c not in story_set:
                dangling.setdefault(c, []).append(sid)
    for c in sorted(dangling):
        fail = True
        who = ", ".join(sorted(dangling[c]))
        lines.append(
            f"DANGLING   {c}: claimed by slice(s) {who} but STORY.md defines no such "
            f"criterion. Fix the id, or add the criterion to the story."
        )

    if fail:
        lines.append(f"COVERAGE: FAIL — {len(story_set)} criteria, "
                     f"{len(uncovered)} uncovered, {len(dangling)} dangling")
        return 1, lines

    # Silence is not a pass: a slice that never declared coverage was never checked,
    # so a clean result over the slices that DID declare must not launder it.
    if undeclared:
        for sid in undeclared:
            lines.append(
                f"UNVERIFIED {sid}: no \"covers\" key. This slice never said which "
                f"acceptance criteria it implements, so nothing about it was checked."
            )
        lines.append(
            f"COVERAGE: UNVERIFIED (exit 3) — {len(undeclared)} slice(s) never declared "
            f"\"covers\". Add the AC ids each implements, or \"covers\": [] to record that "
            f"it implements none (scaffolding, config, docs)."
        )
        return 3, lines

    lines.append(f"COVERAGE: OK — all {len(story_set)} acceptance criteria reach a slice")
    return 0, lines


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]

    if cmd == "selfcheck":
        return selfcheck()
    if cmd == "map":
        if not rest:
            print("usage: coverage.py map <arch_dir>", file=sys.stderr)
            return 2
        code, lines = check_map(rest[0])
        stream = sys.stdout if code == 0 else sys.stderr
        for ln in lines:
            print(ln, file=stream)
        return code

    print(f"unknown subcommand '{cmd}' (expected: map, selfcheck)", file=sys.stderr)
    return 2


def selfcheck():
    import tempfile

    d = Path(tempfile.mkdtemp())
    story = d / "STORY.md"
    manifest = d / "slices.json"

    def write_story(rows):
        story.write_text(
            "# Feature — story\n\n"
            "## Acceptance criteria\n"
            "| # | Given / when / then | How it is proven |\n"
            "|---|---|---|\n" + rows + "\n"
            "## Explicitly out of scope\n- nothing\n"
        )

    def write_slices(slices):
        manifest.write_text(json.dumps({"slices": slices}))

    def run():
        return check_map(str(d))[0]

    two_acs = ("| AC-1 | offline edits queue | queue.spec |\n"
               "| AC-2 | conflict resolves last-write-wins | resolve.spec |\n")

    # A missing story or manifest is an IO error (exit 2), distinct from a coverage
    # FAIL — the operator must know the difference between "not gated yet" and "gated
    # and failed".
    write_slices([{"id": "01", "owns": ["a.ts"], "covers": ["AC-1"]}])
    assert run() == 2, "a missing STORY.md must be exit 2 (IO), not a coverage verdict"
    assert "missing" in check_map(str(d))[1][0], "the message must name the missing file"

    # A story with the section but no AC-<n> ids cannot be traced at all.
    story.write_text("# F\n\n## Acceptance criteria\n| # | x | y |\n|---|---|---|\n"
                     "| 1 | a positive path | test |\n\n## Explicitly out of scope\n- z\n")
    assert run() == 2, "a criteria section with no AC-<n> ids must fail as unusable (exit 2)"
    assert "no AC-<n> ids" in check_map(str(d))[1][0]

    # Duplicate ids are a story bug: an ambiguous target is not a traceable one.
    write_story("| AC-1 | a | t |\n| AC-1 | b | t |\n")
    assert run() == 2 and "more than one row" in "\n".join(check_map(str(d))[1]), \
        "a duplicated AC id must be reported, not silently deduplicated"

    # The happy path: every AC claimed by a slice, every slice declared.
    write_story(two_acs)
    write_slices([
        {"id": "01", "owns": ["q.ts"], "covers": ["AC-1"]},
        {"id": "02", "owns": ["r.ts"], "covers": ["AC-2"]},
    ])
    assert run() == 0, "every AC covered and every slice declared must pass"

    # One AC covered by nobody is the unbuilt-requirement bug this gate exists for.
    write_slices([
        {"id": "01", "owns": ["q.ts"], "covers": ["AC-1"]},
        {"id": "02", "owns": ["r.ts"], "covers": []},
    ])
    code, lines = check_map(str(d))
    assert code == 1, "an AC no slice covers must FAIL"
    assert any("UNCOVERED  AC-2" in ln for ln in lines), \
        f"the uncovered criterion must be named: {lines}"

    # A slice claiming an AC the story does not define is the dangling / typo case.
    write_slices([
        {"id": "01", "owns": ["q.ts"], "covers": ["AC-1"]},
        {"id": "02", "owns": ["r.ts"], "covers": ["AC-2", "AC-9"]},
    ])
    code, lines = check_map(str(d))
    assert code == 1, "a covers-ref with no matching AC must FAIL"
    assert any("DANGLING   AC-9" in ln for ln in lines), f"the dangling ref must be named: {lines}"
    assert any("slice(s) 02" in ln for ln in lines), "the dangling report must name the slice"

    # A slice with no "covers" key is UNVERIFIED (exit 3), never a silent pass — even
    # when every declared slice is clean.
    write_slices([
        {"id": "01", "owns": ["q.ts"], "covers": ["AC-1", "AC-2"]},
        {"id": "02", "owns": ["r.ts"]},
    ])
    code, lines = check_map(str(d))
    assert code == 3, "a slice with no \"covers\" key must be UNVERIFIED (exit 3)"
    assert any("UNVERIFIED 02" in ln for ln in lines), f"the undeclared slice must be named: {lines}"

    # A real FAIL outranks an UNVERIFIED: an uncovered AC is a definite bug, a missing
    # key is an unanswered question — report the bug.
    write_slices([
        {"id": "01", "owns": ["q.ts"], "covers": ["AC-1"]},
        {"id": "02", "owns": ["r.ts"]},
    ])
    assert check_map(str(d))[0] == 1, \
        "an uncovered AC (FAIL) must outrank an undeclared slice (UNVERIFIED)"

    # An explicit empty list is a real answer and must pass when it leaves no AC
    # uncovered — a scaffolding slice implements no criterion, and says so.
    write_story("| AC-1 | only one | t |\n")
    write_slices([
        {"id": "01", "owns": ["q.ts"], "covers": ["AC-1"]},
        {"id": "02", "owns": ["config.ts"], "covers": []},
    ])
    assert run() == 0, "an explicit \"covers\": [] is a declaration of none and must pass"

    # Case folding: AC-1 in the story and ac-1 in the manifest are the same criterion.
    write_slices([{"id": "01", "owns": ["q.ts"], "covers": ["ac-1"]}])
    assert run() == 0, "AC ids must compare case-insensitively"

    print("coverage.py selfcheck: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

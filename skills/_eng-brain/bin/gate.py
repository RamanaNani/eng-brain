#!/usr/bin/env python3
"""Pre-PR gate: failure-mode coverage and honest test output.

Provenance: the original gate.py was only partially recovered from brain
transcripts — its `selfcheck()` survived intact but the implementation did not.
That selfcheck is a precise executable spec (it pins exact behaviour AND exact
diagnostic wording), so the implementation below was rebuilt to satisfy it and
is verified by running `gate.py selfcheck`. The runner regexes are transcribed
from the recovered copy; the comments explaining them are the original's and are
worth keeping — each one records a real false result someone had to debug.

Subcommands:
    gate.py modes   <arch_dir>       every failure mode reaches a slice brief
    gate.py testout <file>           the runner actually ran and was green
    gate.py selfcheck                verify this file against the original spec

Exit 0 pass, 1 fail.
"""
import re
import sys
from pathlib import Path

# --- test-output parsing (transcribed from the recovered copy) ----------------
# node --test prints '# fail 0' / '# pass 12'. An earlier version of this regex was
# written from memory and matched neither of a real node v24 run. The prefix is
# '\S{0,2}' and not '\W*' because Python's \w matches U+2139 INFORMATION SOURCE
# — it is Alphabetic — so '[^\w]' skips past nothing at all on the spec line.
_NODE = r"^\s*\S{{0,2}}\s*{word}\s+(\d+)\s*$"
_FAIL_COUNTS = (
    re.compile(r"\b(\d+)\s+fail(?:ed|ures?|ing)\b", re.I),  # pytest jest cargo mocha
    re.compile(r"\b(\d+)\s+errors?\b", re.I),               # pytest "1 error", mocha
    re.compile(_NODE.format(word="fail"), re.I | re.M),     # node --test
)
_PASS_COUNTS = (
    re.compile(r"\b(\d+)\s+pass(?:ed|ing)\b", re.I),        # pytest jest cargo mocha
    re.compile(_NODE.format(word="pass"), re.I | re.M),     # node --test
)
# go test prints no counts at all: one 'ok <pkg> 0.01s' line per passing package
# and 'FAIL'/'--- FAIL: TestX' per failing one. TAP prints 'ok 1 - name' and
# 'not ok 1 - name'. jest prints 'FAIL src/foo.test.js' per red suite file.
_UNCOUNTED_PASS = re.compile(r"^ok[ \t]+\S+", re.M)
_UNCOUNTED_FAIL = re.compile(r"^(?:---\s*)?FAIL\b|^not ok\b", re.M)
# python3 -m unittest prints no pass count and no 'ok <name>' line. A green run is
# 'Ran 2 tests in 0.000s' followed by a bare 'OK', and neither matched anything
# above, so a legitimately green unittest slice was rejected as NOT RUN. 'FAILED'
# does not match _UNCOUNTED_FAIL either: '\b' after FAIL does not fire before the
# 'E'. The count lives inside the parens — 'FAILED (failures=1, errors=2)'.
_UNITTEST_RAN = re.compile(r"^Ran (\d+) tests? in ", re.M)
_UNITTEST_FAILED = re.compile(r"^FAILED\s*\(([^)]*)\)\s*$", re.M)
# A run that DIED is not a run that passed. None of the count regexes above fire
# on a crash, so without these a suite that panicked after printing a green
# summary reads as green. Checked before any green return.
_ABORT = re.compile(
    r"^panic:"
    r"|Segmentation fault"
    r"|^Traceback \(most recent call last\)"
    r"|^error: could not compile"
    r"|^error: test failed"
    r"|^FAILURES!"
    r"|Unhandled Error",
    re.M,
)


def _sum(patterns, text):
    total, seen = 0, False
    for p in patterns:
        for m in p.finditer(text):
            total += int(m.group(1))
            seen = True
    return total, seen


def check_testout(path):
    """Return a list of problems. Empty list means the suite genuinely passed.

    Ordering rule: EVERY red signal is consulted before any green return. An
    earlier version returned [] as soon as it saw a pass count, which made the
    uncounted-red, unittest-red and crash checks unreachable whenever a green
    summary appeared anywhere in the file — so a monorepo slice teeing two
    runners into one log read green while one runner was red.
    """
    p = Path(path)
    if not p.exists():
        return [f"{path}: NOT RUN — no test output file. The slice did not run the tests."]
    text = p.read_text(errors="replace")
    if not text.strip():
        return [f"{path}: NOT RUN — output is empty. The slice did not run the tests."]

    failed, saw_fail = _sum(_FAIL_COUNTS, text)
    passed, saw_pass = _sum(_PASS_COUNTS, text)

    # --- red signals first, unconditionally ---------------------------------
    if (m := _ABORT.search(text)):
        return [f"{path}: RED — the run aborted ({m.group(0).strip()!r}). A crashed run is not a pass."]

    if saw_fail and failed > 0:
        return [f"{path}: RED — {failed} failing. A run with failures is not a pass."]

    if (m := _UNITTEST_FAILED.search(text)):
        return [f"{path}: RED — unittest reported FAILED ({m.group(1)})."]

    if _UNCOUNTED_FAIL.search(text):
        return [f"{path}: RED — runner reported FAIL."]

    # --- only now may it be green -------------------------------------------
    ran = _UNITTEST_RAN.search(text)
    if ran and not saw_pass:
        if int(ran.group(1)) == 0:
            return [f"{path}: NOT RUN — the runner collected 0 tests."]
        return []

    if saw_pass:
        if passed == 0:
            return [f"{path}: NOT RUN — the runner collected 0 tests."]
        return []

    if _UNCOUNTED_PASS.search(text):
        return []

    return [f"{path}: NOT RUN — no runner summary found in the output."]


# --- failure-mode coverage ----------------------------------------------------
_MODE_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|", re.M)
_SECTION = re.compile(r"^##\s+(.+?)\s*$", re.M)


def _section_body(text, title_pred):
    """Body text of the first '## ' section whose title satisfies title_pred."""
    marks = list(_SECTION.finditer(text))
    for i, m in enumerate(marks):
        if title_pred(m.group(1).strip().lower()):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            return text[m.end():end]
    return None


def _failure_modes(arch_text):
    body = _section_body(arch_text, lambda t: t.startswith("failure mode"))
    if body is None:
        return None
    modes = []
    for row in _MODE_ROW.finditer(body):
        cell = row.group(1).strip()
        if not cell or set(cell) <= set("-: "):      # separator row
            continue
        if cell.lower() in ("mode", "failure mode"):  # header row
            continue
        modes.append(cell)
    return modes


def _briefs(arch_dir):
    """Slice briefs only. ADRs are not briefs, and must not count as coverage."""
    d = Path(arch_dir)
    out = list((d / "slices").glob("*.md")) if (d / "slices").is_dir() else []
    for p in d.glob("*.md"):
        if p.name == "ARCHITECTURE.md" or p.name.startswith("ADR-"):
            continue
        out.append(p)
    return out


def check_modes(arch_dir):
    d = Path(arch_dir)
    arch = d / "ARCHITECTURE.md"
    if not arch.exists():
        return [f"{arch}: missing. Run /arch before gating."]
    text = arch.read_text(errors="replace")
    modes = _failure_modes(text)
    if modes is None:
        return [f"{arch}: no '## Failure modes' section. /arch must enumerate them."]
    if not modes:
        return [f"{arch}: '## Failure modes' section is empty."]

    briefs = _briefs(arch_dir)
    if not briefs:
        # Without this branch every mode also reads as "never reaches any brief",
        # which would send the operator to edit files that do not exist.
        return [f"{arch_dir}: no slice briefs found under slices/. Run /slice before gating."]

    covered = ""
    for b in briefs:
        t = b.read_text(errors="replace")
        for pred in (lambda s: s.startswith("edge cases"), lambda s: s.startswith("out of scope")):
            body = _section_body(t, pred)
            if body:
                covered += "\n" + body

    covered_l = covered.lower()
    problems = []
    for mode in modes:
        if mode.lower() not in covered_l:
            problems.append(
                f"failure mode never reaches a slice brief: '{mode}' — add it to a brief's "
                f"'## Edge cases to test' or '## Out of scope'."
            )
    return problems


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 1
    cmd, rest = argv[0], argv[1:]

    if cmd == "selfcheck":
        selfcheck()
        print("gate.py selfcheck: OK")
        return 0
    if cmd == "modes":
        if not rest:
            print("usage: gate.py modes <arch_dir>", file=sys.stderr)
            return 1
        problems = check_modes(rest[0])
    elif cmd == "testout":
        if not rest:
            print("usage: gate.py testout <file>", file=sys.stderr)
            return 1
        problems = check_testout(rest[0])
    else:
        print(f"unknown subcommand '{cmd}'", file=sys.stderr)
        return 1

    for p in problems:
        print(p, file=sys.stderr)
    return 1 if problems else 0


def selfcheck():
    import tempfile

    # --- modes: fixtures laid out exactly as slice/SKILL.md Phase 4 documents ---
    d = Path(tempfile.mkdtemp())
    arch = d / "ARCHITECTURE.md"

    assert main(["modes", str(d)]) == 1, "a missing ARCHITECTURE.md must fail"

    arch.write_text("# Feature\n\n## Interfaces\nnothing here\n")
    assert main(["modes", str(d)]) == 1, "no '## Failure modes' section must fail"

    arch.write_text(
        "# Feature\n\n"
        "## Failure modes\n"
        "| Mode | Guaranteed behaviour |\n"
        "|---|---|\n"
        "| pooler drops the prepared statement | search returns empty, not an error |\n"
        "| capture resolves the wrong source | the write lands in a code source |\n"
        "\n## Interfaces\nunrelated\n"
    )
    # Exit 1 alone does not prove this branch survives: with no briefs, every mode
    # is also "never reaches any brief". That diagnosis would send the operator to
    # edit files that do not exist, so the message is the behaviour here.
    probs = check_modes(str(d))
    assert probs and "no slice briefs found" in probs[0], \
        f"no briefs must be named as such, not listed as one miss per mode: {probs}"

    # An ADR is not a brief. It covers mode two; the gate must still report mode two
    # missing, which is only true if slices/ IS read and ADR-*.md is NOT.
    (d / "ADR-001-source-resolution.md").write_text(
        "## Edge cases to test\n- capture resolves the wrong source\n")
    (d / "slices").mkdir()
    (d / "slices" / "01-pooler.md").write_text(
        "# Slice 01\n\n## Edge cases to test\n- pooler drops the prepared statement\n")
    probs = check_modes(str(d))
    assert len(probs) == 1 and "wrong source" in probs[0], (
        f"a brief under slices/ must count and an ADR must not: {probs}")

    (d / "02-source.md").write_text(
        "# Slice 02\n\n## Out of scope\n"
        "- capture resolves the wrong source — owned by the ops runbook\n")
    assert main(["modes", str(d)]) == 0, "a root-level brief must still count"

    # --- testout ---
    t = Path(tempfile.mkdtemp())
    out = t / "test_output.txt"

    def testout(sample):
        out.write_text(sample)
        return main(["testout", str(out)])

    assert testout("") == 1, "empty output must fail"
    assert testout("running the suite...\nlooks good to me!\n") == 1, \
        "prose with no counts must fail"

    # Both of those also trip the zero-passing check below, so the exit code alone
    # cannot tell whether these two branches still exist. Their whole job is the
    # message — the operator has to know whether the file was empty or merely
    # unparseable — so the message is what has to be pinned.
    out.write_text("")
    assert "did not run the tests" in check_testout(str(out))[0], \
        "an empty file must be reported as never run, not as an unparseable one"
    out.write_text("running the suite...\nlooks good to me!\n")
    assert "no runner summary" in check_testout(str(out))[0], \
        "prose must be reported as NOT RUN, not as a suite that collected nothing"

    # The three fixtures the round-1 critic proved this gate PASSED. All red.
    assert testout("=== 3 failed, 5 passed in 2.1s ===") == 1, \
        "pytest red must fail: 3 failed is not a pass"
    assert testout("# tests 12\n# pass 10\n# fail 2\n") == 1, \
        "node --test red must fail"
    assert testout("--- FAIL: TestThing (0.00s)\nFAIL\n") == 1, \
        "go red must fail"

    # Green fixtures, one per runner family.
    assert testout("=== 5 passed in 2.1s ===") == 0, "pytest green must pass"
    assert testout("# tests 12\n# pass 12\n# fail 0\n") == 0, "node green must pass"
    assert testout("ok  \tgithub.com/x/y\t0.01s\n") == 0, "go green must pass"
    assert testout("Ran 2 tests in 0.001s\n\nOK\n") == 0, "unittest green must pass"
    assert testout("Ran 2 tests in 0.001s\n\nFAILED (failures=1)\n") == 1, \
        "unittest red must fail"


if __name__ == "__main__":
    sys.exit(main())

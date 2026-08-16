#!/usr/bin/env python3
"""Feature state machine for the eng-brain SDLC spine.

The pipeline stages already existed as independent skills; nothing sequenced
them, so "where is this feature stuck" was unanswerable and gates were skippable
by simply invoking the next skill. This holds the ladder and refuses to advance
past a gate that has not been shown to pass.

State lives at docs/arch/<feature>/STATE.json so it travels with the artifacts
and survives a lost session.

Usage:
    state.py init   <arch_dir> --feature S [--branch B]
    state.py show   <arch_dir> [--json]
    state.py next   <arch_dir>
    state.py pass   <arch_dir> --stage S [--artifact P] [--note N]
    state.py fail   <arch_dir> --stage S --why W
    state.py skip   <arch_dir> --stage S --why W

Exit codes: 0 ok, 1 usage/IO error, 2 gate refused.
"""
import argparse, json, os, sys
from datetime import datetime, timezone

SCHEMA = "eng-brain.state/v1"

# The ladder. Order is meaningful; `optional` stages may be skipped with a reason.
LADDER = [
    ("story",     False, "STORY.md"),
    ("arch",      False, "ARCHITECTURE.md"),
    ("contract",  True,  "contracts/"),
    ("slice",     False, "slices.json"),
    ("fleet",     False, "FLEET.md"),
    # before-pr is mechanical and cheap; review is judgment and expensive.
    # Mechanical first — nobody should spend review attention on code whose
    # tests are red.
    ("before-pr", False, "GATE.md"),
    ("review",    False, "REVIEW.md"),
    # Optional because a docs change does not warrant a DAST run and DAST needs
    # a live target — but it must be SKIPPED WITH A REASON, never silently
    # dropped. That is the whole point of optional-but-recorded here.
    ("pentest",   True,  "PENTEST.md"),
    ("pr",        False, "PR.md"),
    # deploy sits AFTER pr because a human merges in between. This stage detects
    # that merge; it never performs it. Optional because a library change may
    # have nothing to deploy — but skipping still needs a reason on the record.
    ("deploy",    True,  "DEPLOY.md"),
    # canary measures the delta a deploy caused, so it follows deploy.
    ("canary",    True,  "CANARY.md"),
]
NAMES = [n for n, _, _ in LADDER]
OPTIONAL = {n for n, o, _ in LADDER if o}
ARTIFACT = {n: a for n, _, a in LADDER}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def path_of(arch_dir):
    return os.path.join(arch_dir, "STATE.json")


def load(arch_dir):
    p = path_of(arch_dir)
    if not os.path.exists(p):
        sys.exit(f"no STATE.json at {p} — run: state.py init {arch_dir} --feature <slug>")
    try:
        with open(p) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        # A corrupt STATE.json used to surface as a raw traceback, which reads like a
        # bug in this tool rather than a damaged file the operator can fix or restore.
        sys.exit(f"STATE.json at {p} is not valid JSON ({e}). It may be corrupt — restore "
                 f"it from git, or re-init with: state.py init {arch_dir} --feature <slug> --force")


def save(arch_dir, st):
    # Write-and-rename so an interrupted write can never leave a half-written STATE.json.
    # os.replace is atomic on the same filesystem, so a reader either sees the old file
    # or the new one, never a truncated one — this file is the whole point of surviving
    # a lost session, so it must not be the thing a crash corrupts.
    os.makedirs(arch_dir, exist_ok=True)
    final = path_of(arch_dir)
    tmp = f"{final}.tmp.{os.getpid()}"
    try:
        with open(tmp, "w") as f:
            json.dump(st, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, final)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def cmd_init(a):
    p = path_of(a.arch_dir)
    if os.path.exists(p) and not a.force:
        sys.exit(f"STATE.json already exists at {p} (use --force to reset)")
    st = {
        "schema": SCHEMA,
        "feature": a.feature,
        "created": now(),
        "source_branch": a.branch,
        "stages": {n: {"status": "pending"} for n in NAMES},
    }
    save(a.arch_dir, st)
    print(f"initialised {a.feature} at {p}")


def blocking(st):
    """First stage that is not pass/skipped, or None if the ladder is complete."""
    for n in NAMES:
        if st["stages"].get(n, {}).get("status") not in ("pass", "skipped"):
            return n
    return None


def cmd_show(a):
    st = load(a.arch_dir)
    if a.json:
        print(json.dumps(st, indent=2))
        return
    nxt = blocking(st)
    print(f"feature : {st['feature']}   branch: {st.get('source_branch') or '?'}")
    print(f"next    : {nxt or 'COMPLETE'}\n")
    for n in NAMES:
        s = st["stages"].get(n, {})
        status = s.get("status", "pending")
        mark = {"pass": "✓", "skipped": "–", "fail": "✗", "pending": "·"}.get(status, "?")
        extra = ""
        if status == "skipped":
            extra = f"  ({s.get('why','no reason recorded')})"
        elif status == "fail":
            extra = f"  ({s.get('why','')})"
        elif status == "pass" and s.get("artifact"):
            extra = f"  -> {s['artifact']}"
        opt = " [optional]" if n in OPTIONAL else ""
        print(f"  {mark} {n:<10}{opt}{extra}")


def cmd_next(a):
    st = load(a.arch_dir)
    nxt = blocking(st)
    if nxt is None:
        print("COMPLETE")
        return
    print(nxt)


def _require_order(st, stage):
    """Refuse to record a stage while an earlier mandatory one is unmet."""
    idx = NAMES.index(stage)
    for n in NAMES[:idx]:
        s = st["stages"].get(n, {}).get("status")
        if s in ("pass", "skipped"):
            continue
        # NB: optional stages block too. "Optional" means it may be SKIPPED —
        # with a reason on the record — not that it may be ignored. Letting a
        # pending `pentest` slide silently is exactly the outcome the stage
        # exists to prevent.
        print(
            f"REFUSED: cannot record '{stage}' while '{n}' is {s or 'pending'}.\n"
            f"The ladder is ordered. Either run {n} first, or — if it genuinely does "
            f"not apply — record it explicitly:\n"
            f"    state.py skip {'<arch_dir>'} --stage {n} --why '<reason>'",
            file=sys.stderr,
        )
        sys.exit(2)


def cmd_pass(a):
    st = load(a.arch_dir)
    if a.stage not in NAMES:
        sys.exit(f"unknown stage '{a.stage}' (expected one of: {', '.join(NAMES)})")
    _require_order(st, a.stage)
    entry = {"status": "pass", "at": now()}
    entry["artifact"] = a.artifact or ARTIFACT[a.stage]
    if a.note:
        entry["note"] = a.note
    st["stages"][a.stage] = entry
    save(a.arch_dir, st)
    nxt = blocking(st)
    print(f"{a.stage}: pass   next: {nxt or 'COMPLETE'}")


def cmd_fail(a):
    st = load(a.arch_dir)
    if a.stage not in NAMES:
        sys.exit(f"unknown stage '{a.stage}'")
    st["stages"][a.stage] = {"status": "fail", "at": now(), "why": a.why}
    save(a.arch_dir, st)
    print(f"{a.stage}: fail — {a.why}")


def cmd_skip(a):
    st = load(a.arch_dir)
    if a.stage not in NAMES:
        sys.exit(f"unknown stage '{a.stage}'")
    if a.stage not in OPTIONAL:
        sys.exit(
            f"REFUSED: '{a.stage}' is mandatory and cannot be skipped.\n"
            f"Optional stages are: {', '.join(sorted(OPTIONAL))}"
        )
    st["stages"][a.stage] = {"status": "skipped", "at": now(), "why": a.why}
    save(a.arch_dir, st)
    nxt = blocking(st)
    print(f"{a.stage}: skipped — {a.why}   next: {nxt or 'COMPLETE'}")


def main():
    p = argparse.ArgumentParser(prog="state.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("arch_dir")
        return sp

    i = common(sub.add_parser("init"))
    i.add_argument("--feature", required=True)
    i.add_argument("--branch", default=None)
    i.add_argument("--force", action="store_true")
    i.set_defaults(fn=cmd_init)

    s = common(sub.add_parser("show"))
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_show)

    n = common(sub.add_parser("next"))
    n.set_defaults(fn=cmd_next)

    pa = common(sub.add_parser("pass"))
    pa.add_argument("--stage", required=True)
    pa.add_argument("--artifact")
    pa.add_argument("--note")
    pa.set_defaults(fn=cmd_pass)

    fa = common(sub.add_parser("fail"))
    fa.add_argument("--stage", required=True)
    fa.add_argument("--why", required=True)
    fa.set_defaults(fn=cmd_fail)

    sk = common(sub.add_parser("skip"))
    sk.add_argument("--stage", required=True)
    sk.add_argument("--why", required=True)
    sk.set_defaults(fn=cmd_skip)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()

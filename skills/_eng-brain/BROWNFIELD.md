# Adding a feature to an existing codebase

Reference for `/arch` when the code already exists. Read with `CONVENTIONS.md`.

The whole game here is **fitting**. A feature that works but doesn't fit is worse than
no feature — it adds a second way to do something, and now every future change has to
handle both. Most of the work is research, not design.

---

## Phase 1 — Research (do not skip; this is 60% of the job)

Four questions, in order. Each has a command.

### 1a. What did I already decide about this?

```bash
gbrain think "<feature area> — what have I decided before, and does it still hold?"
gbrain graph-query projects/<related-feature> --direction out --depth 2
```

Plus MCP `find_contradictions` and `takes_search`. A feature that contradicts a live ADR
isn't a feature, it's a decision reversal — and it needs a new ADR with a `supersedes`
edge, not a quiet override.

### 1b. What does the code actually do today?

Not what the docs say. What it does.

```bash
gbrain code-def <EntryPoint>        # where it starts
gbrain code-callers <SharedFn>      # EVERY path that reaches it
gbrain code-refs <SharedType>       # every place the shape is assumed
```

**`code-callers` is the important one.** It's how you find the siblings. The classic
brownfield failure is fixing the path the ticket named and leaving three callers broken.
If gbrain's code index isn't built (`gbrain sync --source <id> --strategy code`), this
returns nothing and you are designing blind — build it first.

Also dispatch `ecc:code-explorer` to trace the runtime path end to end.

### 1c. Where are the seams?

A seam is where you can change behavior without editing existing logic — an interface, a
registry, a hook, a config switch. Features that land at seams are clean. Features that
land by editing five call sites are the ones people revert.

Ask: *what is the smallest set of existing files that must change?* If the answer is more
than three, look harder for a seam before accepting it.

### 1d. What constrains me?

Existing schema, public API contracts, in-flight migrations, anything a client depends on.
These are the walls. Design inside them or explicitly decide to move one — moving one is
an ADR.

---

## Phase 2 — Options and trade-offs

**1–3 options. Never more.** Two obviously-bad options padding one good one is a fake
choice; cut it to one and say "this is the only sensible shape, here's why."

For each option, state four things and nothing else:

| | |
|---|---|
| **Shape** | two sentences, how it works |
| **Fits** | which existing pattern it extends, or which it breaks |
| **Cost** | files touched, migration needed, new dependency |
| **Fails when** | the concrete condition under which this is the wrong call |

Then recommend one, with the reason.

Call out explicitly:
- **One-way doors** — schema shape, public API surface, anything with clients. Cheap now,
  expensive forever. Spend real time here.
- **Two-way doors** — internal structure, file layout, naming. Reversible. Decide fast,
  don't agonize.
- **What breaks at 10x** — not 1000x. Ten times current load is the honest horizon.

---

## Phase 3 — Apply the ponytail ladder (AFTER research, never before)

Ponytail is loaded and it governs *what you build*, not how much you understand. Its own
rule: **"The ladder shortens the solution, never the reading."** So research fully in
Phase 1, then climb:

1. **Does this need to exist?** Speculative need → say so in one line, stop.
2. **Already in this codebase?** A helper, hook, util, or pattern two files over. This
   rung catches the most waste in brownfield work — you have thousands of files and you
   have not read them all.
3. **Stdlib?**
4. **Native platform feature?** `<input type="date">` over a picker lib, CSS over JS, a DB
   constraint over app-layer validation.
5. **Already-installed dependency?** Check `package.json` before adding anything.
6. **One line?**
7. **Only then:** minimum code that works.

Two rungs work → take the higher one and move.

**Never simplify away:** input validation at trust boundaries, error handling that
prevents data loss, security, accessibility basics, anything explicitly requested.

Mark deliberate shortcuts with a `ponytail:` comment naming the ceiling and the upgrade
path: `// ponytail: linear scan, index it if this exceeds ~1k rows`.

---

## Phase 4 — API contracts

If anything outside this module calls it, the contract is the deliverable — the
implementation is an detail you can rewrite later.

Write down, exactly:
- **Shape** — request/response types, verbatim. Copy them into every slice brief; they
  are the only thing keeping parallel worktrees compatible.
- **Errors** — every failure mode and its status/type. "Throws on bad input" is not a
  contract; `400 {code: "invalid_range", field: "start"}` is.
- **Backward compatibility** — additive-only, or a version bump? Who breaks if you're
  wrong?
- **Idempotency** — can it be retried safely? Say yes or no explicitly.

Extend the existing convention even where you'd have chosen differently. Consistency beats
your preference. If the existing convention is genuinely bad, that's a separate ADR and a
separate change — not a thing you fix quietly inside a feature.

---

## Phase 5 — Algorithms and libraries

Default to the boring choice. The interesting one is what someone decodes at 3am.

Before adding a dependency, in order: is it in the repo already → stdlib → native
platform → an installed dep → a few lines of your own → new dependency (last resort).

When you do need a real algorithm, name the complexity and the input size you expect.
`O(n²)` over 50 items is fine and simple; over 50,000 it's an outage. Write the number
down in the ADR so the next person doesn't have to re-derive whether it was reasonable.

---

## Phase 6 — UI

Match what exists. Open three neighbouring screens before designing a fourth.

- **Components** — reuse before creating. A near-match you extend beats a new one.
- **States** — loading, empty, error, partial, and success. Empty and error are the ones
  that get skipped and the ones users actually hit.
- **Accessibility** — keyboard path, focus order, labels, contrast. Not optional and not
  a follow-up ticket.
- **Responsive** — the breakpoints this codebase already uses, not new ones.

If the design genuinely needs a pattern that doesn't exist yet, that's an ADR too —
because you're adding to the design system, and the next feature will copy it.

---

## Output

`docs/arch/<slug>/ARCHITECTURE.md` + one ADR per non-obvious decision, then the brain
write-back from `CONVENTIONS.md` §5. Then `/slice`.

## The brownfield failure modes

| Symptom | Root cause |
|---|---|
| Fixed one path, three siblings still broken | skipped `code-callers` |
| Second way to do an existing thing | skipped ladder rung 2 |
| Merges clean, doesn't work | interfaces underspecified in Phase 4 |
| Reverted a week later | landed by editing call sites, not at a seam |
| "Why is this here?" in six months | decision never written as an ADR |

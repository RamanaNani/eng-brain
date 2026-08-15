---
name: contract
version: 1.0.0
description: "Write the interface contract between two repos that cannot see each other, with a conformance test on each side and an explicit deploy order. Use when a feature spans more than one repository. Writes CONTRACTS.md. Runs between /arch and /slice."
triggers:
  - contract
  - cross repo
  - cross-repo contract
  - two repos
  - deploy order
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
---

# /contract — the seam between repos

Agents in separate worktrees cannot see each other's code. Agents in separate
*repos* cannot see each other at all — and neither can the type checker. A wrong
shared assumption inside one repo fails at build time; the same wrong assumption
across two repos fails in production.

This stage exists because the type checker stops at the repo boundary. Something
has to take its place, and that something is a written contract plus a test on
each side that fails when the other side drifts.

**Read `~/.claude/skills/_eng-brain/CONVENTIONS.md` first.**

## When to invoke

After `/arch`, before `/slice`, whenever the feature touches more than one repo.
`/slice` Phase 1.5 refuses to proceed on a multi-repo feature without a
CONTRACTS.md.

Single-repo features skip this entirely — the Interfaces section of
ARCHITECTURE.md already does this job, and the compiler enforces it.

## The one inviolable rule

Every contract row has a **conformance test on both sides**. A contract with
prose but no test is a comment, and comments do not fail builds. If you cannot
write a test for a row, it is not a contract — it is a hope, and it belongs in
ARCHITECTURE.md as a risk.

## Phase 1 — Find the real seam

Do not invent the seam. Trace it:

```bash
# What actually crosses? Follow the wire, not the intention.
rg -n "fetch\(|requests\.|httpx|axios|client\." --glob '!**/node_modules/**' <repo_a>
```

For each thing that crosses, record where it is produced and where it is
consumed, with `file:line` on both sides. A contract without line anchors rots
within one sprint, because nobody can find what it was describing.

## Phase 2 — Write the rows

Each row is one shared fact. Verbatim values, not descriptions of values.

| # | Fact | Producer | Consumer | Conformance test |
|---|---|---|---|---|
| C1 | Allowed attachment kinds are exactly `"literature_review"`, `"protocol"`, `"experiment"` | AI `core/agent.py:976` | acme-app `lib/mention-types.ts:12` | AI `test_kinds_match`, acme-app `mention-types.spec.ts` |
| C2 | `attachments[].kind` is required and never null on the wire | AI `request.py:88` | acme-app `right-sidebar.tsx:1307` | contract fixture, both sides |

Rules:
- Spell out the literal values. "The kind enum" is not a contract; the list is.
- Name the consumer's exact call site. That is what makes the contract findable.
- One row per fact. A row containing "and" is two rows.

## Phase 3 — The conformance test, on both sides

The pattern that works: one fixture file, committed to both repos, that each side
asserts against. When one side widens the set, the other side's test goes red on
its own next build — without anyone remembering this document exists.

```python
# AI side — tests/test_contract_kinds.py
import json, pathlib
from core.agent import ALLOWED_KINDS

def test_kinds_match_contract():
    fixture = json.loads(pathlib.Path("contracts/attachment-kinds.json").read_text())
    assert sorted(ALLOWED_KINDS) == sorted(fixture["kinds"]), (
        "AI widened the kind set without updating contracts/attachment-kinds.json; "
        "acme-app will reject these at the seam"
    )
```

```typescript
// acme-app side — lib/__tests__/contract-kinds.spec.ts
import fixture from "../../contracts/attachment-kinds.json";
import { MENTION_KINDS } from "../mention-types";

it("matches the shared attachment-kind contract", () => {
  expect([...MENTION_KINDS].sort()).toEqual([...fixture.kinds].sort());
});
```

The failure message must name the *other* repo. An engineer hitting this test is
usually not the one who broke it.

## Phase 4 — Deploy order is not build order

State both, separately. They are different, and conflating them is how a green
build produces a broken production.

```markdown
## Order
- Build dependency: none. Both sides can be built and reviewed in parallel.
- Deploy order: AI must deploy FIRST. acme-app sending a new kind to an old AI
  gets a 422. AI accepting a kind no acme-app sends yet is inert.
- Backward window: AI accepts both old and new sets for one release.
```

The general rule: **widen the consumer first, narrow the producer last.** Anything
else has a window where valid traffic is rejected.

## Phase 5 — Write CONTRACTS.md and gate

Write `docs/arch/<slug>/CONTRACTS.md` in the primary repo, and commit the fixture
to `contracts/` in **both** repos.

**Gate — all must hold before `/slice` may run:**

- [ ] Every row has verbatim values, not a description of them
- [ ] Every row names a producer `file:line` and a consumer `file:line`
- [ ] Every row has a conformance test on both sides, and both are written
- [ ] Both conformance tests have been run and observed to FAIL when the fixture
      is deliberately edited — an unfalsified test proves nothing
- [ ] Deploy order and the backward-compatibility window are stated
- [ ] `slices.json` in each repo records `"contracts": "<path to CONTRACTS.md>"`

Then **stop** and hand back for review.

## Phase 6 — Write back to the brain

```bash
python3 -c 'import json,sys; print(json.dumps({
  "slug": sys.argv[1], "type": "analysis", "title": sys.argv[2],
  "source": "default", "content": open(sys.argv[3]).read()}))' \
  "contract-$FEATURE_SLUG" "<Feature> contract" "$ARCH_DIR/CONTRACTS.md" \
| xargs -0 gbrain call put_page
```

Four things about that, none of them optional:

- **`source: "default"`.** The write matches the current directory against registered code
  sources before falling back to `default`. This stage is the one most likely to be run
  from inside a repo rather than above it — it is *about* two repos — so it is the one most
  exposed to that fallback filing the page into a code source while `link`, `tag`, `get`
  and `graph-query` keep resolving against `default`. Both halves report success.
- **Not `mcp__gbrain__put_page`.** The MCP tool returns `auto_links: {"skipped":"remote"}`;
  remote callers get no wikilink extraction and the page lands orphaned.
- **`call put_page`, not `capture`.** Both extract wikilinks locally, but `capture` stamps
  `captured_at` and `captured_via` into the frontmatter and rewrites `source_uri` to a path
  that will not survive the session. `put_page` preserves what you wrote and reports the
  edge count.
- **The `[[wikilinks]]` in CONTRACTS.md are the edges.** Head the file with
  `Feature: [[projects/<feature-slug>]]` and wikilink any ADR that forced the seam. Those
  pages exist by now — `/contract` runs after `/arch` — so they resolve on the first write.

That last point has a precondition, and it is the one that fails: **the ADR slugs are typed
from memory, and a wikilink whose target does not exist is discarded silently.** Exit 0, no
warning, and it does not even appear in `unresolved` — the write reports
`auto_links: {created: 0, removed: 0, errors: 0, unresolved: []}` whether the body linked
nothing or linked three pages that were all thrown away. Confirm each target first:

```bash
for s in "projects/$FEATURE_SLUG" analysis/adr-012-<topic>; do
  gbrain get "$s" >/dev/null 2>&1 && echo "ok   $s" || echo "MISSING $s — fix the slug before writing"
done
```

Wikilinking the architecture matters more here than anywhere else in the pipeline. This
document is the only artifact describing a boundary that **no type checker can see**, and
it lives in the primary repo while half of what it constrains lives in the other one. If
it lands unreachable, the next engineer's only route to it is remembering it exists.

Verify. Read `auto_links.created` off the write — that is the number `capture` could never
give you, since it reports slug, status and hash and says nothing about links. Then confirm
from the other side, in **two** commands, because `graph-query` is fail-open: a typo'd slug,
a page in the wrong source, and a page with genuinely no edges all print
`No edges found from <slug>.` and all exit 0.

```bash
gbrain get "contract-$FEATURE_SLUG" >/dev/null   # exit 1 + page_not_found = wrong slug or wrong source
gbrain graph-query "contract-$FEATURE_SLUG" --direction out --depth 1
```

## Failure modes

| Smell | What it means | Do this |
|---|---|---|
| A row with no test | It is a comment, not a contract | Write the test or delete the row |
| Test never observed failing | It may assert nothing | Break the fixture, watch it go red, restore |
| Deploy order unstated | Someone will ship them in the wrong order | State it, and say which side is forward-compatible |
| "The API returns a user object" | A description, not a contract | List the fields that must be present |
| Contract lives in only one repo | The other side has no tripwire | Commit the fixture to both |
| Producer widened first | Live traffic will 422 | Widen the consumer first, always |
| Page written, `graph-query` empty | a wikilink target slug does not exist, so the edge was discarded silently | `gbrain get` each target before writing. `unresolved` comes back empty either way — it will never tell you |

# Starting a new project from zero

Reference for `/arch` when there is no code yet. Read with `CONVENTIONS.md`.

Brownfield's hard problem is *fitting*. Greenfield's hard problem is **restraint**. You
have no constraints, which feels like freedom and is actually the danger — every
structure you add on day one is a structure you maintain for years, usually before you
know whether it was the right one.

The goal of week one is not a good architecture. It is **the smallest thing that runs end
to end**, so that reality starts correcting you immediately.

---

## Phase 1 — Before any architecture

Answer these four. If you can't, you are not ready to design — you are ready to talk to a
user.

1. **Who uses this and for what?** One sentence, a real person, a real job.
2. **What is the one thing it must do well?** Exactly one. Everything else is secondary
   and should be visibly secondary in the design.
3. **What does failure look like?** Data loss? Wrong answer? Slow? These rank differently
   and they pull the architecture in different directions.
4. **What's the realistic scale in 12 months?** Not the pitch-deck number. Ten users or
   ten thousand — the answer changes almost nothing structurally, and believing otherwise
   is how founders build for scale they never reach.

Then check the brain — even for a new project, you are not new:

```bash
gbrain think "What have I decided about <stack/pattern/domain> in past projects? What did I regret?"
```

Your past ADRs are the closest thing to experience you can query. A greenfield project is
where prior decisions pay off most, because nothing in the repo is arguing with you yet.

---

## Phase 2 — Build the walking skeleton first

One thin slice, end to end, deployed. Not a layer. Not a module. **A request that enters
the system, touches storage, and returns — running in the environment it will actually
live in.**

For a typical product that is: one route → one handler → one table → one rendered view,
plus deploy.

Do this before designing anything else. It surfaces the real problems — auth, config,
build, deploy, CORS, migrations — while the cost of learning is one file instead of forty.
Every hour spent on architecture before the skeleton runs is an hour spent guessing.

---

## Phase 3 — Default architecture (start here, deviate only with a reason)

**One process. One database. Server-rendered where possible. Boring stack.**

| Decision | Default | Deviate when |
|---|---|---|
| Structure | **Modular monolith** — one deployable, clear internal module boundaries | Never at the start. Genuinely never. |
| Database | **One Postgres** | You have a measured need another store solves |
| State | **In the database** | You have measured that it's the bottleneck |
| Async work | **A table + a worker loop** | Volume actually justifies a broker |
| Auth | **A library, or the platform's** | Never roll your own |
| API | **REST + JSON** | A client genuinely needs graph queries or streaming |
| Frontend | **The framework's default** rendering mode | You have a specific measured reason |

**Modules over services.** Draw boundaries as directories with clear interfaces inside one
deployable. You get the design benefit of separation without distributed-systems tax —
network failure, versioning, tracing, deploy ordering. If a module later needs to be a
service, a well-bounded module extracts cleanly. A premature service almost never merges
back.

**The one place to spend real design effort: the data model.** Everything else is a
two-way door. Schema shape is the one-way door — it outlives every framework choice you
make around it, and migrations get more expensive every month. Get the entities and their
relationships right; be sloppy elsewhere if you must.

---

## Phase 4 — Contracts

Even solo, write the contracts down before implementing. They're how the pieces stay
compatible, and they're what `/slice` hands to parallel worktrees.

**Data contract (highest value):** entities, relationships, what's required vs optional,
what's unique, what cascades on delete. Put constraints **in the database** — `NOT NULL`,
`UNIQUE`, foreign keys, `CHECK`. A DB constraint is one line and cannot be bypassed;
app-layer validation is many lines and gets bypassed by the next code path.

**API contract:** request/response shapes verbatim, every error with its code, idempotency
stated explicitly. Version from day one — a `/v1/` prefix costs nothing now and is
miserable to retrofit.

**Module contract:** what each module exposes and what it may import. Write the import
rule down; without it, "modular monolith" degrades into a normal monolith in about six
weeks.

---

## Phase 5 — Ponytail at project scale

The ladder applies to whole subsystems, not just functions. At project scale rung 1 —
*does this need to exist at all?* — is worth the most, because you are deciding whether to
own a thing forever.

**Defer all of these until something actually hurts:**

microservices · message queues · caching layers · custom auth · GraphQL · event sourcing ·
CQRS · feature-flag services · multi-tenancy · i18n framework · plugin architecture ·
custom design systems · Kubernetes · monorepo tooling · a second database

Every one of them is a real answer to a real problem you probably do not have yet. Adding
one before the problem arrives means you pay the cost with none of the benefit, and you
usually shape the codebase around a guess.

**Never defer:** input validation at trust boundaries, auth on anything non-public,
database constraints, backups you have actually restored from once, error handling that
prevents data loss, accessibility basics. These are not premature — they are the things
that are brutal to retrofit and cheap to start with.

---

## Phase 6 — What "done" looks like for the architecture

- The walking skeleton is deployed and reachable
- The data model is written down with constraints in the DB
- API contracts exist for anything crossing a boundary
- Module boundaries and import rules are written down
- One ADR per non-obvious choice, especially every deviation from the defaults above
- Written back to the brain per `CONVENTIONS.md` §5

Then `/slice`. Greenfield slices well — with no existing code, file ownership collisions
are rare and wave 1 can be unusually wide.

---

## When to add structure later

Add it on evidence, not anticipation:

| Add | When |
|---|---|
| A cache | you measured the slow query |
| A queue | the request is actually timing out |
| A service | a module has a genuinely different scaling or deploy cadence |
| A second DB | the access pattern is truly wrong for Postgres |
| Abstraction | you have **three** real cases, not two |

Three, not two. Two cases look like a pattern and usually aren't; the abstraction you
build from two is nearly always wrong in the way the third reveals.

## The greenfield failure modes

| Symptom | Root cause |
|---|---|
| Week three, nothing deployed | designed before the walking skeleton |
| Microservices with one user | deviated from the monolith default without evidence |
| Painful migration in month two | data model rushed; it was the one-way door |
| Abstractions that fit nothing | built from two cases instead of three |
| "Why did we choose this?" | no ADRs — greenfield decisions are the ones most worth recording, and the easiest to skip because it all feels obvious at the time |

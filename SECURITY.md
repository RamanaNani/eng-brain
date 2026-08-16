# Security Policy

## Reporting a vulnerability

**Do not open a public GitHub issue for a security vulnerability.**

Report it privately through GitHub's [Security Advisories](https://github.com/RamanaNani/eng-brain/security/advisories/new)
("Report a vulnerability" on the Security tab). Include:

- what the issue is and where (file, skill, or gate),
- how to reproduce it,
- the impact you see.

You will get an acknowledgement within a few days. Once a fix is out, we are glad to credit you
in the advisory unless you would rather stay anonymous.

## What is in scope

eng-brain runs on your machine and drives your tools, so the sensitive surfaces are:

- **The gate scripts** (`skills/_eng-brain/bin/*.py`) — a bug that makes a gate report a false
  green is a security-relevant defect, because the whole system's safety rests on the gates
  being honest.
- **The `/pentest` skill and `security-tester` agent** — these run scanners. They are
  **authorized-targets-only** by design: `engagement.md` scope is read first and out-of-scope
  hosts are refused, no destructive payloads are ever run. A way to make them touch a host the
  scope does not authorise is in scope for this policy.
- **The install/sync scripts** (`install.sh`, `hooks/sync.sh`, `check-upstream.sh`) — anything
  that could make them write outside their intended targets or run untrusted code.

## What is not a vulnerability here

- **The brain stores a Postgres password in plaintext** at `~/.gbrain/config.json`. This is
  gbrain's design, documented, and the reason [SETUP.md](docs/SETUP.md) says to keep `~/.gbrain/`
  out of any backup that leaves your machine. Treat that directory as a secret; it is not a
  defect in this repo.
- **The pipeline will not merge for you.** That is intentional — `/pr` opens a PR and a human
  merges. "It didn't auto-merge" is the feature working.

## A note on the pentest tooling

`/pentest` vendors nothing at rest — Strix's Apache-2.0 playbooks are fetched at runtime and
kept out of this MIT distribution. It is a defensive and authorized-testing tool. Using it
against systems you do not own or are not authorised to test is your responsibility and outside
the scope this project supports.

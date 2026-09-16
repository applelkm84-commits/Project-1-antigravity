# Release proof and counterfactual review

`antigravity-proof` turns the evidence already collected by Antigravity into a review artifact. It is intentionally different from a release button: it does not publish anything, run deployment commands, or claim that green evidence guarantees correctness.

## Why this exists

Coding agents can produce a convincing completion summary even when the underlying evidence is weak. Common failure modes include:

- a test passed before requirements or decisions changed;
- a green test never exercised the failing path;
- an external assumption expired after the implementation was written;
- a small task grew into a broad diff while all unit tests remained green;
- reviewers see individual checks but cannot reconstruct which approvals, decisions, assumptions, leases, and scope controls were active at review time;
- reproduction instructions accidentally copy credentials or secret-bearing notes.

The proof layer makes those gaps visible in one artifact.

## Build a release proof

```bash
antigravity-proof bundle <task-id>
```

Write both machine-readable and human-readable artifacts:

```bash
antigravity-proof bundle <task-id> \
  --json-out .antigravity/proofs/release.json \
  --markdown-out .antigravity/proofs/release.md
```

Use another Git base for the blast-radius audit when needed:

```bash
antigravity-proof bundle <task-id> --base origin/main
```

A non-ready proof exits non-zero. The output still exists when output paths are supplied, so CI or a reviewer can inspect why it failed.

## What the proof contains

A proof snapshot includes:

- objective, acceptance criteria, status, and dependency readiness;
- current settled decisions;
- active exact-scope approval receipts;
- active lease and lease history;
- active and expired assumptions;
- protected invariants;
- the latest result for each named verification check;
- the age and freshness status of each latest verification result;
- the current local Git blast-radius audit;
- reality-check blockers and evidence debt;
- current coordination fingerprint and Git HEAD;
- a deterministic proof digest over the evidence snapshot.

The proof deliberately separates **recorded evidence** from **claims**. Missing verification remains evidence debt. A failed or skipped latest check cannot become green because some older run passed.

## Evidence freshness

Each latest verification result receives an age and a freshness classification.

A result becomes stale when Antigravity can see a relevant event after the check, such as a new review finding, settled decision, assumption, invariant, change-policy update, or a later modification time on a currently changed file. This is conservative: it is designed to stop old green evidence from silently surviving a changed task context.

Freshness is not a cryptographic proof that source code was unchanged. The proof also records Git HEAD and the live scope audit so reviewers can compare repository state explicitly.

## Counterfactual review

```bash
antigravity-proof counterfactual <task-id>
```

or:

```bash
antigravity-proof counterfactual <task-id> --output counterfactual-review.md
```

This does not ask another agent to repeat the green tests. It asks the reviewer to assume the green evidence is truthful and then search for ways the release could **still** be wrong.

The prompt attacks seven classes of false confidence:

1. false-green or mis-specified tests;
2. missing negative/edge cases;
3. incorrect or expired external assumptions;
4. trust-boundary and security blind spots;
5. migration, replay, partial-write, and rollback risk;
6. scope drift or invariant violations;
7. stale decisions, approvals, dependency state, or other coordination context.

Each hypothesis must be falsifiable and include the cheapest test or observation that could disprove it. This turns review into a pre-mortem instead of another confidence summary.

## Minimal reproducibility recipe

```bash
antigravity-proof repro <task-id>
antigravity-proof repro <task-id> --json --output repro.json
```

The recipe includes the objective, acceptance criteria, changed paths, non-secret assumption names/sources, invariants, recorded verification commands, Git HEAD, and a short sequence for reproducing the evidence in an isolated checkout.

It intentionally does **not** export assumption values into the recipe. It also redacts common secret-bearing assignments and credential/token formats such as API keys, bearer tokens, GitHub tokens, AWS access-key-like strings, passwords, cookies, and credential/private-key fields.

Redaction is defense in depth, not a substitute for keeping secrets out of task descriptions and Git history.

## Proof digest

`proof_digest` is a SHA-256 digest of the proof evidence snapshot excluding the generation timestamp and digest field itself. It makes it easy to notice when two proof artifacts represent different evidence, even if their presentation is similar.

It is not a signature and does not establish author identity.

## Limits

A release proof can only reason over information Antigravity can observe and records that humans or agents actually supplied. It cannot prove that:

- a test command was honest or comprehensive;
- an approval receipt corresponds to an organization's real permission model;
- a protected invariant is complete;
- a secret never existed in source control;
- an unrecorded manual action occurred;
- a deployment environment matches the local repository.

Use the proof as a compact evidence package for human or automated review, not as an authorization system or correctness certificate.

# Dev Workflow — WhatsApp Chat Exporter

Repo: `Dhyuthidhar2404/Whatsapp_Export` · 21 labeled issues in the Backlog.

This document defines how implementation runs: the branching model, the one-PR-per-issue process, and the kickoff prompt to paste into Claude Code.

---

## Branching model

- **`main`** — always green and releasable. No direct commits. Protected (see below).
- **One branch per issue**, branched from an up-to-date `main`:
  `<type>/<issue#>-<slug>` where `type` ∈ `feat | fix | chore | test | ci`.
- **One PR per issue**, merged back to `main` with a **squash merge**, then the branch is deleted.
- A solo `develop` integration branch is **not** used — it adds ceremony with no benefit for one developer. PR straight to `main`.

**Dependencies:** issues are dependency-ordered (Phase 0 → 6). Do not start an issue whose prerequisites aren't merged to `main` yet. Branch each new issue from `main` *after* the prerequisite PR is merged, so you never stack unmerged work. Hard dependency to remember: **#13 (crypt15 fixture + pinned deps) must merge before #14 (decrypt/export)** — #14's Done criteria can't pass without the fixture.

**Branch protection (set once on GitHub):** require PR review (self-review is fine solo) and require the CI check to pass before merge. CI arrives in #21 — see the note in the prompt about pulling its skeleton forward.

### Branch name per issue

| # | Branch |
|---|---|
| 1 | `chore/1-package-scaffold` |
| 2 | `feat/2-error-hierarchy` |
| 3 | `feat/3-run-context` |
| 4 | `feat/4-logging-redaction` |
| 5 | `feat/5-key-normalize` |
| 6 | `feat/6-key-input` |
| 7 | `feat/7-env-preflight` |
| 8 | `feat/8-adb-version-floor` |
| 9 | `feat/9-device-selection` |
| 10 | `feat/10-adb-wrapper-paths` |
| 11 | `feat/11-pull-backup` |
| 12 | `feat/12-pull-media` |
| 13 | `chore/13-crypt15-fixture-deps` |
| 14 | `feat/14-decrypt-export` |
| 15 | `feat/15-format-flags` |
| 16 | `feat/16-vcard-enrichment` |
| 17 | `feat/17-contacts-csv` |
| 18 | `feat/18-package-zip` |
| 19 | `feat/19-run-export-facade` |
| 20 | `feat/20-cli-shell` |
| 21 | `ci/21-safety-gate-ci` |

## Per-issue loop

1. `git switch main && git pull`
2. `git switch -c <branch>` for the issue.
3. Implement the issue **plus its tests** (tests are part of the work, not a follow-up).
4. Run unit tests and the safety gate locally; all green.
5. Commit with a conventional message ending in `Refs #<n>` (or `Closes #<n>` on the final commit).
6. `git push -u origin <branch>` and open a PR whose body pastes the issue's **Done** checklist and ticks each item, ending with `Closes #<n>`.
7. Ensure CI is green, self-review the diff, squash-merge, delete the branch.
8. Move to the next issue in order.

**Commit format:** `type(scope): summary` — e.g. `feat(key-handling): add normalize() with strict 64-hex validation`.

---

## Kickoff prompt for Claude Code

> Paste everything in the box below into Claude Code at the repo root.

```text
You are implementing the WhatsApp Chat Exporter. Before writing any code, read these
files in the repo and treat them as binding:
- CLAUDE.md and .claude/rules/architecture.md  (the rules — non-negotiable)
- SPEC.md                                        (full spec; §6 is the CLI contract)
- docs/architecture.md and docs/interface-contract.md  (module signatures + data flow)
- tasks.md                                       (the 21 tasks, in execution order)
- the open GitHub issues (gh issue list)         (one issue per task; respect labels)

Workflow — follow exactly:
- Work ONE issue at a time, in execution order (issues #1 → #21). Do not start an issue
  whose dependencies are not yet merged to main. Note: #13 (crypt15 fixture + pinned
  deps) must be merged before #14.
- For each issue: branch from an up-to-date main using the naming
  `<type>/<issue#>-<slug>` (type ∈ feat|fix|chore|test|ci); implement the code AND its
  tests together; run the unit tests and the safety gate locally until green; commit with
  conventional messages; push; open a PR whose body reproduces the issue's Done checklist
  with every box ticked and ends with `Closes #<issue-number>`.
- One PR per issue. Never bundle multiple issues into one PR or one branch.
- After opening each PR, STOP and summarize what you did and the test results. Wait for
  me to review and merge before you start the next issue. (We can speed up to whole-phase
  batches once Phase 0 is merged and the pattern is proven.)

Architecture rules you must honor in every issue (from .claude/rules/architecture.md):
- No network anywhere. No http/socket/requests/urllib imports in wae/ or export.py.
- The key lives only in keyutil and decrypt_export; never in RunContext, never logged,
  printed, or written. RunContext is frozen and holds non-secret config only.
- adb is invoked only from pull.py, read-only — no commands that write to the device.
- No stage imports another stage; the orchestrator wires them via RunContext + returns.
- All decryption/parsing goes through whatsapp-chat-exporter — no custom crypto.
- Errors are raised as WaeError subclasses mapped to exit codes; export.py is a thin
  shell over the run_export facade.
- Temp cleanup + key wipe run via try/finally on every exit path (incl. Ctrl-C → 130).
- Never commit secrets/data: keep the .gitignore entries intact (key, *.crypt15,
  msgstore.db, wa.db, *.vcf, /output/, /.tmp/, *.zip).

Definition of done for an issue = every checkbox in that issue passes, tests included,
the safety gate passes, and the code obeys the rules above. Do not implement anything
listed as Out of Scope in tasks.md / SPEC §9.

Start now with issue #1 (package scaffold + .gitignore). Confirm your plan for #1 in one
short paragraph, then implement it and open the PR.

Optional but recommended: before #1, or as the very first PR, stand up a minimal CI
workflow + the safety_gate.py skeleton (the substance of #21) so every subsequent PR is
checked by CI. If you do this, still track it under #21 and keep that issue's full Done
criteria for the complete version.
```

---

## Notes

- **Why pause after each PR early on:** Phase 0 (#1–#4) is the foundation everything imports; a wrong shape there propagates. Once those are merged and the rhythm is proven, you can let Claude Code run a whole phase before pausing.
- **The CI chicken-and-egg:** `tasks.md` lists the safety gate + CI last (#21), but you want CI green on every PR. The prompt offers to bring a minimal CI + `safety_gate.py` skeleton forward as the first PR. Recommended — otherwise the early PRs have nothing enforcing the no-network / key-hygiene rules except review.
- **The one real unknown** is still #13: confirming a `crypt15` backup decrypts with the 64-hex key using the pinned library, against a current WhatsApp backup. Treat #13 as a spike — if the premise fails there, stop and reassess before building #14 onward.

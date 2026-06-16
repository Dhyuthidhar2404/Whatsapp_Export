# Architectural Decisions of Record

Every decision in `docs/architecture.md` has an entry here; the two stay in sync. Never edit manually — regenerate via tooling if the premise changes.

---

## Orchestrated linear pipeline over a modular package (not an event-bus modular monolith)

**Date:** 2026-06-16
**Decision:** Structure the tool as a thin CLI shell over a six-stage pipes-and-filters pipeline of isolated modules, coordinated by an orchestrator. No event bus.
**Reason:** The flow is fixed and synchronous (env → key → pull → decrypt → contacts → package). A monolithic single script would defeat the security pillars (can't unit-test key validation or statically prove "no network"). An event bus adds ceremony with zero benefit for a linear flow.
**Alternatives considered:** Single monolithic script (rejected — untestable, unauditable); full modular monolith with event bus (rejected — no async events to warrant it); plugin/event-driven (rejected — no extensibility need).
**Agreed by:** Owner (PM + Tech Lead)
**Affects:** All modules; export.py orchestrator
**Linked issue:** —

---

## Package-level Facade `run_export(config) -> Path`; CLI is a thin shell

**Date:** 2026-06-16
**Decision:** A single `run_export` facade runs the whole pipeline and returns the ZIP path. `export.py` only parses flags, builds config, calls the facade, and maps exceptions to exit codes.
**Reason:** Makes the tool importable/programmatic, gives end-to-end tests a clean seam, and keeps the CLI dumb. One facade is the right amount for this size.
**Alternatives considered:** Orchestrator-only with logic in `export.py` (rejected — couples CLI to orchestration, harder to test); facades-in-front-of-facades (rejected — ceremony).
**Agreed by:** Owner (PM + Tech Lead)
**Affects:** export.py; orchestrator; test seams
**Linked issue:** —

---

## Stack: Python 3.9+ with argparse (stdlib), minimal dependencies

**Date:** 2026-06-16
**Decision:** Python 3.9+ CLI using stdlib `argparse`, `zipfile`, `csv`, `subprocess`, `getpass`, `logging`, `dataclasses`.
**Reason:** Identical on macOS and Windows; the exporter library is Python; minimal third-party deps shrink the audit surface (a security property). `argparse` over `click` avoids an added dependency.
**Alternatives considered:** Node/TS (rejected — exporter is Python); compiled language (rejected — overkill, harder cross-platform distribution); `click` (rejected — needless dependency).
**Agreed by:** Owner (PM + Tech Lead)
**Affects:** Whole codebase; requirements.txt
**Linked issue:** —

---

## Use `adb` as an external binary, not a Python adb library

**Date:** 2026-06-16
**Decision:** Shell out to the official `adb` binary (only from the `pull` module).
**Reason:** Official, well-understood, predictable; avoids adding a third-party library that would hold device-access privileges.
**Alternatives considered:** pure-Python adb libs (rejected — extra privileged dependency, less predictable than official tooling).
**Agreed by:** Owner (PM + Tech Lead)
**Affects:** pull module; env_check (adb presence/version)
**Linked issue:** —

---

## Delegate all decryption and parsing to `whatsapp-chat-exporter`; no custom crypto

**Date:** 2026-06-16
**Decision:** All crypt15 decryption and chat parsing go through `whatsapp-chat-exporter`. We write no cryptography.
**Reason:** Mature, audited library; hand-rolled crypto is a liability. Keeps custom code touching the key minimal.
**Alternatives considered:** Custom crypt15 decryptor (rejected — unnecessary risk and effort).
**Agreed by:** Owner (PM + Tech Lead)
**Affects:** decrypt_export module
**Linked issue:** —

---

## No-root, no-downgrade: rely solely on the user's 64-hex E2E backup key

**Date:** 2026-06-16
**Decision:** Decryption uses only the user's 64-hex end-to-end backup key plus scoped-storage files. The `adb backup`/WhatsApp-downgrade key-extraction trick and the rooted `key`-file path are excluded.
**Reason:** The downgrade trick is deprecated and unreliable on modern Android; rooting is invasive. The E2E key path is robust, root-free, and user-controlled.
**Alternatives considered:** `adb backup` downgrade extraction (rejected — deprecated/fragile); rooted `/data/data` key file (rejected — requires root).
**Agreed by:** Owner (PM + Tech Lead)
**Affects:** keyutil; pull; decrypt_export; SECURITY pillar 2
**Linked issue:** —

---

## Contact names come from a user-supplied vCard (not `wa.db`)

**Date:** 2026-06-16
**Decision:** Display names are enriched from an optional `--contacts-vcf`; without it, numbers only. `wa.db` is not pulled.
**Reason:** `wa.db` lives in app-private storage requiring root, which violates the no-root pillar. A vCard is root-free and user-controlled.
**Alternatives considered:** Pull `wa.db` (rejected — needs root); fetch from Google Contacts API (rejected — adds network + auth, violates no-network).
**Agreed by:** Owner (PM + Tech Lead)
**Affects:** decrypt_export (enrichment); contacts module
**Linked issue:** —

---

## Immutable `RunContext`; the key is passed separately, never stored in it

**Date:** 2026-06-16
**Decision:** A frozen `RunContext` dataclass carries non-secret config only. The key is passed as a separate argument to `keyutil` and `decrypt_export` and is never placed in `RunContext`.
**Reason:** A frozen dataclass's default `repr` would print the key; keeping it out makes key-hygiene structural, not just a convention. Immutability preserves explicit pipes-and-filters data flow.
**Alternatives considered:** Key inside the context object (rejected — leak risk via repr/logs); mutable shared state (rejected — hidden coupling).
**Agreed by:** Owner (PM + Tech Lead)
**Affects:** RunContext; orchestrator; keyutil; decrypt_export
**Linked issue:** —

---

## No network, no telemetry (local-only)

**Date:** 2026-06-16
**Decision:** The tool makes no outbound network calls and collects no telemetry. A static test asserts no network/socket/HTTP imports anywhere.
**Reason:** Chats and the key are maximally sensitive; keeping everything local is the core safety guarantee and the project's reason for existing over extensions/cloud tools.
**Alternatives considered:** Optional cloud upload/sync (rejected — violates the central pillar); crash/usage telemetry (rejected — needs network).
**Agreed by:** Owner (PM + Tech Lead)
**Affects:** Whole codebase; safety gate tests
**Linked issue:** —

---

## Typed exception hierarchy bound to exit codes; guaranteed teardown

**Date:** 2026-06-16
**Decision:** `WaeError(message, exit_code)` base with typed subclasses (exit codes 1–5); `KeyboardInterrupt`→130. Temp cleanup and key wipe run via `try/finally` on every exit path.
**Reason:** Binds the documented exit codes to types so they can't drift; guarantees no decrypted data or key residue is left behind, even on Ctrl-C.
**Alternatives considered:** Scattered `sys.exit` calls (rejected — codes drift, no central mapping); best-effort cleanup (rejected — leaves residue on failure paths).
**Agreed by:** Owner (PM + Tech Lead)
**Affects:** Error model; orchestrator teardown; export.py shell
**Linked issue:** —

---

## Internal interface contract in place of an HTTP API contract

**Date:** 2026-06-16
**Decision:** Define and agree an internal module-interface contract (the `run_export` facade, the `RunContext` shape, per-stage function signatures, the data hand-off map, the error contract, and the ZIP output shape) instead of an HTTP API contract, mock file, or designer/Figma contract.
**Reason:** The architecture is a local CLI with no server, no network, no frontend, and no designer, so there is no HTTP surface, no frontend to unblock with a mock, and no screens to design. The genuine pre-implementation contract that lets the six pipeline stages be built in parallel is the interface between modules. Recorded in docs/interface-contract.md.
**Alternatives considered:** Generating REST endpoints / Bearer auth / a mock.json / a designer-contract (rejected — would invent a network architecture that contradicts the no-network pillar and create exactly the kind of mismatch the contract is meant to prevent).
**Agreed by:** Owner (PM + Tech Lead)
**Affects:** All six stage modules; the run_export facade; export.py; SPEC §6
**Linked issue:** —

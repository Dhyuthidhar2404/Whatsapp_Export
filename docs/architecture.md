# Architecture — WhatsApp Chat Exporter (local)

**Status:** Approved · **Date:** 2026-06-16 · **Source:** SPEC.md v1.0, features.md
**Decisions of record:** see DECISIONS.md (every choice below has a matching entry).

---

## 1. System design overview

A single-process, local command-line tool that exports all of a user's WhatsApp chats, media, and a contacts CSV from an Android phone into one ZIP. It reads WhatsApp's encrypted local backup (`msgstore.db.crypt15`), decrypts it locally with the user's own 64-hex end-to-end backup **key**, converts it to human-readable **chats**, and packages the result. No server, no database, no network, no deployment — `git clone` → `pip install` → run.

The five non-negotiable pillars (from the spec) shape every decision: local-only/no-network, no-root/no-downgrade, read-only-on-device, key-never-persisted, crypto-delegated.

## 2. High-Level Design

```
            ┌──────────────────────────────────────────────┐
   user ───▶│ export.py  (thin CLI shell)                   │
  (key)     │   parse flags → build RunContext → run_export │
            └───────────────────┬──────────────────────────┘
                                │  facade: run_export(config) -> Path
                                ▼
            ┌──────────────────────────────────────────────┐
            │ orchestrator (pipeline coordinator)           │
            │  env_check → keyutil → pull → decrypt_export   │
            │            → contacts → package → cleanup      │
            └───┬──────────┬───────────┬───────────┬────────┘
                │          │           │           │
         (adb, read-only)  │      (wtsexporter)    │
                ▼          ▼           ▼           ▼
            [device]  [temp workdir ./.tmp]   [output/ ZIP]
```

Three external actors only: the **device** (read-only, over `adb`), the **filesystem** (ephemeral temp + final output), and the **user** (the key prompt). There is deliberately **no network actor** — its absence is the central security invariant, enforced by a static test.

The package-level **Facade** (`run_export(config) -> Path`) runs the whole pipeline and returns the ZIP path. `export.py` is a thin shell: parse flags, build config, call the facade, map exceptions to exit codes. This keeps the tool importable, gives end-to-end tests a clean seam, and keeps the CLI dumb.

## 3. Low-Level Design

The pipeline is **pipes-and-filters**: each stage is an isolated module with one responsibility and no cross-module imports. The orchestrator passes an immutable `RunContext` (non-secret config) plus each stage's returned values forward. The **key never enters `RunContext`** (a frozen dataclass's `repr` would print it); it is passed as a separate argument only to `keyutil` (produces) and `decrypt_export` (consumes).

| Stage / module | Responsibility | Key internals |
|---|---|---|
| `env_check` | Confirm prerequisites | Python ≥ 3.9; `adb` on PATH; `adb version` floor; exactly one authorized device (else `--device`) |
| `keyutil` | Produce a valid key | `normalize()` strips known noise (Unicode whitespace, zero-width, smart-quotes), strict 64-hex; pure, unit-tested |
| `pull` | Copy backup + media (read-only) | Probe candidate paths (+ `--db-path`/`--media-path`); `adb pull`; 3× retry/linear backoff on transport errors; size-verify backup |
| `decrypt_export` | Backup → chats | Invoke `wtsexporter -a -k <key> -b <crypt15>`; verify exit 0 **and** output exists; map "invalid key" to friendly error; command logged redacted |
| `contacts` | Build contacts CSV | Unique participants; digits-only vCard join; `name,number,source` |
| `package` | Bundle the ZIP | Zip export dir → `whatsapp-export-YYYY-MM-DD.zip`; suffix on collision; pre-check writability/space |
| orchestrator (`run_export`) | Sequence + lifecycle | Stage order, `try/finally` teardown (temp wipe + key wipe), exception→exit-code mapping |

**Error model:** typed hierarchy `WaeError(message, exit_code)` → `EnvError(1)`, `DeviceError(1)`, `InvalidKey(2)`, `NoBackupError(3)`, `DecryptionError(4)`, `PackagingError(5)`; `KeyboardInterrupt`→`130`. The shell catches `WaeError`, prints `.message`, exits `.exit_code`.

**Logging:** one logger; INFO→stdout, DEBUG under `--verbose`. The key is never passed to the logger; a `SecretRedactionFilter` scrubs any 64-hex substring as a backstop. No telemetry.

## 4. Technical architecture (stack, justified)

- **Python 3.9+** — identical on macOS and Windows, the exporter is a Python library, and the stdlib (`zipfile`, `csv`, `subprocess`, `getpass`, `logging`, `dataclasses`) covers nearly everything → minimal dependencies, which is itself a security property.
- **`argparse` (stdlib)** over `click` — no added dependency = smaller audit surface.
- **`whatsapp-chat-exporter`** for all decryption/parsing — never hand-roll crypto.
- **`adb` as an external binary** — the official, well-understood tool; avoids a third-party Python library holding device-access privileges.

## 5. Design patterns in use

| Pattern | Where | Why |
|---|---|---|
| Facade | `run_export()` | One simple entry over the multi-stage subsystem; importable + testable |
| Pipes-and-filters | the stage sequence | Linear, isolated, single-responsibility stages |
| Adapter/wrapper | `pull` (adb), `decrypt_export` (exporter) | Isolate + mock the external/privileged surface |
| Pure function | `keyutil.normalize` | Deterministic, trivially testable core |
| Typed errors + guard clauses | `WaeError` hierarchy | Fail fast; exit codes bound to types |
| Immutable context | `RunContext` | Explicit data flow; no shared mutable state; key kept out by design |

Deliberately **avoided:** an event bus (no async events to warrant it), plugins (no extensibility need), and facades-in-front-of-facades (one facade is enough for a tool this size).

## 6. Module boundaries (ownership)

Strict write-ownership: only `pull` writes pulled files; only `decrypt_export` writes the export dir; only `package` reads it to make the ZIP; only the orchestrator deletes temp. Stages never import one another. `adb` is touched **only** by `pull`. The key is touched **only** by `keyutil` and `decrypt_export`.

## 7. "Database" design

No application database. Three data stores: the phone's encrypted backup (read-only, external), the temp workdir (ephemeral — the only on-disk decrypted data, wiped on every exit path), and the output ZIP. No shared mutable state.

## 8. Deployment strategy

Distribution is `git clone` → `pip install -r requirements.txt` → run; the only environment is the user's local machine. Optional CI: a GitHub Actions workflow running the unit + static-safety tests on push (no real device needed for those). No infrastructure, no servers, no secrets in CI.

## 9. Security approach

The five pillars, plus: `.gitignore` as a first-class control (excludes key, `*.crypt15`, `msgstore.db`, `wa.db`, `*.vcf`, `/output/`, `/.tmp/`, `*.zip`); a static safety gate (no network imports anywhere; key never reaches a log/print sink); structural key-hygiene (key absent from `RunContext`; redaction filter as backstop); and read-only device access (no `adb` write/shell-mutate commands). Full detail in SECURITY.md.

## 10. Monitoring & error handling

No telemetry — by design, since there is no network. "Monitoring" for a local CLI is clear stderr messages and honest non-zero exit codes (`1`–`5`, `130`) the user or CI can act on. Decryption is explicitly verified rather than assumed; deferred edge cases (see SPEC §11) must fail clearly, never degrade silently.

## 11. Known open item

Confirm crypt15 decrypts with the hex key against a *current* WhatsApp backup (the fixture test in build step 4) and pin dependency versions at that point. This is the one premise to validate before building the rest.

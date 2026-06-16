# Tasks — WhatsApp Chat Exporter (local)

**Status:** For PM review (not yet approved) · **Date:** 2026-06-16
**Source:** `docs/features.md` (PQR), `docs/architecture.md`, `CLAUDE.md`
**Scope guard:** No task exists for anything in a Feature's Out-of-Scope list or SPEC §9's out-of-scope list (iPhone, downgrade trick, root/`wa.db`, GUI, cloud, incremental). Deferred edge cases (SPEC §11) appear only as *fail-clearly* Done criteria, never as feature work.

Tasks are listed in **execution order** (dependency-correct). Each carries its `mod:`/`feat:`/priority labels for the GitHub step. 19 tasks across 7 phases.

**Execution order:** Foundations → Key Handling → Readiness → Backup Acquisition → Chat Export → Contacts → Pipeline & Delivery.

---

## Phase 0 — Foundations (Module 0, cross-cutting)

> Parent note: these have no single parent Feature — they are the shared primitives every stage depends on, from `architecture.md` §3/§5/§10 and the `CLAUDE.md` rules. Inherited context is project-level: *the tool must run locally, fail predictably, and never leak the key* (enforces SPEC pillars 1 and 4).

### T0.1 — Create package scaffold and `.gitignore`
- **Parent:** Module 0 Foundations · feat: scaffolding
- **Q:** Create the `wae/` package (`__init__.py`, empty stage modules `env_check.py`, `keyutil.py`, `pull.py`, `decrypt_export.py`, `contacts.py`, `package.py`, `pipeline.py`, plus `context.py`, `errors.py`, `logging_setup.py`), a `tests/` dir, `export.py` at root, and `requirements.txt` (deps unpinned for now — pins resolved in T4.0). Author `.gitignore` with the exact exclude list from CLAUDE.md/SECURITY.md.
- **Inherited P:** "After finishing, the tool … guarantees the key was never written anywhere." **R:** "Leaving decrypted data or a leaked key on disk would defeat the whole local-and-private premise."
- **Done when:**
  - [ ] `import wae` and each submodule imports without error
  - [ ] `.gitignore` excludes `key`, `*.key`, `key.txt`, `*.crypt12/14/15`, `msgstore.db`, `wa.db`, `*.vcf`, `/output/`, `/.tmp/`, `*.zip`, `.env`
  - [ ] `git status` on a dir containing a dummy `key` and `msgstore.db.crypt15` shows neither as committable
- **Labels:** `mod:foundations` `feat:scaffolding` `p0:blocker`

### T0.2 — Typed error hierarchy (`errors.py`)
- **Parent:** Module 0 Foundations · feat: error-model (supports F6.1)
- **Q:** `class WaeError(Exception)` with `__init__(self, message: str, exit_code: int)`. Subclasses with fixed codes: `EnvError`=1, `DeviceError`=1, `InvalidKey`=2, `NoBackupError`=3, `DecryptionError`=4, `PackagingError`=5.
- **Inherited P:** "The user runs one command and the tool walks through every stage, stopping with a clear reason if any stage fails." **R:** "One command and predictable exit codes is exactly the 'push to GitHub, run locally, get a ZIP' experience that defines the project."
- **Done when:**
  - [ ] Each subclass instance exposes the correct `.exit_code`
  - [ ] Unit test asserts all six code mappings
  - [ ] `str(err)` returns the human message with no key material
- **Labels:** `mod:foundations` `feat:error-model` `p0:blocker`

### T0.3 — Immutable `RunContext` + `build_context` (`context.py`)
- **Parent:** Module 0 Foundations · feat: run-context (supports F6.1)
- **Q:** `@dataclass(frozen=True) class RunContext` with non-secret fields only: `output_dir: Path`, `fmt: str`, `include_media: bool`, `contacts_vcf: Path|None`, `device: str|None`, `package: str`, `db_path: str|None`, `media_path: str|None`, `verbose: bool`, `keep_temp: bool`, `tmp_dir: Path`. **No key field.** `build_context(args) -> RunContext` maps an argparse `Namespace` to the dataclass.
- **Inherited P/R:** same as F6.1 (above).
- **Done when:**
  - [ ] Mutating any field raises `FrozenInstanceError`
  - [ ] `repr(ctx)` contains no key/secret (there is no key field by construction)
  - [ ] Unit test: a sample `Namespace` builds the expected `RunContext`
- **Labels:** `mod:foundations` `feat:run-context` `p0:blocker`

### T0.4 — Logging setup + `SecretRedactionFilter` (`logging_setup.py`)
- **Parent:** Module 0 Foundations · feat: logging (supports F6.3)
- **Q:** `setup_logging(verbose: bool) -> Logger` (INFO→stdout default, DEBUG under `--verbose`). `class SecretRedactionFilter(logging.Filter)` whose `filter()` replaces any 64-hex substring in `record.msg`/args with `***`. Attach the filter to the logger by default.
- **Inherited P:** "After finishing, the tool cleans up the working files and guarantees the key was never written anywhere." **R:** same as F6.3.
- **Done when:**
  - [ ] A log call containing a 64-hex string renders as `***` (unit test)
  - [ ] `--verbose` emits DEBUG; default does not
  - [ ] No telemetry/handlers other than stdout/stderr
- **Labels:** `mod:foundations` `feat:logging` `p1:high`

---

## Phase 1 — Key Handling (Module 2)

### T2.1 — `keyutil.normalize` (pure)
- **Parent:** Module 2 Key Handling · F2.2 Key validation & normalization
- **Q:** `normalize(raw: str) -> str`. Strip only known noise (ASCII + Unicode whitespace, zero-width `U+200B–U+200D`/`U+FEFF`, wrapping smart-quotes/`'"\``), lowercase, then require exactly 64 hex chars else raise `InvalidKey`. Do not strip arbitrary characters.
- **Inherited P:** "The tool checks the key looks right before using it, so a typo fails clearly instead of producing junk." **R:** "A silent wrong key would yield an empty or corrupt export with no explanation; early validation makes failures legible."
- **Done when:**
  - [ ] 64-hex with spaces / uppercase / wrapping quotes / zero-width chars → normalized 64-char lowercase
  - [ ] 63 chars, non-hex char, or empty → raises `InvalidKey` (exit 2)
  - [ ] The raw/normalized key never appears in any raised message
- **Labels:** `mod:key-handling` `feat:key-validation` `p0:blocker`

### T2.2 — `keyutil.get_key` (input)
- **Parent:** Module 2 Key Handling · F2.1 Key input
- **Q:** `get_key(key_file: Path|None) -> str`. If `key_file` given, read its contents; else prompt via `getpass.getpass` (no echo). Pass through `normalize`. Never echo, log, print, or write the value. Returned only to the caller (the orchestrator), held in a local, not in `RunContext`.
- **Inherited P:** "The tool asks for the user's 64-digit key privately, or reads it from a file they point to, and never stores it." **R:** "The key unlocks the user's entire chat history; mishandling it is the single biggest risk this tool carries."
- **Done when:**
  - [ ] No flag → no-echo interactive prompt returns a normalized key
  - [ ] `--key-file` path → reads and normalizes from file
  - [ ] Static check: the key variable is never passed to `print`/`logging`
- **Labels:** `mod:key-handling` `feat:key-input` `p0:blocker`

---

## Phase 2 — Readiness & Device Connection (Module 1)

### T1.1 — Environment preflight (`env_check.check_python`, `check_adb`)
- **Parent:** Module 1 Readiness · F1.1 Environment preflight
- **Q:** `check_python()` raises `EnvError` if `sys.version_info < (3,9)`. `check_adb()` uses `shutil.which("adb")`; if absent raise `EnvError` with install guidance + the network-settings note.
- **Inherited P:** "Before doing anything, the tool checks that the computer has what it needs and tells the user exactly what's missing if not." **R:** "A failed run halfway through is confusing and can leave temp data around; failing fast at the gate keeps the tool trustworthy and predictable."
- **Done when:**
  - [ ] Python < 3.9 → `EnvError` (exit 1) with version message
  - [ ] `adb` absent → `EnvError` (exit 1) naming adb + install guidance
  - [ ] Both present → returns cleanly
- **Labels:** `mod:readiness` `feat:env-preflight` `p1:high`

### T1.2 — adb version floor (`env_check.check_adb_version`)
- **Parent:** Module 1 Readiness · F1.1 Environment preflight
- **Q:** Run `adb version` (read-only), parse the version, warn (not raise) if below a known-good minimum. Unparseable output → warn and continue.
- **Inherited P/R:** same as F1.1.
- **Done when:**
  - [ ] Below-minimum version logs a warning, does not abort
  - [ ] Unparseable/odd output handled without crashing
- **Labels:** `mod:readiness` `feat:env-preflight` `p2:normal`

### T1.3 — Device selection (`env_check.select_device`)
- **Parent:** Module 1 Readiness · F1.2 Device detection & selection
- **Q:** `select_device(requested: str|None) -> str`. Parse `adb devices`. 0 authorized → `DeviceError` instructing connect + enable USB debugging + accept the on-phone dialog. Exactly 1 → return it. >1 without `requested` → `DeviceError` listing serials. `unauthorized` state → message to accept the phone dialog.
- **Inherited P:** "The tool finds the connected phone; if none or several are connected, it guides the user instead of guessing." **R:** "Pulling from the wrong or an unauthorized device would silently produce someone else's or no data; explicit selection prevents that."
- **Done when:**
  - [ ] One authorized device → returned automatically
  - [ ] Zero → `DeviceError` (exit 1) with connect/authorize guidance
  - [ ] Multiple without `--device` → `DeviceError` listing serials
  - [ ] `unauthorized` → message tells user to accept the phone dialog
- **Labels:** `mod:readiness` `feat:device-selection` `p1:high`

---

## Phase 3 — Backup Acquisition (Module 3)

### T3.1 — adb wrapper + path resolution (`pull.adb`, `pull.resolve_paths`)
- **Parent:** Module 3 Backup Acquisition · F3.1 Pull encrypted backup
- **Q:** `adb(args, serial, read_only=True)` subprocess wrapper that forbids known write verbs (`push`, `install`, `rm`, `mv`, etc.). `resolve_paths(ctx, serial) -> (db_remote, media_remote)`: probe candidate paths (default `/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/{Databases,Media}`, then known OEM variants) via read-only `adb shell ls`; honor `--db-path`/`--media-path`/`--package`. None found → `NoBackupError`.
- **Inherited P:** "The tool copies the phone's latest WhatsApp backup file to the computer and tells the user how old it is." **R:** "The export is only as complete as the last backup; surfacing freshness prevents the user mistaking a stale export for a current one."
- **Done when:**
  - [ ] Default path resolves on a standard device
  - [ ] OEM fallback path resolves when default missing
  - [ ] `--db-path`/`--media-path`/`--package com.whatsapp.w4b` overrides honored
  - [ ] No candidate found → `NoBackupError` (exit 3) with Back-Up guidance
  - [ ] `adb()` rejects any write verb (unit test)
- **Labels:** `mod:backup-acquisition` `feat:pull-backup` `p1:high`

### T3.2 — Pull backup with retry + integrity + freshness (`pull.pull_backup`)
- **Parent:** Module 3 Backup Acquisition · F3.1 Pull encrypted backup
- **Q:** `adb pull` the crypt15 into `ctx.tmp_dir`; 3 attempts, linear backoff (2s, 4s) on transport errors only (never on file-not-found). Verify local size == remote size (`adb shell stat`); mismatch → retry. Report file mtime; if mtime within ~30s, warn it may still be writing and offer wait/abort.
- **Inherited P/R:** same as F3.1.
- **Done when:**
  - [ ] Successful pull lands the file in temp; mtime printed as freshness
  - [ ] Simulated transport error retries up to 3× then `DeviceError` (exit 1)
  - [ ] Size mismatch (partial) treated as failure → retried
  - [ ] mtime < 30s → mid-write warning shown
- **Labels:** `mod:backup-acquisition` `feat:pull-backup` `p1:high`

### T3.3 — Pull media with disk guard + skip-warn (`pull.pull_media`)
- **Parent:** Module 3 Backup Acquisition · F3.2 Pull media + disk-space guard
- **Q:** Unless `ctx.include_media is False`, estimate remote media size (`adb shell du -s`, read-only), compare to local free space, warn + offer abort if insufficient. `adb pull` the media tree; continue past individual unreadable files, collecting a skipped-files summary. Pull permission error (locked phone) → message to unlock and retry.
- **Inherited P:** "By default the tool also copies all photos/videos/voice notes, warning first if the computer might not have room." **R:** "Media is what makes the export feel complete; the disk guard stops a multi-GB pull from filling the user's drive mid-run."
- **Done when:**
  - [ ] Default run pulls the full media tree into temp
  - [ ] `--no-media` skips media entirely
  - [ ] Insufficient free space → warning + abort option before pulling
  - [ ] Unreadable files skipped with a summary, run continues
- **Labels:** `mod:backup-acquisition` `feat:pull-media` `p1:high`

---

## Phase 4 — Chat Export (Module 4)

### T4.0 — Obtain crypt15 test fixture + key; pin dependencies
- **Parent:** Module 4 Chat Export · F4.1 Decrypt + export chats
- **Q:** Produce a small known-good `msgstore.db.crypt15` fixture + its 64-hex key (from a throwaway/test account), commit it to `tests/fixtures/` (gitignored from the *secret* rules but allowed as a deliberate test asset — store the key in the test, not in a `key` file). Pin `whatsapp-chat-exporter`, `pycryptodome`, `javaobj-py3` to the latest stable and confirm crypt15-with-hex-key decrypts the fixture. **This resolves the one open premise.**
- **Inherited P:** "The tool turns the locked backup into readable, browsable chats the user can open in a browser." **R:** "Browsable, complete chats with no per-chat cap is the core reason the tool exists over WhatsApp's built-in export."
- **Done when:**
  - [ ] Fixture decrypts with the pinned library and known key
  - [ ] `requirements.txt` pins exact versions confirmed to work
  - [ ] Fixture/key handling does not violate the secret-commit rules
- **Labels:** `mod:chat-export` `feat:decrypt-export` `p0:blocker`

### T4.1 — `decrypt_export.detect_format` + `export_chats` (HTML default)
- **Parent:** Module 4 Chat Export · F4.1 Decrypt + export chats (+ F4.3 verification)
- **Q:** `detect_format(db_path)` → raise `DecryptionError` with clear message for legacy crypt12/14. `export_chats(db_path, media_dir, key, ctx) -> Path` builds `wtsexporter -a -k <key> -b <crypt15>` with media path and `ctx.fmt` (default `html`); log the command with the key replaced by `***`. Success only if exit 0 **and** expected output files exist, else `DecryptionError`; leave no partial output on failure.
- **Inherited P (F4.1):** as T4.0. **Plus F4.3 P:** "If the key doesn't match the backup, the tool says so plainly instead of producing an empty result." **R (F4.3):** "A silent empty export after a wrong key is the most confusing failure mode; loud verification protects trust in the tool."
- **Done when:**
  - [ ] Fixture + correct key → browsable `index.html`, expected chat count
  - [ ] Wrong key → `DecryptionError` (exit 4), no partial output left behind
  - [ ] Legacy crypt12/14 → clear failure pointing to re-creating an E2E backup
  - [ ] Logged command shows `***`, never the key
- **Labels:** `mod:chat-export` `feat:decrypt-export` `p0:blocker`

### T4.2 — Format flag passthrough (json / txt)
- **Parent:** Module 4 Chat Export · F4.1 Decrypt + export chats
- **Q:** Wire `ctx.fmt` ∈ {html, json, txt} into the exporter invocation.
- **Inherited P/R:** same as F4.1.
- **Done when:**
  - [ ] `--format json` produces JSON output
  - [ ] `--format txt` produces text output
  - [ ] Default remains browsable HTML
- **Labels:** `mod:chat-export` `feat:decrypt-export` `p2:normal`

### T4.3 — vCard name enrichment
- **Parent:** Module 4 Chat Export · F4.2 Contact-name enrichment from vCard
- **Q:** When `ctx.contacts_vcf` set, pass `--enrich-from-vcards <path>` to the exporter; numbers normalized to digits-only before matching. Without a vCard, chats render with numbers.
- **Inherited P:** "If the user supplies their contacts file, chats show people's names instead of bare phone numbers." **R:** "Numbers-only chats are hard to read; names make the export genuinely usable, while staying root-free."
- **Done when:**
  - [ ] With a vCard, a known number renders as its name in chats
  - [ ] Without a vCard, chats render numbers with no crash
  - [ ] `+91 98xxx` matches `9198xxx@s.whatsapp.net` (digits-only)
- **Labels:** `mod:chat-export` `feat:vcard-enrichment` `p1:high`

---

## Phase 5 — Contacts Export (Module 5)

### T5.1 — Contacts CSV generation (`contacts.*`)
- **Parent:** Module 5 Contacts Export · F5.1 Contacts CSV generation
- **Q:** `extract_participants(export_dir) -> set` (incl. group members), `parse_vcard(path) -> dict`, `normalize_number(n) -> str` (strip `+`/spaces/dashes), `write_contacts_csv(participants, vmap, export_dir) -> Path` with columns `name,number,source` (`source` ∈ `vcard|number-only`), UTF-8.
- **Inherited P:** "Alongside the chats, the tool writes a spreadsheet-friendly list of everyone the user has chatted with." **R:** "A portable contacts list is a concrete deliverable the user asked for and is useful independent of the chats."
- **Done when:**
  - [ ] `contacts.csv` lists each unique participant exactly once
  - [ ] With a vCard, matched rows carry the name and `source=vcard`
  - [ ] Without a vCard, rows are numbers with `source=number-only`
  - [ ] Non-ASCII names written correctly (UTF-8)
- **Labels:** `mod:contacts-export` `feat:contacts-csv` `p2:normal`

---

## Phase 6 — Pipeline & Delivery (Module 6)

### T6.1 — `package.make_zip` + writability/space check
- **Parent:** Module 6 Pipeline & Delivery · F6.2 Packaging to ZIP
- **Q:** `check_output_writable(output_dir)` (raise `PackagingError` if unwritable / insufficient space). `make_zip(export_dir, output_dir) -> Path` → `whatsapp-export-YYYY-MM-DD.zip`; on same-day collision suffix `-2`, `-3`, …; `index.html` and `contacts.csv` at the ZIP root.
- **Inherited P:** "The finished export is bundled into a single dated ZIP that never silently overwrites an earlier one." **R:** "A single self-contained ZIP is the concrete artifact the user takes away; non-overwrite protects earlier exports."
- **Done when:**
  - [ ] Output is one ZIP at the documented path
  - [ ] Opening `index.html` browses all chats; `contacts.csv` present at root
  - [ ] Second same-day run yields `…-2.zip`, never overwrites
  - [ ] Unwritable dir / no space → `PackagingError` (exit 5)
- **Labels:** `mod:pipeline-delivery` `feat:packaging` `p1:high`

### T6.2 — `run_export` facade + orchestrator + teardown (`pipeline.py`)
- **Parent:** Module 6 Pipeline & Delivery · F6.1 CLI orchestration (+ F6.3 teardown)
- **Q:** `run_export(ctx: RunContext, key: str) -> Path` sequences env_check → pull → decrypt_export → contacts → package, passing `ctx` + returned values forward and `key` only to `export_chats`. Wrap in `try/finally`: delete `ctx.tmp_dir` unless `ctx.keep_temp`, and drop the key reference. Catch `KeyboardInterrupt` so teardown still runs.
- **Inherited P (F6.1):** "The user runs one command and the tool walks through every stage, stopping with a clear reason if any stage fails." **R:** "One command and predictable exit codes is exactly the … experience that defines the project." **Plus F6.3** key-hygiene/teardown.
- **Done when:**
  - [ ] Happy path runs all stages and returns the ZIP `Path`
  - [ ] Any stage `WaeError` propagates with its code; temp still cleaned
  - [ ] Simulated Ctrl-C → temp removed, no key/`*.crypt15` residue
  - [ ] `--keep-temp` preserves temp; default removes it
- **Labels:** `mod:pipeline-delivery` `feat:orchestration` `p0:blocker`

### T6.3 — `export.py` thin CLI shell
- **Parent:** Module 6 Pipeline & Delivery · F6.1 CLI orchestration
- **Q:** argparse for all flags (`--output-dir`, `--format`, `--no-media`, `--contacts-vcf`, `--key-file`, `--device`, `--package`, `--db-path`, `--media-path`, `--verbose`, `--keep-temp`). Build `RunContext`, call `get_key`, call `run_export`, map `WaeError → .exit_code` (print `.message`) and `KeyboardInterrupt → 130`, print final ZIP path. No business logic, no adb, no crypto here.
- **Inherited P/R:** same as F6.1.
- **Done when:**
  - [ ] All documented flags parse and take effect
  - [ ] Each `WaeError` exits with its specified code + message
  - [ ] `KeyboardInterrupt` exits `130`
  - [ ] Happy path runs end to end unattended after the key prompt
- **Labels:** `mod:pipeline-delivery` `feat:orchestration` `p0:blocker`

### T6.4 — Safety-gate script + CI workflow
- **Parent:** Module 6 Pipeline & Delivery · F6.3 Temp cleanup & key-hygiene guarantee
- **Q:** A `scripts/safety_gate.py` that statically asserts: no network/socket/HTTP imports anywhere in `wae/`/`export.py`; the key variable is never passed to `print`/`logging`; `.gitignore` contains every required pattern. A GitHub Actions workflow runs unit tests + the safety gate on push (no device needed).
- **Inherited P:** "After finishing, the tool cleans up the working files and guarantees the key was never written anywhere." **R:** "Leaving decrypted data or a leaked key on disk would defeat the whole local-and-private premise; this feature enforces pillars 1 and 4."
- **Done when:**
  - [ ] Safety gate fails the build on any network import
  - [ ] Safety gate fails on any key→log/print path
  - [ ] Safety gate fails if a required `.gitignore` entry is missing
  - [ ] CI runs unit + safety gate on push and blocks on failure
- **Labels:** `mod:pipeline-delivery` `feat:key-hygiene` `p1:high`

---

## Summary

| Phase | Module | Tasks | Blockers (p0) |
|---|---|---|---|
| 0 | Foundations | T0.1–T0.4 | 3 |
| 1 | Key Handling | T2.1–T2.2 | 2 |
| 2 | Readiness | T1.1–T1.3 | 0 |
| 3 | Backup Acquisition | T3.1–T3.3 | 0 |
| 4 | Chat Export | T4.0–T4.3 | 2 |
| 5 | Contacts Export | T5.1 | 0 |
| 6 | Pipeline & Delivery | T6.1–T6.4 | 2 |

**19 tasks total · 9 p0 blockers.** Tests are embedded in each task's Done criteria, not separated. The single open premise (crypt15 + hex key against a current backup) is resolved by T4.0 before the rest of Chat Export proceeds.

---

**docs/tasks.md is ready for PM review. GitHub Issues will be created only after the PM has approved this document.**

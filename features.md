# Features (PQR Breakdown) — WhatsApp Chat Exporter (local)

**Source of truth:** `SPEC.md` v1.0 (used in place of `architecture.md` + PRD).
**Reviewer:** you (acting as both PM and Tech Lead).
**Rule:** anything not in an Out-of-Scope list below, and not in the spec, is a Change Request.

---

## Shared Metaphor (locked vocabulary)

These exact terms travel through every layer — flags, function names, output files, docs. They do not change without a DECISIONS.md entry.

| Term | Meaning | Never call it |
|---|---|---|
| **key** | the 64-hex (32-byte) E2E backup key | password, passphrase, secret |
| **encrypted backup** | `msgstore.db.crypt15` pulled from the phone | dump, db file, export |
| **chats** | the decrypted, human-readable conversations | messages-export, logs |
| **media** | photos/videos/voice/docs from the WhatsApp Media dir | attachments, files |
| **contacts CSV** | `contacts.csv` of participants | address book, contact dump |
| **export** | the final readable output (chats + media + contacts CSV) | extract, backup |
| **device** | the connected Android phone over adb | handset, target |
| **the ZIP** | `whatsapp-export-YYYY-MM-DD.zip` | archive, bundle, output file |

---

## Module overview

| # | Module | Responsibility (one sentence) | Features |
|---|---|---|---|
| 1 | Readiness & Device Connection | Confirms the tool can run and reach exactly one authorized device. | 2 |
| 2 | Key Handling | Obtains a valid key without ever persisting it. | 2 |
| 3 | Backup Acquisition | Copies the encrypted backup and media off the device read-only. | 2 |
| 4 | Chat Export | Converts the encrypted backup into human-readable chats. | 3 |
| 5 | Contacts Export | Produces a contacts CSV from chat participants. | 1 |
| 6 | Pipeline & Delivery | Runs the full export from one command and delivers the ZIP. | 3 |

Total: 6 modules, 13 features. Honest total effort estimate: **7–10 developer-days** (see per-feature estimates; device + crypto integration carries real friction).

---

## Module 1 — Readiness & Device Connection
*Confirms the tool can run and reach exactly one authorized device.*

### F1.1 — Environment preflight
- **P:** Before doing anything, the tool checks that the computer has what it needs and tells the user exactly what's missing if not.
- **Q:** `wae/env_check.py` verifies Python ≥ 3.9 and that `adb` resolves on PATH (via `shutil.which`). On failure, exits code `1` with an actionable message; the adb-missing message includes install guidance and the network-settings note. No device interaction yet.
- **R:** A failed run halfway through is confusing and can leave temp data around; failing fast at the gate keeps the tool trustworthy and predictable.
- **Done:**
  - ✅ Python < 3.9 → exits `1` with a clear version message
  - ✅ `adb` absent → exits `1` naming adb + how to install
  - ✅ All present → proceeds silently to F1.2
- **Out of scope:** auto-installing adb; bundling platform-tools (Change Request).
- **Effort:** 0.5 day

### F1.2 — Device detection & selection
- **P:** The tool finds the connected phone; if none or several are connected, it guides the user instead of guessing.
- **Q:** Parses `adb devices`. Zero authorized devices → exit `1` instructing the user to connect, enable USB debugging, and accept the on-phone "Allow USB debugging?" dialog. Exactly one → use it. More than one → require `--device SERIAL`, else exit `1` listing serials. Selected serial threads into all later `adb -s SERIAL` calls.
- **R:** Pulling from the wrong or an unauthorized device would silently produce someone else's or no data; explicit selection prevents that.
- **Done:**
  - ✅ One authorized device → auto-selected
  - ✅ Zero → exit `1` with connect/authorize instructions
  - ✅ Multiple without `--device` → exit `1` listing serials
  - ✅ `unauthorized` state → message tells user to accept the phone dialog
- **Out of scope:** wireless/adb-over-Wi-Fi pairing; iOS devices (Change Request).
- **Effort:** 0.5 day

---

## Module 2 — Key Handling
*Obtains a valid key without ever persisting it.*

### F2.1 — Key input
- **P:** The tool asks for the user's 64-digit key privately, or reads it from a file they point to, and never stores it.
- **Q:** If `--key-file PATH` given, read its contents; else prompt via `getpass` (no echo). The value lives only in memory for the process lifetime. The key is never written to disk by the tool, never logged, never printed, never included in error text. (`.gitignore` covers any user-managed key file.)
- **R:** The key unlocks the user's entire chat history; mishandling it is the single biggest risk this tool carries.
- **Done:**
  - ✅ No flag → no-echo interactive prompt
  - ✅ `--key-file` → reads from file
  - ✅ Key never appears in stdout/stderr/logs/any written file (verified by static check)
- **Out of scope:** OS keychain integration; remembering the key between runs (Change Request — would violate pillar 4).
- **Effort:** 0.5 day

### F2.2 — Key validation & normalization
- **P:** The tool checks the key looks right before using it, so a typo fails clearly instead of producing junk.
- **Q:** `wae/keyutil.normalize(raw)` strips spaces/newlines, lowercases, and requires exactly 64 hex chars; otherwise raises `InvalidKey` → exit `2`. Pure function, unit-tested.
- **R:** A silent wrong key would yield an empty or corrupt export with no explanation; early validation makes failures legible.
- **Done:**
  - ✅ 64-hex with spaces/uppercase accepted and normalized
  - ✅ 63 chars, non-hex, or empty → `InvalidKey`, exit `2`
  - ✅ Validation message never echoes the key value
- **Out of scope:** checksum/verifying the key actually matches the backup (that's F4.3, post-decrypt).
- **Effort:** 0.5 day

---

## Module 3 — Backup Acquisition
*Copies the encrypted backup and media off the device read-only.*

### F3.1 — Pull encrypted backup + freshness report
- **P:** The tool copies the phone's latest WhatsApp backup file to the computer and tells the user how old it is.
- **Q:** `wae/pull.py` runs `adb [-s SERIAL] pull /storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Databases/msgstore.db.crypt15` into the temp workdir (`./.tmp/`). Missing file → exit `3` instructing the user to run **Back Up** in WhatsApp. Reports the file's modified timestamp. Read-only: no `adb shell` writes.
- **R:** The export is only as complete as the last backup; surfacing freshness prevents the user mistaking a stale export for a current one.
- **Done:**
  - ✅ Backup present → pulled to temp workdir, mtime printed
  - ✅ Backup absent → exit `3` with the Back-Up instruction
  - ✅ No write operation ever issued to the device
- **Out of scope:** triggering the backup remotely; decrypting crypt12/crypt14 legacy formats (Change Request — fail clearly).
- **Effort:** 1 day (real-device adb friction)

### F3.2 — Pull media + disk-space guard
- **P:** By default the tool also copies all photos/videos/voice notes, warning first if the computer might not have room.
- **Q:** Unless `--no-media`, `adb pull` the `…/WhatsApp/Media/` tree into the temp workdir. Before pulling, estimate remote media size (`adb shell du -s`, read-only) and compare to local free space; warn (and let the user abort) if insufficient.
- **R:** Media is what makes the export feel complete; the disk guard stops a multi-GB pull from filling the user's drive mid-run.
- **Done:**
  - ✅ Default run includes the full media tree in the export
  - ✅ `--no-media` produces a chats-only export
  - ✅ Insufficient free space → warning + abort option before pulling
- **Out of scope:** selective/per-chat media; deduplicating media (Change Request).
- **Effort:** 1 day

---

## Module 4 — Chat Export
*Converts the encrypted backup into human-readable chats.*

### F4.1 — Decrypt + export chats
- **P:** The tool turns the locked backup into readable, browsable chats the user can open in a browser.
- **Q:** `wae/decrypt_export.py` invokes `whatsapp-chat-exporter` (`wtsexporter -a -k <key> -b msgstore.db.crypt15`) with the pulled media path and `--format` (default `html`, also `json`/`txt`). HTML output exposes a browsable `index.html`. Output written to the export dir under the temp workdir.
- **R:** Browsable, complete chats with no per-chat cap is the core reason the tool exists over WhatsApp's built-in export.
- **Done:**
  - ✅ Default run produces browsable HTML with `index.html`
  - ✅ `--format json|txt` produces the respective output
  - ✅ A long chat is complete beyond the ~40k built-in cap (manual QA)
- **Out of scope:** in-tool search/redaction/editing of chats (Change Request).
- **Effort:** 1.5 days

### F4.2 — Contact-name enrichment from vCard
- **P:** If the user supplies their contacts file, chats show people's names instead of bare phone numbers.
- **Q:** When `--contacts-vcf PATH` is given, pass `--enrich-from-vcards` to the exporter. Phone numbers are normalized to digits-only before matching. Without a vCard, chats show numbers (names from `wa.db` are unavailable without root — locked in SPEC §1).
- **R:** Numbers-only chats are hard to read; names make the export genuinely usable, while staying root-free.
- **Done:**
  - ✅ With a vCard, a known number renders as its name in chats
  - ✅ Without a vCard, chats render with numbers and no crash
  - ✅ Number matching normalizes `+91 98xxx` to match `9198xxx@...`
- **Out of scope:** pulling `wa.db` (needs root); fetching contacts from Google directly (Change Request).
- **Effort:** 1 day

### F4.3 — Decryption verification & failure handling
- **P:** If the key doesn't match the backup, the tool says so plainly instead of producing an empty result.
- **Q:** Treat decryption as successful only if the exporter exits `0` **and** expected output files exist. The known "invalid key / inflate" failure maps to exit `4` with a message that the key likely doesn't match this backup. No partial output left behind on failure.
- **R:** A silent empty export after a wrong key is the most confusing failure mode; loud verification protects trust in the tool.
- **Done:**
  - ✅ Correct key → verified success, output present
  - ✅ Wrong key → exit `4`, clear message, no partial files left
  - ✅ Locked with a fixture test (known-good backup + key)
- **Out of scope:** auto-retrying with alternate key formats (Change Request).
- **Effort:** 0.5 day

---

## Module 5 — Contacts Export
*Produces a contacts CSV from chat participants.*

### F5.1 — Contacts CSV generation
- **P:** Alongside the chats, the tool writes a spreadsheet-friendly list of everyone the user has chatted with.
- **Q:** `wae/contacts.py` extracts unique participants (including group members) from the decrypted data, joins to the vCard (digits-only match) when supplied, and writes `contacts.csv` with columns `name,number,source` (`source` ∈ `vcard | number-only`) into the export dir.
- **R:** A portable contacts list is a concrete deliverable the user asked for and is useful independent of the chats.
- **Done:**
  - ✅ `contacts.csv` lists every unique participant exactly once
  - ✅ With a vCard, matched rows carry the name and `source=vcard`
  - ✅ Without a vCard, rows are numbers with `source=number-only`
- **Out of scope:** vCard *output*; profile photos; per-contact message counts (Change Request).
- **Effort:** 1 day

---

## Module 6 — Pipeline & Delivery
*Runs the full export from one command and delivers the ZIP.*

### F6.1 — CLI orchestration & exit codes
- **P:** The user runs one command and the tool walks through every stage, stopping with a clear reason if any stage fails.
- **Q:** `export.py` parses flags (`--output-dir`, `--format`, `--no-media`, `--contacts-vcf`, `--key-file`, `--device`, `--keep-temp`) and runs the pipeline `env_check → key → pull → decrypt_export → contacts → package → cleanup`, mapping each failure to its exit code (`1`–`5`) and an actionable message.
- **R:** One command and predictable exit codes is exactly the "push to GitHub, run locally, get a ZIP" experience that defines the project.
- **Done:**
  - ✅ All documented flags parse and take effect
  - ✅ Each stage failure exits with its specified code + message
  - ✅ Happy path runs end to end unattended after the key prompt
- **Out of scope:** GUI/web UI; config files/profiles (Change Request).
- **Effort:** 1 day

### F6.2 — Packaging to ZIP
- **P:** The finished export is bundled into a single dated ZIP that never silently overwrites an earlier one.
- **Q:** `wae/package.py` zips the export dir to `output/whatsapp-export-YYYY-MM-DD.zip`; if today's file exists, suffix `-2`, `-3`, … `index.html` and `contacts.csv` sit at the ZIP root.
- **R:** A single self-contained ZIP is the concrete artifact the user takes away; non-overwrite protects earlier exports.
- **Done:**
  - ✅ Output is one ZIP at the documented path
  - ✅ Opening `index.html` browses all chats; `contacts.csv` present
  - ✅ Second same-day run yields `…-2.zip`, never overwrites
- **Out of scope:** encrypting the ZIP; splitting into volumes (Change Request).
- **Effort:** 0.5 day

### F6.3 — Temp cleanup & key-hygiene guarantee
- **P:** After finishing, the tool cleans up the working files and guarantees the key was never written anywhere.
- **Q:** On completion (success or handled failure), delete `./.tmp/` unless `--keep-temp`. A safety/static test asserts no network imports exist anywhere and the key variable is never passed to `print`/`logging`. `.gitignore` excludes `*.crypt15`, `msgstore.db`, `wa.db`, `*.vcf`, `key`, `*.key`, `/output/`, `/.tmp/`, `*.zip` from the first commit.
- **R:** Leaving decrypted data or a leaked key on disk would defeat the whole local-and-private premise; this feature enforces pillars 1 and 4.
- **Done:**
  - ✅ Temp workdir removed after a run (unless `--keep-temp`)
  - ✅ Static check: zero network/socket/HTTP usage in the codebase
  - ✅ Static check: key never reaches a log or print sink
  - ✅ `git status` after a run shows no secret/data files committable
- **Out of scope:** secure-wipe/shredding of temp files (Change Request).
- **Effort:** 0.5 day

---

## Review gate

Do not proceed to task breakdown until you've agreed every **Out of Scope** list above — an unagreed boundary becomes a Change Request argument later. One spec-level open item still stands and should be resolved during the first build feature (F4.1/F4.3): pin the dependency versions and confirm crypt15-with-hex-key decrypts a *current* WhatsApp backup via the fixture test.

# WhatsApp Chat Exporter (Local)

**Version:** 1.0  
**Owner:** You  
**Stack:** Python 3.9+ CLI · ADB (external) · `whatsapp-chat-exporter` for decrypt/parse · stdlib `zipfile`/`csv`/`subprocess`  
**Runs on:** macOS and Windows  
**Audience:** A single technical user exporting their own WhatsApp chats from an Android phone to a local ZIP.

---

## Overview

A command-line tool that produces a single ZIP containing **all** of the user's WhatsApp chats (human-readable, browsable HTML), their media, and a separate contacts CSV. It reads WhatsApp's real encrypted local backup (`msgstore.db.crypt15`), decrypts it locally with the user's own 64-digit end-to-end backup key, converts it, and zips it. Nothing is uploaded.

**Mental model:** *The phone already keeps a complete, encrypted backup of every chat; this tool copies that backup to the computer, unlocks it with the user's own key, converts it to readable files, and packages it.*

---

## Design Pillars (Non-Negotiable)

1. **Local-only, zero network.** The tool makes no outbound network requests. Chat data and the key never leave the machine. Any future change that adds a network call violates this pillar.

2. **No root, no app downgrade.** Decryption relies solely on the user's 64-digit E2E backup key plus files in scoped storage. The deprecated `adb backup` / "downgrade WhatsApp" trick is **never** used.

3. **Read-only on the phone.** The tool only reads/pulls from the device. It never writes to, modifies, or deletes WhatsApp data on the phone.

4. **The key is never persisted.** It is held in memory for one run only — never written to disk by the tool, never logged, never printed, never committed.

5. **Crypto is delegated.** All decryption and chat parsing go through the mature `whatsapp-chat-exporter` library. No custom cryptography is written.

6. **Complete over convenient.** Every chat, no per-chat message cap, media included by default. Completeness is the reason this exists instead of the built-in export.

---

## Technical Facts

| Fact | Value |
|---|---|
| Encrypted backup file | `msgstore.db.crypt15` |
| Backup file location on phone | `/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Databases/msgstore.db.crypt15` |
| Media root on phone | `/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Media/` |
| Decryption key | 64-hexadecimal-character key (= 32 bytes) shown when enabling E2E encrypted backup with the *key* option |
| Key file (`key`) and contacts DB (`wa.db`) | Live in `/data/data/com.whatsapp/` → require root, NOT used by this tool |
| Exporter invocation | `wtsexporter -a -k <64hexkey> -b msgstore.db.crypt15` |
| Contact-name source | User-supplied **vCard** (`contacts.vcf`), since `wa.db` needs root. Enriched via `--enrich-from-vcards` |
| Built-in export caps (why we avoid that route) | ~40,000 msgs without media / ~10,000 with — **not** a limit of this tool |

### Locked Interpretations

**Backup freshness:** WhatsApp's local `msgstore.db.crypt15` is only as recent as the last local backup (auto ~daily). The tool must instruct the user to run a manual backup (WhatsApp → Settings → Chats → Chat backup → **Back Up**) before running, and must report the backup file's modified-timestamp so the user knows how fresh the export is.

**Key format:** Enabling E2E encrypted backups switches the local backup to crypt15, decryptable with the same 64-hex key. The tool accepts the key as 64 hex chars (case-insensitive, spaces stripped). It does **not** attempt the rooted `key`-file path.

---

## System Architecture

Single local CLI. No server, no database of its own, no auth (it's a personal local tool), no background jobs.

```
whatsapp-chat-exporter-local/
├── export.py            # CLI entry point: arg parsing + orchestration
├── wae/
│   ├── __init__.py
│   ├── env_check.py     # python version, adb present, device connected/authorized
│   ├── keyutil.py       # normalize + validate the 64-hex key
│   ├── pull.py          # adb pull crypt15 + media into temp workdir
│   ├── decrypt_export.py# wrap whatsapp-chat-exporter (decrypt → HTML/JSON/txt)
│   ├── contacts.py      # build contacts.csv from chats + vCard
│   └── package.py       # zip export dir → output/
├── requirements.txt     # pinned deps
├── .gitignore           # excludes key/db/output (see SECURITY.md)
├── README.md
├── SECURITY.md
└── SPEC.md
```

**Flow:** `export.py` orchestrates a strict pipeline:
`env_check → get key → pull → decrypt_export → contacts → package → cleanup`.

State lives only in a temp working directory (e.g. `./.tmp/`, gitignored, deleted at end) and the final `./output/` ZIP. External dependency: the `adb` binary on PATH.

---

## Data Model (Artifacts & Invariants)

| Artifact | What it is | Invariants |
|---|---|---|
| **Key** (in-memory string) | 64-hex decryption key | Exactly 64 hex chars after normalization; never written to disk, logged, or printed; lives only for the process lifetime |
| **Encrypted DB** (`msgstore.db.crypt15`) | Pulled from phone | Read-only copy; resides only in temp workdir; deleted on cleanup |
| **Media dir** | Pulled from phone (unless `--no-media`) | Read-only copy; temp workdir; deleted on cleanup |
| **vCard** (`contacts.vcf`, optional) | User-supplied contact export | Never modified; only read |
| **Export dir** | Decrypted HTML/JSON/txt + media | Generated fresh each run; basis of the ZIP |
| **Output ZIP** | `output/whatsapp-export-YYYY-MM-DD.zip` | Self-contained; opening `index.html` browses all chats; contains `contacts.csv` |

**Global invariants:** nothing is ever written *to* the phone; the temp workdir contains the only on-disk copies of decrypted data and is removed on success (unless `--keep-temp`); the key never appears in any file or log line.

---

## Feature Flow (Step by Step)

Single command: `python export.py [flags]`. The run proceeds through these stages, each of which fails loud with an actionable message rather than continuing silently.

### 1. Preflight (`env_check`)
- Python ≥ 3.9, else exit with message.
- `adb` resolvable on PATH, else exit with install guidance.
- Exactly one authorized device via `adb devices`. If zero → prompt user to connect + enable USB debugging. If >1 → require `--device SERIAL`.

### 2. Guidance Gate
- Print a reminder: ensure (a) E2E encrypted backup is ON with the 64-digit key, and (b) a fresh **Back Up** was just run. Continue on confirmation.

### 3. Get Key (`keyutil`)
- If `--key-file PATH` given, read it (file is the user's responsibility, must be gitignored). Else prompt interactively with no echo (`getpass`).
- Normalize (strip spaces/newlines, lowercase) and validate exactly 64 hex chars. Reject otherwise with a clear message. Never echo the key back.

### 4. Pull (`pull`)
- `adb pull` the `msgstore.db.crypt15` into temp workdir. If missing → tell user no local backup exists; instruct to run Back Up.
- Report the file's modified time (freshness).
- Unless `--no-media`: `adb pull` the Media dir into temp workdir. Pre-check free disk space and warn if media looks larger than available space.

### 5. Decrypt + Export (`decrypt_export`)
- Invoke `whatsapp-chat-exporter` with the key, the crypt15 file, the media path, the chosen `--format` (default `html`), and `--enrich-from-vcards` if a vCard was supplied.
- **Verify decryption succeeded** (exporter exits 0 and produces output). On the common "invalid key" failure, stop with a message that the key likely doesn't match this backup.

### 6. Contacts CSV (`contacts`)
- Extract unique participants (numbers, group membership) from the decrypted data.
- If a vCard was supplied, join to attach display names; otherwise emit numbers only.
- Write `contacts.csv` (columns: `name,number,source` where source ∈ `vcard|number-only`) into the export dir.

### 7. Package (`package`)
- Zip the export dir to `output/whatsapp-export-YYYY-MM-DD.zip`. If a ZIP for today exists, suffix `-2`, `-3`, … (never overwrite silently).

### 8. Cleanup
- Delete temp workdir (unless `--keep-temp`). Confirm key was never persisted. Print final ZIP path.

### Default Behaviours

- **Format:** human-readable browsable **HTML** (`index.html` entry). `--format json|txt` available.
- **Media:** **included** by default. `--no-media` to skip.
- **Contacts CSV:** always produced. Names require `--contacts-vcf`; without it, numbers only.
- **Key input:** interactive no-echo prompt. `--key-file` optional.
- **Device:** auto if one attached; `--device` required if multiple.

---

## CLI Interface

| Flag | Type | Default | Effect |
|---|---|---|---|
| `--output-dir PATH` | path | `./output` | Where the ZIP is written |
| `--format {html,json,txt}` | enum | `html` | Export format of chats |
| `--no-media` | flag | off (media included) | Skip pulling/embedding media |
| `--contacts-vcf PATH` | path | none | vCard to enrich names + power contacts CSV |
| `--key-file PATH` | path | none | Read key from file instead of prompting |
| `--device SERIAL` | string | auto | Select device when multiple attached |
| `--keep-temp` | flag | off | Keep temp workdir for debugging |

### Exit Codes
- `0` — success
- `1` — preflight failure (python/adb/device)
- `2` — invalid key
- `3` — no backup file found
- `4` — decryption failed
- `5` — packaging/IO error

Each maps to a printed, actionable message.

---

## Core Logic Internals

**Key normalization (`keyutil`)** — pure function, unit-testable:
```python
def normalize(raw):
    s = raw.strip().replace(" ", "").replace("\n", "").lower()
    if len(s) != 64 or not all(c in "0123456789abcdef" for c in s):
        raise InvalidKey
    return s
```

**Pull (`pull`)** — uses `subprocess` to call `adb [-s SERIAL] pull <remote> <localtemp>`. Remote paths are the fixed locations. Never runs `adb shell` commands that write.

**Decrypt/export (`decrypt_export`)** — builds and runs the `wtsexporter` command. Captures exit code + stderr; maps the known "invalid key / inflate" error to a friendly message. **LOCKED:** decryption is considered successful only if the exporter exits 0 *and* the expected output files exist.

**Contacts join (`contacts`)** — pseudocode:
```python
participants = unique numbers seen across all chats (incl. group members)
vmap = parse_vcard(vcf) -> {normalized_number: name}   # if vcf provided
for p in participants:
    name = vmap.get(normalize_number(p))
    row = (name or "", p, "vcard" if name else "number-only")
write_csv(rows)
```

**Locked Interpretation — phone-number matching:** numbers are normalized to digits-only (strip `+`, spaces, dashes) before joining vCard to chat participants, to maximize match rate.

---

## Critical Behaviours (Don't Get These Wrong)

- **Phone is read-only.** No `adb` command may write to or alter WhatsApp on the device. Pulls only.
- **Key hygiene.** The key must never be written to disk, logged, included in error output, or committed. Audit: grep the codebase for logging of the key variable — there must be none.
- **No network.** No HTTP client, socket, or upload anywhere in the tool. This is the central safety property.
- **Decryption verification.** A wrong/mismatched key must fail loudly (exit 2/4), not produce a silent empty or partial export.
- **Idempotent / re-runnable.** Running twice never corrupts state; ZIPs are suffixed, not overwritten; temp is always cleaned.
- **Secrets never enter Git.** `.gitignore` excludes keys, `*.crypt15`, `msgstore.db`, `wa.db`, `*.vcf`, `/output/`, `/.tmp/`, `*.zip` from the first commit.
- **Disk safety with media.** Media can be large; check free space before pull and warn.

---

## Test Plan

### Unit Tests
- `normalize()` accepts a 64-hex key with spaces/uppercase; rejects 63 chars, non-hex, empty → raises `InvalidKey`.
- Number normalization: `+91 98765 43210` and `919876543210@s.whatsapp.net` normalize to the same key.
- ZIP naming: second run same day yields `…-2.zip`, never overwrites.

### Integration Tests
- Given a known-good fixture `msgstore.db.crypt15` + matching key → exporter runs, `index.html` exists, expected chat count present.
- Given a deliberately wrong key → exit code 2/4 with the "key doesn't match" message; no partial output left behind.
- Contacts CSV: with a vCard, a known number gets its name and `source=vcard`; without a vCard, same number is `source=number-only`.
- `--no-media` produces a ZIP with no media dir; default includes media.

### Behavioural / Safety (Gate)
- Static check: **no** network/socket/HTTP imports or calls anywhere in `wae/` or `export.py`.
- Static check: the key variable is never passed to `print`/`logging`.
- After a successful run, the temp workdir is gone and no `key`/`*.crypt15` file remains outside it.
- `git status` after a run shows no secret/data files as untracked-but-includable (i.e. `.gitignore` covers them).

### Manual QA (E2E, Real Device)
- Fresh Back Up → run → open `index.html` → spot-check that a long chat is complete (beyond the 40k cap) and media renders.

### Edge Cases
- Zero chats
- A chat with only media
- Group with members not in vCard
- Multiple attached devices (must require `--device`)
- Unauthorized device (must instruct to accept the dialog)
- Media dir larger than free disk
- Non-ASCII contact names
- Corrupted/old crypt14 backup (fail clearly)

---

## Build Order (Dependencies First)

1. `keyutil` + its unit tests (cheapest, pure).
2. `env_check` (python/adb/device detection).
3. `pull` (adb integration) against a real device or recorded fixtures.
4. `decrypt_export` wrapper + the known-good fixture integration test (this is the riskiest integration — do it early to validate the whole premise).
5. `contacts` CSV + vCard join.
6. `package` (zip + naming).
7. `export.py` orchestration + exit-code mapping.
8. `.gitignore`, README, SECURITY wiring + the safety/static gate tests.

---

## Out of Scope / Resist in v1

- iPhone / iOS backups (different format and flow).
- The `adb backup` / WhatsApp-downgrade key-extraction trick (deprecated, unreliable — explicitly excluded by pillar 2).
- Rooted-device `key`-file / `wa.db` path.
- Any GUI, web UI, or browser extension.
- Cloud upload, sync, or hosted service of any kind.
- Incremental / delta exports (each run is a full export).
- Decrypting crypt12/crypt14 legacy formats (fail clearly and point to backup re-creation).
- Editing, redacting, or searching chats inside the tool (the HTML output already browses; leave analysis to the user).

---

## Open Items

- **TO BE DECIDED:** exact pinned dependency versions (`whatsapp-chat-exporter`, `pycryptodome`, `javaobj-py3`) — resolve by pinning the latest stable at build start, then run the §8 fixture test to confirm crypt15-with-hex-key works against a *current* WhatsApp backup. This is the one premise to validate before building the rest.

---

## Project Links & Docs

- **README.md** — user-facing guide, installation, quickstart.
- **SECURITY.md** — key hygiene, `.gitignore` design, safety checklist.
- **SPEC.md** — full technical specification (this document's source).

# Interface Contract — WhatsApp Chat Exporter (local)

**Status:** Agreed · **Date:** 2026-06-16
**Source:** `docs/architecture.md`, `tasks.md`, `SPEC.md` §6, `CLAUDE.md`

> **Why this isn't an HTTP API contract.** This project is a local CLI with no server, no network, no frontend, and no designer (see DECISIONS.md: "No network, no telemetry"). There are therefore no REST endpoints, no auth, no mock file, and no designer/Figma contract to produce. What *does* need pinning before code — so the six pipeline stages can be built in parallel and integrate cleanly — is the **internal interface between modules** and the tool's **programmatic + CLI entry points**. That is this document. It plays the exact role an API contract plays for a web app: agree the shapes before anyone writes code.

---

## 1. Entry points (the tool's public surface)

**Command-line entry** — see `SPEC.md §6` for the full flag table and exit codes. `export.py` only parses flags, builds a `RunContext`, obtains the key, calls `run_export`, and maps exceptions to exit codes.

**Programmatic entry (the Facade)** — the single importable function:

```python
run_export(ctx: RunContext, key: str) -> Path
#   returns: path to the produced ZIP
#   raises:  WaeError subclasses (see §5); KeyboardInterrupt handled by caller
#   side effects: pulls from device (read-only), writes temp + output ZIP,
#                 always cleans temp + drops key on exit (success or failure)
```

Anything importing this tool depends only on `run_export`, `RunContext`, and the `WaeError` hierarchy. Those three are the stable contract; everything else is internal.

---

## 2. Shared data object — `RunContext`

Immutable, non-secret configuration passed to every stage. **Contains no key.**

```python
@dataclass(frozen=True)
class RunContext:
    output_dir: Path        # where the ZIP is written        (default ./output)
    fmt: str                # "html" | "json" | "txt"          (default "html")
    include_media: bool     # pull media?                      (default True)
    contacts_vcf: Path|None # vCard for name enrichment        (default None)
    device: str|None        # adb serial to target             (default None → auto)
    package: str            # WhatsApp package                 (default "com.whatsapp")
    db_path: str|None       # on-device backup path override   (default None → probe)
    media_path: str|None    # on-device media path override    (default None → probe)
    verbose: bool           # DEBUG logging                    (default False)
    keep_temp: bool         # keep temp workdir                (default False)
    tmp_dir: Path           # ephemeral working directory
```

The **key** is never placed here. It is passed as a separate `key: str` argument, and only to `run_export` → `export_chats`.

---

## 3. Per-stage interface contract

Each stage is independently buildable against these signatures. No stage imports another; the orchestrator wires them.

### `env_check`
```python
check_python() -> None          # raises EnvError if Python < 3.9
check_adb() -> None             # raises EnvError if adb not on PATH
check_adb_version() -> None     # warns (never raises) if adb below known-good
select_device(requested: str|None) -> str   # returns adb serial; raises DeviceError
```

### `keyutil`
```python
normalize(raw: str) -> str      # returns 64-char lowercase hex; raises InvalidKey
get_key(key_file: Path|None) -> str   # prompt (no-echo) or read file → normalize
```

### `pull`
```python
adb(args: list[str], serial: str, read_only: bool = True) -> CompletedProcess
                                # forbids write verbs when read_only
resolve_paths(ctx: RunContext, serial: str) -> tuple[str, str]
                                # (db_remote, media_remote); raises NoBackupError
pull_backup(ctx: RunContext, serial: str) -> Path
                                # local path to msgstore backup; retries on transport error
pull_media(ctx: RunContext, serial: str) -> Path|None
                                # local media dir, or None if include_media is False
```

### `decrypt_export`
```python
detect_format(db_path: Path) -> str          # "crypt15"; raises DecryptionError on legacy
export_chats(db_path: Path, media_dir: Path|None, key: str, ctx: RunContext) -> Path
                                # returns export dir; raises DecryptionError on bad key / no output
```

### `contacts`
```python
extract_participants(export_dir: Path) -> set[str]      # unique numbers incl. group members
parse_vcard(path: Path) -> dict[str, str]               # {normalized_number: name}
normalize_number(n: str) -> str                         # digits-only
write_contacts_csv(participants: set[str], vmap: dict[str, str], export_dir: Path) -> Path
                                # writes contacts.csv (name,number,source)
```

### `package`
```python
check_output_writable(output_dir: Path) -> None   # raises PackagingError if unwritable/no space
make_zip(export_dir: Path, output_dir: Path) -> Path   # dated ZIP, suffix on collision
```

---

## 4. Data hand-off contract (what flows stage → stage)

This is the integration map — the equivalent of "what each endpoint returns to its caller."

| Producer | Value handed forward | Consumer |
|---|---|---|
| `get_key` | `key: str` (64-hex) | `export_chats` only |
| `select_device` | `serial: str` | `pull` functions |
| `resolve_paths` | `(db_remote, media_remote)` | `pull_backup`, `pull_media` |
| `pull_backup` | local backup `Path` | `export_chats` |
| `pull_media` | local media `Path \| None` | `export_chats` |
| `export_chats` | export-dir `Path` | `contacts`, `package` |
| `write_contacts_csv` | `contacts.csv` inside export dir | `package` |
| `make_zip` | final ZIP `Path` | `run_export` return value |

---

## 5. Error contract (the "error responses")

Every failure is a typed `WaeError` carrying a message and an exit code. This is the contract the CLI shell maps to process exit codes.

| Exception | Exit code | Raised by | Meaning |
|---|---|---|---|
| `EnvError` | 1 | env_check | Python/adb prerequisite missing |
| `DeviceError` | 1 | env_check, pull | No/ambiguous/unauthorized device, or transport failure after retries |
| `InvalidKey` | 2 | keyutil | Key not 64-hex after normalization |
| `NoBackupError` | 3 | pull | No backup file found on device |
| `DecryptionError` | 4 | decrypt_export | Wrong key, or legacy/unsupported format |
| `PackagingError` | 5 | package | Output unwritable / insufficient space |
| `KeyboardInterrupt` | 130 | (user) | Handled by the shell; teardown still runs |

---

## 6. Output contract (what the tool produces — the "response shape")

The ZIP `whatsapp-export-YYYY-MM-DD.zip` (suffixed `-2`, `-3`… on same-day collision) contains, at its root:

- the browsable chats entry (`index.html` for the default HTML format; JSON or text files for the other formats),
- the `media/` tree (unless `--no-media`),
- `contacts.csv` with columns `name,number,source` (`source` ∈ `vcard | number-only`).

An empty account still yields a valid ZIP (empty chats view, header-only `contacts.csv`).

---

## 7. Explicitly NOT part of this contract

Deliberately excluded because the architecture has no such surface — designing or building for these would contradict the agreed design:

- **HTTP/REST endpoints, routes, status codes** — there is no server.
- **Authentication / tokens** — nothing is exposed over a network.
- **A `mock.json` for a frontend** — there is no frontend developer to unblock.
- **A designer / Figma contract** — there are no screens; the user-facing surface is the CLI (`SPEC.md §6`) and the produced ZIP.
- **Any network call of any kind** — see DECISIONS.md ("No network, no telemetry").

---

## Sync rule

This contract and `SPEC.md §6` (CLI surface) must agree. A field or signature change here must be reflected in `SPEC.md` / `tasks.md` / the relevant GitHub issue in the same change. Divergence is a block, exactly as TECHNICAL.md and designer-contract.md are kept in sync in the standard flow.

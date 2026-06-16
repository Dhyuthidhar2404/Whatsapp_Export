# SECURITY.md

This document explains the security model of the WhatsApp Chat Exporter and the precautions you must take. Read it before running or publishing the tool.

---

## The core idea

There is **nothing secret in the code itself**. The code only copies files, calls an existing library, and zips the result. The sensitive things are:

1. Your **64-digit encrypted-backup key**.
2. The **encrypted database file** (`msgstore.db.crypt15`).
3. The **exported output** (decrypted chats + media).

Security here is almost entirely about keeping those three things off the internet and off other people's machines. The code being public is fine; the data being public would be a disaster.

---

## Threat model — what could go wrong

| Risk | How it happens | How this project prevents it |
|---|---|---|
| Your entire chat history leaks publicly | You accidentally commit the key, the `.crypt15` file, or the output ZIP to GitHub | `.gitignore` excludes all of them by default |
| Someone reads your chats | They obtain your key **and** your backup file | Key is never written to disk by the tool; you store it yourself, treated like a password |
| Data is sent to a third party | A dependency or your own code makes a network request | Tool is local-only; dependencies are pinned and minimal; crypto handled by a well-known library |
| A user can't trust the tool | Closed-source tools can't be audited | This is open source — every line is readable |

---

## Rules you must follow

### 1. Never commit secrets

The single most important file in this repo is `.gitignore`. It must exclude — from day one — the key, the database files, and the output folder. Suggested contents:

```gitignore
# Never commit secrets or chat data
*.crypt12
*.crypt14
*.crypt15
msgstore.db
wa.db
key
*.key
key.txt
/output/
*.zip

# Working / temp files
/tmp/
__pycache__/
*.pyc
.env
.venv/
venv/
```

If you ever see one of these files appear in `git status` as staged, **stop** and remove it before committing.

> If a secret is *ever* pushed to GitHub — even once, even if you delete it later — assume it is compromised. Regenerate your WhatsApp encrypted-backup key and rewrite history or delete the repo.

### 2. Treat the 64-digit key like a password

- Don't paste it into the repo, a README, an issue, a screenshot, or a chat window.
- Store it in a password manager.
- The tool prompts for it at runtime and does **not** save it. Keep it that way if you modify the code.

### 3. Keep the tool offline-only

This tool should never need to make a network request. If you add a feature, do not introduce one that uploads chats or the key anywhere. The local-only property is the main thing that makes it safe.

### 4. Pin and minimise dependencies

- Pin every dependency to a specific version in `requirements.txt`.
- Prefer the well-known `whatsapp-chat-exporter` library for all decryption rather than writing custom crypto.
- Fewer dependencies touching the key = smaller attack surface and easier for others to audit.

### 5. Clean up after yourself

The decrypted output is your plain-readable chat history. Store the ZIP somewhere safe (encrypted disk / password manager vault), and delete temporary copies of the decrypted database and pulled files when you're done.

---

## What this tool does NOT do

- It does **not** use the `adb backup` / "downgrade WhatsApp to an old version" trick. That method is deprecated, unreliable on modern Android, and risky. This tool relies only on the official encrypted-backup key.
- It does **not** require rooting your phone.
- It does **not** upload anything, anywhere.
- It does **not** store your key.

---

## For contributors / reviewers

If you're reviewing this code before trusting it, check three things:

1. **No network calls** — search the code for HTTP clients, sockets, or upload logic. There should be none.
2. **Key is never persisted** — confirm the key is only held in memory during a run and never written to a file or logged.
3. **`.gitignore` is intact** — confirm it still excludes keys, databases, and output.

If all three hold, the tool does what it claims: a fully local export, with your secrets staying on your machine.

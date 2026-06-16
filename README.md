# WhatsApp Chat Exporter

A small, local-only command-line tool that exports **all** of your WhatsApp chats — with media — into a single ZIP file. Runs on macOS and Windows. Nothing is uploaded anywhere; the whole process happens on your own machine.

> **What this is, in one sentence:** your phone already keeps a complete, encrypted copy of all your chats — this tool copies that copy to your computer, unlocks it with *your own* key, converts it to readable files, and zips it.

---

## Why this approach

WhatsApp has no "export everything" button. The two common shortcuts both fall short:

- **Built-in "Export chat"** is per-conversation and capped (~40,000 messages without media, ~10,000 with), so long chats get silently truncated.
- **Browser extensions** scrape WhatsApp Web by auto-scrolling the page — slow, gap-prone on long chats, and they require trusting a third party with live access to your session.

This tool instead reads WhatsApp's actual encrypted database (`msgstore.db.crypt15`). That single file contains *every* chat with no per-chat cap, fully structured. We decrypt it locally using the key WhatsApp gives you, then export and zip.

The heavy lifting (decryption + parsing) is done by the mature open-source library [`whatsapp-chat-exporter`](https://pypi.org/project/whatsapp-chat-exporter/). This project is mostly the glue around it: pull the files from the phone, run the exporter, zip the result.

---

## How it works (the 4 steps)

1. **You enable an encrypted backup on your phone (one-time, ~2 minutes).**
   In WhatsApp: **Settings → Chats → Chat backup → End-to-end encrypted backup → turn on**, and choose the **64-digit key** option (not a password). Write the key down and keep it safe. This is the only step the tool can't do for you.

2. **The tool copies two things off your phone over USB.**
   The encrypted backup file (`msgstore.db.crypt15`) and your media folder. These live in a normal, accessible location (`/sdcard/Android/media/com.whatsapp/...`) — **no root required**.

3. **The tool decrypts the database using your 64-digit key.**
   Without the key the file is unreadable; with it, the chats come back.

4. **The tool exports everything and zips it.**
   Each conversation is written as HTML (or JSON/TXT), media attached, all bundled into one ZIP in the output folder.

---

## Prerequisites

- **An Android phone** (this database method is Android-specific).
- **Python 3.9+** installed on your computer.
- **ADB (Android Platform Tools)** installed and on your PATH.
- **USB debugging enabled** on the phone: Settings → About phone → tap *Build number* 7 times → back to Developer options → enable *USB debugging*.
- Your **64-digit encrypted-backup key** (from step 1 above).

---

## Installation

```bash
git clone https://github.com/<your-username>/whatsapp-chat-exporter-local.git
cd whatsapp-chat-exporter-local
pip install -r requirements.txt
```

`requirements.txt` should pin specific versions, e.g.:

```
whatsapp-chat-exporter==<pinned-version>
pycryptodome==<pinned-version>
javaobj-py3==<pinned-version>
```

---

## Usage

1. Connect your phone via USB and confirm the connection:

   ```bash
   adb devices
   ```

   You should see your device listed (accept the "Allow USB debugging?" prompt on the phone if it appears).

2. Run the export. You'll be prompted for your 64-digit key (it is **not** stored):

   ```bash
   python export.py
   ```

3. When it finishes, find your archive in:

   ```
   ./output/whatsapp-export-YYYY-MM-DD.zip
   ```

---

## Output

The ZIP contains a browsable HTML view of every chat plus all associated media. Open `index.html` inside it to read your conversations.

---

## Security — read this before using

This tool is safe to publish and safe for others to use, **but the data and the key are sensitive**. The most important rules:

- **Never commit your key, the database files, or the output ZIP to Git.** The included `.gitignore` is configured to prevent this — do not remove those entries.
- **The 64-digit key is the whole ballgame.** Anyone with your key *and* your backup file can read all your chats. Treat it like a password: not in the repo, not in a screenshot, not pasted into a chat window.
- **Everything runs locally.** This tool makes no network calls. If you modify it, keep it that way.

Full details and the safe-handling checklist are in **[SECURITY.md](./SECURITY.md)**.

---

## For other people using this repo

Because it's open source, you can read every line and confirm it never phones home. Dependencies are pinned and minimal, and all cryptography is handled by the well-known `whatsapp-chat-exporter` library rather than custom code. Each person runs it against **their own** phone and **their own** key — nobody can use this repo to reach anyone else's data.

---

## Limitations

- Android only (the encrypted-database method does not apply to iPhone in the same way).
- Requires you to enable the encrypted-backup key once.
- The `adb backup` / "downgrade WhatsApp" trick is **not** used — it's deprecated and unreliable on modern Android. This tool relies on the encrypted-backup key instead.

---

## License

Add a license of your choice (e.g. MIT) before publishing.

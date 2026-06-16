STATUS: APPROVED — Ready for implementation
Generated from: docs/features.md
Last updated: 2026-06-16

> Note: this is a command-line tool, not a screen-based app. There are no screens to load and nothing visual to regression-test, so the screen/Playwright framing of the standard template has been adapted: each "moment" below is a point in the person's real experience — some on their phone, some in a terminal window on their computer. The six-states checklist is kept, mapped to the command-line equivalents (working / done / nothing-to-export / error / partly-done / blocked).

# User Journey — Exporting your WhatsApp chats to a ZIP

This describes what a real person does, start to finish, from "I want a copy of all my chats" to "I have a ZIP I can open." Written for someone who has never used the tool.

---

## Moment 1 — Getting your phone ready (before touching the computer)

**The person is here because:** they want a complete, private copy of all their WhatsApp chats and media on their own computer.

**What they see:** their phone, with WhatsApp open.

**Step 1:** In WhatsApp, they go to **Settings → Chats → Chat backup**, turn on **End-to-End Encrypted Backup**, and choose the option that gives them a 64-digit hexadecimal key (not a password).
→ WhatsApp shows them a long key made of 64 characters (letters and numbers).
→ **They write it down in a password manager or safe location immediately — before they close this screen.** If they leave without saving the key, WhatsApp won't show it again, and they'd have to enable encrypted backup once more (which would create a different, new key). There's no way to recover a lost key. This is the only step the tool can't do for them.

**Step 2:** Still on that backup screen, they tap **Back Up** to make a fresh backup right now.
→ This creates an up-to-date backup immediately, rather than waiting for WhatsApp's automatic daily backup. A timestamp updates to "just now."

**Step 3:** They turn on USB debugging on the phone (**Settings → About phone** → tap "Build number" seven times → go back to **Developer options** → switch on **USB debugging**).
→ The phone is now allowed to talk to a computer over the cable.

**Step 4:** They plug the phone into the computer with a USB cable.
→ The phone may pop up a box asking "Allow USB debugging?" — they tap **Allow** (and "always allow from this computer" if offered).

**If something goes wrong:**
- They can't find the End-to-End Encrypted Backup option: their WhatsApp may be out of date. They update WhatsApp and look again.
- They lost the key or closed the backup screen without writing it down: they go back to Settings → Chats → Chat backup and turn on encrypted backup again. This creates a new, different key. The old backup can no longer be decrypted.
- They use WhatsApp Business instead of regular WhatsApp: the tool can handle that — they'll just need to add a flag when running it (`--package com.whatsapp.w4b`; see the README).
- The "Allow USB debugging?" box doesn't appear or they tapped Deny: they unplug and replug the cable, unlock the phone, and tap Allow when it appears.

---

## Moment 2 — Getting the tool onto the computer

**What they see:** a terminal window (the text-command window on their Mac or Windows computer).

**Step 1:** They download the tool's folder from its web page and install the few things it needs, following the short instructions in the README.
→ After a minute, the tool is ready to run.

**If something goes wrong:**
- The install complains that something called "ADB" is missing: the README points them to install it. This is the piece that lets the computer talk to the phone.
- A download or install step is blocked by their network: the README explains they may need to adjust their network settings.

---

## Moment 3 — Running the tool

**What they see:** the empty terminal, ready for a command.

**Step 1:** They type the run command and press Enter.
→ The tool first checks everything is ready: that the computer has what it needs and that exactly one phone is connected and allowed.
→ If all good, the tool prints a checklist: "Make sure you've (a) turned on End-to-End Encrypted Backup in WhatsApp, and (b) just did a fresh Back Up. Ready to continue? (Y/n)" — they read it and type `y` to continue, or stop here if anything isn't ready.
→ Only then does it ask for the key.

**Blocked / not-ready states (what they might see instead):**
- No phone detected: the tool stops and tells them to connect the phone, switch on USB debugging, and tap Allow on the phone.
- Two phones connected: the tool stops and asks them to say which phone to use.
- The phone shows as "unauthorized": the tool stops and tells them to look at the phone and tap Allow on the dialog.

**If something goes wrong:**
- A required piece (like ADB) is missing: the tool stops immediately with a plain message naming what to install, rather than failing halfway through.

---

## Moment 4 — Entering your key

**What they see:** a prompt asking them to enter their 64-digit hexadecimal key. As they type or paste, nothing shows on screen (the key stays hidden, like a password field).

**Step 1:** They paste the 64-character key they saved in Moment 1 and press Enter.
→ The tool quietly checks the key is the right shape (the right length and characters).
→ If it looks right, the tool carries on. The key is never shown back to them, never saved to a file, never included in the ZIP, and never sent anywhere — it's only used once, in memory, to unlock the backup.

**If something goes wrong:**
- They paste something that isn't a valid key (too short, a typo, extra characters): the tool stops with a clear "that key doesn't look right" message and they can run it again. It does not silently produce an empty or broken result.
- They realize halfway through they entered the wrong key: they can stop the tool with Ctrl-C. The tool will clean up and they can run it again with the correct key.
- They'd rather not paste it each time: they can instead point the tool at a small file that holds the key (the README explains how, and how to keep that file private).

---

## Moment 5 — The tool does its work

**What they see:** a series of short progress messages, in plain language, as the tool works through each stage. They don't have to do anything during this — they just watch.

**Working (what the progress looks like):**
→ "Copying your phone's backup…" — and it tells them how old that backup is (so they know it reflects the Back Up they did in Moment 1).
→ "Copying your photos, videos and voice notes…" — this is the longest part if there's a lot of media. If they have gigabytes of media, this can take several minutes — this is normal and expected.
→ "Unlocking your chats with your key…"
→ "Building readable chats…"
→ "Writing your contacts list…"
→ "Packaging everything into a ZIP…"

**Partly-done states (some things succeed, some don't):**
- A few media files can't be read from the phone (usually due to permissions): the tool skips them, keeps going, and at the end tells them how many were skipped, rather than stopping the whole export.

**If something goes wrong:**
- The phone is disconnected or sleeps mid-copy: the tool tries again a couple of times; if it still can't reach the phone, it stops and asks them to reconnect and re-run.
- There isn't enough free space for all the media: before copying media, the tool estimates the size and checks free disk space. If there isn't enough room, it warns the person with the number of GB needed and offers the option to skip media (using the `--no-media` flag) or free up space and retry.
- No backup is found on the phone: the tool stops and reminds them to tap **Back Up** in WhatsApp first.
- The phone is locked during copying: the tool tells them to unlock the phone and try again.
- The key doesn't match this particular backup: the tool says so plainly and stops — it does not hand them an empty result and pretend it worked.
- The backup is an old, unsupported format (crypt12 or crypt14): the tool explains this and suggests turning on the encrypted backup and making a fresh one.

---

## Moment 6 — You're done

**What they see (done / happy path):** a final message with the location and name of the ZIP, for example "Saved your export to … whatsapp-export-2026-06-16.zip."

**Step 1:** They open the ZIP.
→ Inside is an **index.html** file they can open in any web browser, which shows all their chats in a readable, browsable format. Media is embedded (photos, videos, voice notes are all there). There's also a **contacts.csv** file with everyone they've chatted with — ready to open in Excel or any spreadsheet app.
→ The ZIP is ready to open immediately — no additional software or decryption needed.

**Step 2:** They open the browsable chats file and scroll through their conversations to confirm everything's there — including their longest chats, with nothing cut off.

**Nothing-to-export state (empty):**
- If the account genuinely has no chats, the tool still produces a valid ZIP — the chats view is simply empty and the contacts list has just its column headings. The person isn't left wondering whether it failed.

**If they run it again later:**
- Running it a second time on the same day makes a second, separately named ZIP (e.g., `whatsapp-export-2026-06-16-2.zip`) — it never quietly overwrites the first one.
- When it finishes (or if they stop it partway with Ctrl-C), the tool tidies up its temporary working files and automatically wipes the key from memory, ensuring no sensitive data is left behind on the computer.

---

## The six states, at a glance

For a command-line tool the "per-screen states" map to these run states; each is covered above:

- **Working / loading:** the plain-language progress messages in Moment 5.
- **Done / with data:** the final ZIP message and the browsable chats in Moment 6.
- **Empty / nothing to export:** a valid ZIP with empty chats and a header-only contacts list (Moment 6).
- **Error:** every "if something goes wrong" message stops clearly and says what to do (Moments 3–5).
- **Partly done:** skipped unreadable media reported at the end (Moment 5).
- **Blocked / disabled:** missing tool, no phone, multiple phones, unauthorized phone, no backup — each stops up front before any work begins (Moments 3–5).

---

## Next step

This document is approved and ready for implementation. The natural equivalent for this command-line tool (rather than Playwright visual-qa) is a scripted end-to-end test that walks these same moments, verifying each state and message.

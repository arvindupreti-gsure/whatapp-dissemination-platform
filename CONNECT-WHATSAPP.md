# Connecting a real WhatsApp account

### Step by step | Gsure Technologies Private Limited

---

## Before you start: read this

This connects the platform to a **real WhatsApp account** by operating it as a
linked device, the same mechanism as WhatsApp Web. It is the only route that can
reach groups that already exist, which is why the proposal recommends it.

**It is not covered by WhatsApp's published API terms.** The account carries a
restriction risk, up to and including loss of the number. This is risk R1 in the
proposal, and no configuration removes it.

| Do | Do not |
|---|---|
| Use a **spare or test number** for the first run | Do not start on the client's live 5,000 group number |
| Get **written authorisation** from the number's owner | Do not link a number you do not control |
| Start at **1 message per second** | Do not raise the rate until a small run is clean |
| Send to **one group** first | Do not fire at the whole network on day one |
| Watch the account for warnings between runs | Do not run unattended on the first day |

A brand new SIM is the worst choice. A number with real history and real
conversations behaves far better under automation than a fresh one.

---

## What you need

| Item | Notes |
|---|---|
| Node.js 20 or later | Already installed here (24.16.0) |
| A phone with WhatsApp installed | The handset that **owns** the number |
| The phone and this PC on any network | They do not need to be on the same one |
| Written authorisation from the number's owner | Keep it on file |

---

## Step 1. Start the platform

If it is not already running:

```
cd C:\Users\CORE\Desktop\Clientwork\wdap-poc
run.bat
```

Leave that window open. Confirm **http://127.0.0.1:8000** loads and you can
sign in as `admin@gsuretech.com` / `Gsure@2026`.

---

## Step 2. Start the bridge

Open a **second** terminal window:

```
cd C:\Users\CORE\Desktop\Clientwork\wdap-poc\bridge
npm install
npm start
```

`npm install` only needs to run the first time. You should see:

```
  WDAP linked device bridge
  Gsure Technologies Private Limited

  This operates a REAL WhatsApp account as a linked device.
  Not covered by WhatsApp API terms. Account restriction risk applies.
  Use only on a number whose owner has authorised it in writing.

  Bridge listening on http://127.0.0.1:8787
  Link the account at http://127.0.0.1:8787/qr
```

Leave this window open too. You now have two terminals running.

---

## Step 3. Scan the QR code

1. Open **http://127.0.0.1:8787/qr** in your browser. A QR code appears.
2. On the phone that owns the number:
   - **Android:** WhatsApp → three dots → **Linked devices** → **Link a device**
   - **iPhone:** WhatsApp → **Settings** → **Linked devices** → **Link a device**
3. Point the phone at the QR code on screen.

The QR refreshes every few seconds. If it expires, the page reloads a new one
by itself.

On success the bridge terminal prints:

```
  Linked as <your name> (91XXXXXXXXXX:XX@s.whatsapp.net)
  Cached N groups from the linked account.
```

**That N is the real number of groups that account belongs to.** Confirm it
looks right before going further.

---

## Step 4. Confirm the platform sees it

In the platform, go to **Channels**. The `linked_device` card should now show:

- **ready** (green)
- Sends real messages: **Yes**
- Existing groups: **Can address**

If it still says "not ready", the bridge is running but not yet linked. Go back
to step 3.

---

## Step 5. Import your real groups

On the same **Channels** page, click **Import groups from this channel** on the
`linked_device` card.

The platform pulls every group the linked account belongs to and adds any it has
not seen before. It reports `Discovered N, added M`.

Go to **Groups**. Your real groups are now listed alongside the 5,000 seeded
demo ones, marked with source `linked_device`.

**Tidy up before sending.** The seeded demo groups have fake WhatsApp ids and
will fail if you target them. Either:

- filter to your real groups and build a saved list from them, or
- delete the demo data first: stop the platform, delete
  `data\wdap.sqlite3`, restart, then import (this also clears the demo
  campaigns, and re-seeds 5,000 demo groups on first run, so filter by source
  instead if you want a clean split).

---

## Step 6. Slow the sending rate down

**Do this before your first real send.** Dashboard → **Adjust rate**:

| Setting | First run | Once a run is clean |
|---|---|---|
| Messages per second | **1** | raise gradually, 2, then 5 |
| Randomised jitter | **0.5** | keep high |

Or set it before launch:

```
set WDAP_SEND_RATE=1
set WDAP_SEND_JITTER=0.5
run.bat
```

The governor also applies a warm-up ramp automatically: the first sends go out
well below the nominal rate and it climbs over roughly 500 messages.

---

## Step 7. Send to ONE group first

1. **Campaigns → New campaign**
2. Name it something obvious, for example `Bridge test`
3. Message body: a short, plain, genuinely useful message
4. **Channel: `linked_device`**
5. Target: **Saved campaign list** containing exactly one group you control
6. Leave the schedule blank, create, then **Launch now**

Watch the **per group delivery log**. Within seconds you should see:

```
sent  ->  delivered  ->  read
```

Check the phone. The message should be in the group. If it arrived and the log
advanced past `sent`, the whole pipeline works end to end.

---

## Step 8. Scale up in stages

Only after step 7 is clean:

| Run | Groups | Rate | Then |
|---|---|---|---|
| 1 | 1 | 1/s | Confirm delivery and read |
| 2 | 10 | 1/s | Check for failures |
| 3 | 50 | 1/s | Watch the account for warnings, wait a day |
| 4 | 250 | 2/s | Wait a day |
| 5 | Full network | 5/s | Only if every prior run was clean |

If failures appear, **stop and reduce the rate**. Do not push through them. The
failure codes in the per group log tell you which kind of problem it is:
`130429` and `131056` are rate limits, `131049` means WhatsApp declined to
deliver to protect the recipient experience.

---

## What you get back automatically

Once linked, the platform polls the bridge every 3 seconds and applies what it
finds. No configuration needed.

| Metric | Source | Behaviour |
|---|---|---|
| **M1** groups reached | delivery receipt | `sent` advances to `delivered` |
| **M9** read statistics | per participant read receipts | `delivered` advances to `read`, and **each member who reads increments a count**, so a group read is a number, not a yes or no |
| **M2** failures | send error | numeric code and reason in the log |
| **M6** replies and opt outs | inbound group messages | attributed to the campaign that last targeted that group |
| **M4** link clicks | your own tracked short links | works on any channel |
| **M5** media views | your own tracked landing page | only if media is sent as a tracked link |

Status never moves backwards: a late acknowledgement cannot undo a read.

---

## Unlinking

Either:

- **From the phone:** WhatsApp → Linked devices → tap the entry → **Log out**
- **From the bridge:**
  ```
  curl -X POST -H "X-Bridge-Token: wdap-local-bridge" http://127.0.0.1:8787/logout
  ```

To start completely fresh, stop the bridge and delete the `bridge\auth` folder,
then scan again.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| QR page says "Waiting for a QR code" forever | Bridge cannot reach WhatsApp servers | Check internet, firewall, corporate proxy |
| QR expires before you scan | Normal, they are short lived | The page auto refreshes, just scan the new one |
| "Not linked" after scanning | Connection dropped immediately | Check the bridge terminal for the reason; delete `bridge\auth` and retry |
| Channels shows `linked_device` not ready | Bridge not running, or not linked | Confirm both terminals are open, revisit `/qr` |
| `Import groups` returns 0 | Account belongs to no groups, or cache is stale | Restart the bridge to refresh the cache |
| Everything stays at `sent` | Bridge stopped after the send | Keep the bridge running; receipts arrive seconds to minutes later |
| Sends fail with `Bridge unreachable` | Bridge terminal was closed | Restart it, then use **Retry failed** on the campaign |
| Account gets a warning or is restricted | Rate too high, or content looks like spam | Stop immediately. This is risk R1. Do not switch to another number and continue |

---

## One honest note

Everything above is the mechanism working as designed. What it cannot tell you
is how **your** number, with **your** history, behaves at **your** volume. That
is exactly what the Week 1 proof of concept in the proposal exists to establish,
and why we priced it before the build rather than after.

Nothing here should be treated as evidence that WhatsApp will tolerate sustained
automated dissemination on any particular account.

---

Gsure Technologies Private Limited | Confidential

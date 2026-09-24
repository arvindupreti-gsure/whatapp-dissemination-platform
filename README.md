# WhatsApp Dissemination & Analytics Platform
### Proof of concept | Gsure Technologies Private Limited

A running implementation of the platform described in the project proposal:
centralised dissemination, group management at scale, campaign control,
per group delivery logging, interval analytics, reporting and role based access.

---

## Read this first

**The default despatch channel is a simulator. It sends nothing.**

That is deliberate, and it is the honest position. The simulator models the
outcome distribution a real Week 1 proof of concept would measure, so that the
queue, the rate governor, the retry path, the analytics pipeline, the tracking
endpoints and the interval snapshot engine are all exercised end to end without
touching a live WhatsApp account. Every rate in it (a 3.1% failure rate, a 72%
read rate) is **an assumption drawn from config, not an observation**.

Two channels do send real messages:

| Channel | Sends for real | Can address the client's existing 5,000 groups |
|---|---|---|
| `simulator` (default) | No | Simulated only |
| `cloud_api` | **Yes** | **No.** 8 participants per group, no import path |
| `linked_device` | **Yes** | **Yes.** Not covered by WhatsApp API terms |

The `linked_device` bridge operates a real WhatsApp account and carries an
account restriction risk. This is risk R1 in the proposal. Use it only on a
number whose owner has authorised it in writing.

---

## What you need to provide

| # | Dependency | Required for | Notes |
|---|---|---|---|
| 1 | **Python 3.10+** on PATH | Everything | Already installed here (3.14.6). Windows installer: tick "Add python.exe to PATH" |
| 2 | **Network access to PyPI**, once | First run only | `run.bat` installs the nine packages in `requirements.txt` automatically |
| 3 | **A free TCP port** | Everything | Tries 8000, walks up to 8025 automatically if busy |
| 4 | Node.js 20+ | Only the linked device bridge | Already installed here (24.16.0) |
| 5 | **A WhatsApp number and handset** | Only for real sends | Plus **written authorisation from its owner**. See risk R1 |
| 6 | Meta credentials (phone number id, access token, WABA id, Official Business Account) | Only the `cloud_api` channel | Not needed for the demonstration |
| 7 | A public HTTPS URL | Only to receive Meta webhooks | ngrok or similar for local testing |

**For the demonstration you need items 1 to 3 only.** Nothing else, and no
WhatsApp account.

## Quick start

```
run.bat                 (Windows, safe to double click)
./run.sh                (bash)
```

The launcher checks Python, installs dependencies if they are missing, finds a
free port, starts the server and opens the browser. **It keeps the window open
on any error** so the message can be read. Set `WDAP_NO_BROWSER=1` to skip the
browser.

Then open **http://127.0.0.1:8000** (or whichever port it reports) and sign in.

| Email | Role | Password |
|---|---|---|
| admin@gsuretech.com | Super Administrator | `Gsure@2026` |
| manager@gsuretech.com | Campaign Manager | `Gsure@2026` |
| analyst@gsuretech.com | Analyst | `Gsure@2026` |
| viewer@gsuretech.com | Viewer | `Gsure@2026` |

First run seeds **5,000 synthetic groups**, four users, three saved campaign
lists and three message templates into `data/wdap.sqlite3`. Delete that file to
start over.

### A two minute walkthrough

1. **Dashboard** shows the portfolio and the despatch governor.
2. **Campaigns > New campaign**. Pick the "Weekly community bulletin" template,
   set a link to track, target by category (try Emergency Response, about 500
   groups), leave the schedule blank, create.
3. **Launch now.** Watch the progression chart, the per group log and the
   operational log fill in real time. Retries appear in the log as they happen.
4. When despatch completes, the four interval snapshots are scheduled. At the
   default time scale they land in roughly 9, 36, 108 and 288 seconds.
5. **Reports** exports the same campaign to Excel, CSV and PDF.

---

## Interval compression

The Scope of Work asks for snapshots at 15 minutes, 1 hour, 3 hours and 8 hours.
Waiting 8 hours to see a demonstration is not useful, so `WDAP_TIME_SCALE`
compresses the wall clock spacing. **The labels never change, only the spacing.**

| Label | Nominal | At scale 0.01 (default) |
|---|---|---|
| 15m | 900s | 9s |
| 1h | 3,600s | 36s |
| 3h | 10,800s | 108s |
| 8h | 28,800s | 288s |

Set `WDAP_TIME_SCALE=1` for production semantics.

---

## Coverage against the Scope of Work

| Scope of Work requirement | Status | Where |
|---|---|---|
| **1. Centralised dissemination** | | |
| Text, image, video, document, PDF, audio | Built | Media upload, bridge routes by MIME type |
| Send to all groups or a selected subset | Built | Campaign targeting by list, category, folder or tag |
| One click campaign execution | Built | Launch action |
| Scheduled messaging | Built | `scheduled_at`, scheduler loop polls every 2s |
| Recurring campaigns | Built | Hourly, daily, weekly. Rolls a child campaign forward |
| Reusable templates | Built | Three seeded, create more via API |
| **2. Group management** | | |
| Import and organise ~5,000 groups | Built | 5,000 seeded; CSV import; live import from linked device |
| Categories, tags, folders, campaign lists | Built | All four, with faceted counts |
| Search, filter, manage | Built | Name, id, region search plus three filters, server side paging |
| Add or remove groups from campaigns | Built | Bulk operations endpoint |
| **3. Campaign dashboard** | | |
| Campaign ID, name, date and time | Built | `CMP-00001` sequence |
| Message and media preview | Built | Rendered exactly as one group receives it, tracked links included |
| Target groups, status, success/failure logs | Built | Per group log, one row per group |
| **4. Analytics and reporting** | | |
| 15m / 1h / 3h / 8h intervals | Built | Immutable snapshots, heap scheduled |
| Groups reached, failures, pending | Built | M1, M2, M3 |
| Read statistics | Built | M9, aggregated per group |
| Link clicks | Built | M4, per group tracked short link, real HTTP redirect |
| Media views | Built | M5, tracked landing endpoint only |
| User interactions | Built | M6, replies and opt outs |
| Engagement and custom metrics | Built | M7, M8 |
| **5. Dashboard** | | |
| Live monitoring, history, delivery status | Built | Polls every 2.5s while a campaign runs |
| Graphical analytics | Built | Progression line chart, interval bar chart, status bar |
| Real time logs | Built | Operational event stream |
| Export, user management | Built | See below |
| **6. Reports** | | |
| Excel, CSV, PDF | Built | Four sheet workbook, per group CSV, landscape PDF |
| Campaign, date, group, success/failure, summary | Built | All five cuts |
| **7. User roles** | | |
| Super Admin, Campaign Manager, Analyst, Viewer | Built | Permission matrix, enforced per route |
| **8. Security** | | |
| Secure authentication | Built | PBKDF2-SHA256, 240,000 rounds, server side sessions |
| Audit logs | Built | Actor, action, entity, detail, IP. Denials recorded |
| Encrypted data storage | Partial | Fernet field encryption for channel credentials. Full disk encryption is a deployment concern |
| Backup and recovery | Not built | SQLite file copy in the PoC. Managed Postgres PITR in production |
| Access controls | Built | Least privilege permission matrix |
| **9. Scalability** | | |
| More than 5,000 groups | Demonstrated | 5,000 seeded, 487 despatched in 10.2s at 400 msg/s |
| Multiple campaigns per day | Built | Independent queues and worker pools per campaign |
| Large media | Partial | Uploaded once, reused per group. CDN is a deployment concern |
| Future additional numbers | Designed | Adapter registry accepts a pool. Not exercised |

---

## The feasibility metrics, live

Every metric in the platform carries the identifier it has in the proposal's
feasibility table, so a number on screen can always be traced to its basis.

| Id | Metric | Basis in this build |
|---|---|---|
| M1 | Groups reached | Delivery engine records each group; `sent` and `delivered` statuses |
| M2 | Delivery failures | `failed` status with a real Cloud API error code, title and detail |
| M3 | Pending deliveries | Derived from the gap between `sent` and `delivered`. No dedicated field exists |
| M4 | Link clicks | `/t/{token}`, a real redirect, one token per (campaign, group) |
| M5 | Media views | `/m/{token}`, a real landing page. A direct attachment reports nothing |
| M6 | User interactions | Replies and opt outs, from the bridge or the Meta webhook |
| M7 | Engagement index | Composite over collected data, not a WhatsApp reported figure |
| M8 | Custom metrics | Computed over the event store |
| M9 | Read statistics | `read` status, aggregated per group, with a modelled member count |

The **Feasibility** view in the application reads Meta's published constraints
live from the Cloud API adapter and shows them beside the metric table.

---

## Architecture

```
frontend/          single page app, no build step, vanilla JS
  index.html       shell
  app.js           views, router, charts (hand rolled SVG)
  styles.css       design tokens, light and dark

backend/           FastAPI + SQLAlchemy + SQLite
  app.py           routes, tracking endpoints, Meta webhook, scheduler
  db.py            data model, delivery states mirror the WhatsApp vocabulary
  dispatcher.py    queue, rate governor, retry, maturation heap
  analytics.py     metrics M1 to M9, interval snapshots, time series
  reports.py       Excel, CSV, PDF
  security.py      PBKDF2, sessions, RBAC matrix, Fernet, audit
  tokens.py        signed media tokens
  seed.py          5,000 groups, 4 users, 3 lists, 3 templates
  adapters/
    base.py        the ChannelAdapter contract
    simulator.py   default, sends nothing
    cloud_api.py   real Graph API calls, Groups API constraints documented
    linked_device.py  HTTP client for the bridge

bridge/            Node + Baileys, the real WhatsApp link
  server.js        QR login, group enumeration, send, inbound capture
```

**The channel abstraction is the point.** Campaign creation, group management,
analytics and reporting never talk to WhatsApp. They talk to a `ChannelAdapter`.
That is what lets the Week 1 proof of concept swap the despatch mechanism
without disturbing the rest of the build, exactly as Section 5.3 of the proposal
commits to.

### Despatch pipeline

```
campaign -> expand to one Delivery row per group -> durable queue
   -> N workers -> rate governor (token bucket, jitter, warm up ramp)
   -> adapter.send() -> sent | failed(+code)
   -> transient failure? backoff and requeue, up to 3 attempts
   -> maturation heap: delivered -> read -> click / reply / opt out
   -> queue drains -> campaign closes -> 4 snapshots scheduled
```

One time ordered heap drives all maturation, so 5,000 groups costs one
background loop rather than 10,000 coroutines.

---

## Using a real channel

### Official Cloud API and Groups API

```
set WDAP_PHONE_NUMBER_ID=...
set WDAP_ACCESS_TOKEN=...
set WDAP_WABA_ID=...
set WDAP_CHANNEL=cloud_api
run.bat
```

The adapter makes real Graph API calls, sends with
`"recipient_type": "group"`, and the webhook at `/webhooks/whatsapp` consumes
`sent`, `delivered`, `read` and `failed`. Point Meta at that URL with verify
token `WDAP_VERIFY_TOKEN`.

**It still cannot address the client's existing groups.** The Channels view
prints Meta's published constraints, read from the adapter.

### Linked device (the client's actual network)

```
cd bridge
npm install
npm start
```

Open **http://127.0.0.1:8787/qr**, scan with the handset that owns the number.
Then in the platform: **Channels > linked_device > Import groups from this
channel**. The real groups that account belongs to are enumerated and imported.
Set `WDAP_CHANNEL=linked_device` (or pick it per campaign) to despatch through it.

Start conservatively: `WDAP_SEND_RATE=1` and a small target list. The rate
governor is the primary protection for the account.

---

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `WDAP_CHANNEL` | `simulator` | Default despatch channel |
| `WDAP_TIME_SCALE` | `0.01` | Interval compression. `1` is production semantics |
| `WDAP_PORT` | `8000` | HTTP port |
| `WDAP_SEND_RATE` | `25` | Messages per second, nominal |
| `WDAP_SEND_JITTER` | `0.35` | Randomised spacing, fraction |
| `WDAP_WORKERS` | `8` | Despatch workers per campaign |
| `WDAP_DAILY_CEILING` | `200000` | Daily send ceiling |
| `WDAP_MAX_ATTEMPTS` | `3` | Retry attempts for transient failures |
| `WDAP_SIM_FAILURE` | `0.031` | Simulated failure rate |
| `WDAP_SIM_READ` | `0.72` | Simulated read rate |
| `WDAP_BRIDGE_URL` | `http://127.0.0.1:8787` | Linked device bridge |
| `WDAP_SECRET_KEY` | generated | Fernet key. Set it in production |

API docs are live at `/api/docs`.

---

## What is not built

Stated plainly, because a proof of concept that hides its gaps is not useful.

- **Backup and recovery.** The PoC is a SQLite file. Production is managed
  PostgreSQL with point in time recovery.
- **PostgreSQL, Redis and the queue** proposed in Section 8.2. SQLite and an
  in process asyncio queue stand in. The worker and queue semantics are the
  same; the durability guarantees are not.
- **The React frontend** proposed in Section 8.2. This UI is vanilla JS so it
  runs with no build step.
- **Multi factor authentication**, flagged in the proposal as "to be confirmed".
- **Single sign on**, optional in the proposal.
- **Multi number pooling.** The adapter registry accepts it; it is not exercised.
- **Per participant read breakdown.** The platform records an aggregate read
  count per group, which is what the official API returns. Whether a finer
  breakdown can be captured reliably at 5,000 group scale is precisely what the
  real Week 1 proof of concept has to establish.
- **Load and security testing** to the standard in Section 19.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Window flashes and closes on double click | An older `run.bat` called `exit /b` on failure | Fixed. The window now pauses on every error path |
| `Port 8000 is busy, using 8001 instead` | Something else holds the port | Nothing to do, the launcher already moved on |
| `No free port between 8000 and 8025` | All 26 ports taken | `set WDAP_PORT=9100 && run.bat` |
| Server starts then dies with `WSAEADDRINUSE` | Stale process from an earlier run | `netstat -ano \| findstr :8000` then `taskkill /PID <pid> /F` |
| `python` opens the Microsoft Store | Windows app execution alias | Settings > Apps > Advanced app settings > App execution aliases, switch off `python.exe` and `python3.exe` |
| Dependencies will not install | Offline or behind a proxy | Set `HTTPS_PROXY`, or install `requirements.txt` from an internal mirror |
| Port reported free but the server still fails to bind | A connect based probe was being used | Fixed. `tools/freeport.py` binds instead, which is what uvicorn does |

## Verification

`e2e` exercises the whole pipeline through the HTTP API. The last run:

```
487 groups despatched in 10.2s
reach 96.1%, 19 failures across 7 distinct Cloud API error codes
retries fired and were logged
read curve across snapshots: 158 -> 203 -> 288 -> 327
tracked link click recorded and attributed to a group
Excel 31,962 b | CSV 51,267 b | PDF 32,603 b
RBAC: viewer blocked from campaign.write, denial written to the audit trail
```

---

Gsure Technologies Private Limited | Sector 20, Panchkula, Haryana
info@gsuretech.com | Confidential

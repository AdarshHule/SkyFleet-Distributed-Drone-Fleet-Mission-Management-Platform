# SkyFleet — Learning Log

What I learned building SkyFleet, a distributed drone fleet and mission platform.
Each section lists the key ideas, what I measured in my own experiments, and the
limitations I know about.

---

## Lesson 0 — Setup and workflow

- Tools: Python 3.12 with `uv` (workspace with one shared lockfile), Docker, Git/GitHub CLI, Claude Code.
- Repo layout: `contracts/` (shared message schemas), `services/<name>/` (one package per service), `deploy/` (Docker Compose), `dashboard/` (React).
- Small commits with clear messages (`feat(...)`, `chore(...)`) make the history readable.
- Secrets never go in Git: real values live in `deploy/.env` (ignored), and `deploy/.env.example` documents the variable names.
- AI is a co-engineer, not a replacement: I review every change before accepting it, and log AI use in `AI_WORKFLOW.md`.

---

## Lesson 1 — Contracts (`contracts/`)

- Services share **messages**, not code or databases. One contracts package used by every service prevents silent mismatches (e.g. `battery` vs `battery_pct`).
- **Envelope pattern** — every message has the same wrapper:
  - `event_id`: unique per message, so consumers can drop duplicates
  - `event_type`: lets consumers route without reading the payload
  - `version`: lets the schema evolve without breaking old consumers
  - `occurred_at`: when it happened (timezone-aware UTC), not when it was received
  - `producer`: which service sent it
  - `correlation_id`: links all messages from one user action
- **Tolerant reader:** consumers ignore unknown fields (`extra="ignore"`), so a newer producer doesn't crash an older consumer. Risk: a renamed field is silently dropped. I saw this happen when my envelope used `source` while the test sent `producer`.
- Drones never report `OFFLINE`. A disconnected drone can't send anything, so offline is **inferred by the cloud** from silence.
- My `occurred_at` validator rejects naive datetimes and converts other timezones to UTC (10:00 IST → 04:30 UTC).
- Tests are the spec: write them first, then make them pass without editing them.

---

## Lesson 2 — Virtual drone (`services/edge/`)

- Split **physics** from **plumbing**. `step(dt)` only updates state (no sleeping, printing or networking), so a test can simulate 100 seconds in a millisecond. The loop in `main.py` stays thin.
- Internal state and telemetry differ: battery is a float inside the drone but an int in the contract, so the conversion happens at the boundary (`to_telemetry()`).
- I use `math.floor` for battery, not `round`: over-reporting charge on a drone is a safety risk. (Python's `round` also rounds halves to even: `round(98.5) == 98`.)
- Floating-point `% 360` can return exactly `360.0`, which my contract rejects. The guard in `heading_deg` prevents a rare crash. **Contracts catch real bugs.**
- Known limitation: at 0% battery the drone keeps flying. A real failsafe (return home or land) belongs in the Edge Agent.

---

## Lesson 3 — MQTT

**Concepts**
- A **broker** decouples publishers and subscribers; neither talks to the other directly.
- **Topics:** `skyfleet/{site_id}/{drone_id}/telemetry | commands | status | command_acks`.
- **Wildcards:** `+` matches one level, `#` matches everything below. In `skyfleet/+/SF-PN-001/#`, the `+` matches any *site*; the filter is on the drone ID.
- **QoS:** 0 = fire and forget, 1 = at least once (duplicates possible), 2 = exactly once (slow, rarely used).
- **Retained message:** the broker keeps the last message on a topic and gives it to new subscribers immediately. I use it for drone status.
- **Last Will (LWT):** the broker publishes it for a client that disconnects **without** saying goodbye. On a clean shutdown (Ctrl+C) the drone must publish `offline` itself.
- Topic builders live in `contracts/` because topics are part of the contract, and they reject `/`, `+` and `#` in IDs (topic injection).

**What I measured**
- `kill -9` → `offline` appeared **instantly**: the OS closed the TCP connection, so the broker saw an ungraceful disconnect.
- Frozen process (`kill -STOP`, simulating a network dropout) → `offline` after **15 s** = 1.5 × keepalive (10 s). A shorter keepalive detects failures faster but causes false alarms on weak 4G links.
- Broker outage of ~15 s → the drone printed 15 × `rc=4`, then reconnected, re-announced `online`, and **all 15 messages arrived in a burst**. Paho had queued them **in RAM**.
- `rc=0` means "queued", not "delivered". `rc=4` means "not connected" (but QoS 1 may still be queued). Delivery is only confirmed by the broker's PUBACK.
- `offline` really means "the cloud lost contact", not "the drone crashed". When the broker shut down, it published Last Wills for drones that were fine.

**Limitations this revealed**
- Paho's queue is in memory only: lost on a crash and unbounded during a long outage. The Edge Agent needs a **durable, bounded buffer** on disk.
- Reconnecting, resubscribing and re-announcing status is **my code's job**.

---

## Lesson 4 — Storing telemetry (`services/telemetry/`)

**Concepts**
- Two tables, two jobs (a light form of CQRS):
  - `telemetry_history` is append-only: every message, for replay and analysis.
  - `drone_latest_state` has one row per drone: "where is it now?" (fast reads for the dashboard).
- **The database enforces the rules, not Python.** With several replicas, "check, then insert" in Python is a race condition. Constraints are atomic.
  - Deduplication: `event_id` primary key + `ON CONFLICT (event_id) DO NOTHING`.
  - Latest state only moves forward: upsert with `WHERE EXCLUDED.occurred_at > drone_latest_state.occurred_at`.
- `received_at − occurred_at` shows how late each message arrived.
- Always pass values as **parameters** (`%(drone_id)s`), never with f-strings — that's how SQL injection happens.
- Both writes go in **one transaction** so the tables never disagree. Tests can't check this; it needs code review.
- **Poison messages** (invalid data) are logged and dropped, never fatal.
- **Persistent session** (`clean_session=False` + fixed client ID): the broker holds QoS 1 messages while my service is down.

**What I measured**
- Duplicate insert → `INSERT 0 0`. Without `ON CONFLICT` → `duplicate key value violates unique constraint`.
- Late message (10:00:02 after 10:00:05) → `INSERT 0 0`; latest state stayed at battery 89.
- Garbage on the telemetry topic → `rejected ... errors=1`, and the service kept running.
- Service stopped ~20 s while the drone flew → a burst on restart with lags up to ~20 s, and **nothing lost: the drone sent 44 messages, the service stored 44**. Count, don't eyeball: a "missing" second in the log was just timestamp drift.
- A 2.5-minute gap turned out to be the drone not running. I found it by querying the data instead of guessing.

**Limitations**
- A message with a **future timestamp** would freeze a drone's latest state.
- If Postgres goes down, the ingest worker crashes (nothing restarts it yet).
- Mosquitto has no persistence, so a broker restart loses held messages.
- Two replicas would both receive every message (dedup keeps it correct, but doubles the work). Fix later: MQTT shared subscriptions.

---

## Lesson 5 — Read API and API Gateway

**Telemetry read API (port 8001)**
- **Database per service:** only the telemetry service touches telemetry tables; others ask over HTTP.
- One service, two processes: the ingest worker and the read API share the database but scale separately.
- Three different contracts: the MQTT event, the DB row and the API response are separate on purpose.
- `def` (not `async def`) for endpoints using a **blocking** driver like psycopg; FastAPI runs them in a thread pool.
- Bounded queries: `limit` between 1 and 500 protects the database.
- `(drone_id,)` — the trailing comma makes a one-item tuple.

**Gateway (port 8000)**
- One front door for browsers; hides the internal layout; future home of auth and rate limiting.
- **Every network call needs a timeout** (2 s here).
- Error translation: down → **503**, too slow → **504**, upstream crash → **502**, not found → **404**. Never leak stack traces.
- Catch `httpx.TimeoutException` **before** `httpx.TransportError`, because it's a subclass.
- Validate the drone ID before using it in another URL (path injection).
- `async def` is right here because `httpx.AsyncClient` doesn't block.
- `httpx.MockTransport` fakes the telemetry service, so I can test timeouts and crashes that are hard to reproduce for real. A "spy" test proves no call was made at all.

**Live view (WebSocket)**
- Push instead of pull: the gateway pushes each position over a WebSocket.
- Same topic, opposite needs:
  - ingest worker: every message, QoS 1, persistent session, replay after downtime
  - live view: only the latest, QoS 0, clean session, no replay
- The live view is not the source of truth; a browser can always resync over REST.

**Gotchas I hit**
- All tests passed, but WebSockets returned 404: plain `uvicorn` has no WebSocket support. The fix was `uvicorn[standard]`. **Tests only prove what they exercise** — always run the real thing.
- `Address already in use` means the program is already running somewhere (`lsof -i :8000`).
- `localhost` may resolve to IPv6; `127.0.0.1` is unambiguous.

**Limitation:** one slow browser delays every viewer (broadcast is sequential). Fix later: a small per-client queue that drops old messages.

---

## Lesson 6 — Dashboard (`dashboard/`, React + TypeScript + Leaflet)

- **Snapshot, then stream:** fetch current state over REST, then let the WebSocket update it. Resync after **every** reconnect.
- **Newer wins**, a third time (SQL, Python, TypeScript): `mergeDrone` ignores anything not newer. This makes the race between the REST snapshot and the WebSocket stream safe — order doesn't matter.
- My `<=` in TypeScript matches `>` in SQL, including ties (the first message wins in both).
- **Compare instants, not strings:** `"10:00:06Z"` is newer than `"15:30:05+05:30"` even though it sorts lower as text.
- Return the **same object** when nothing changed and a **new object** when it did — that's how React decides to re-render.
- The UI infers **NO SIGNAL** after 5 s of silence instead of waiting for an `offline` message.
- **No CORS needed:** Vite's dev server proxies `/api` and `/ws` to the gateway, so the browser sees one origin.
- Edge case: an invalid timestamp makes `Date.parse` return `NaN`, and the message would be accepted. It can't happen today because the gateway validates first — defense in depth.
- The dashboard needs all backend services running. M4 will start everything with one command.

**Milestone M1 (walking skeleton) complete.**

---

## Lesson 7 — Commands (`services/command/`)

- **Two generals problem:** if no reply comes, the cloud can't tell a lost command from a lost ack. Fix: **retries + idempotency** (`command_id`, executed at most once by the drone).
- Commands **expire** (`expires_at`): a stale `RETURN_HOME` delivered after an outage could be dangerous.
- Acks arrive duplicated, late and out of order; the state machine must handle all of them without going backwards.
- **Expected weirdness vs. impossible events:** a duplicate ack is ignored; an ack for a command never sent raises `InvalidTransition` (bug or spoofing).
- The transition table is **data, not code**: easy to review and to test exhaustively (two stacked `parametrize` decorators = 24 cases).
- Terminal states are checked first, so late events after the end are ignored instead of raising.
- `AwareDatetime` rejects naive datetimes; `@model_validator(mode="after")` checks rules across several fields (GOTO needs a target).

---

## Tooling lessons

- Run `cd ~/Dev/SkyFleet` in every new terminal; relative paths only work from the repo root.
- zsh doesn't treat `#` as a comment interactively unless `setopt interactivecomments` is set.
- Long pastes into the terminal break easily; write files in the editor instead.
- SQL runs inside `psql`, not in zsh. Press `q` to leave psql's pager (`(END)`).
- `docker compose ... config --quiet` validates a compose file (no output = valid).
- `--reload` picks up code changes, not newly installed packages; restart for those.

---

## Explain-back questions (answer in my own words)

Writing these myself is the point: these are the questions an interviewer will ask.

1. Why does every message carry an `event_id`?
   - My answer:
2. Why is `OFFLINE` not a telemetry status?
   - My answer:
3. Why does `step()` take `dt` instead of sleeping inside?
   - My answer:
4. Why does the database, not Python, enforce deduplication when several replicas run?
   - My answer:
5. What does `received_at − occurred_at` tell me?
   - My answer:
6. Why must the gateway call the telemetry API instead of reading its tables?
   - My answer:
7. Why must every network call have a timeout?
   - My answer:
8. Why does the dashboard resync over REST after every WebSocket reconnect?
   - My answer:
9. Why must the command service save the state as SENT **before** publishing the command? What race happens otherwise?
   - My answer:
10. A drone completes a command after the cloud marked it `TIMED_OUT`. What should a real system do?
    - My answer:

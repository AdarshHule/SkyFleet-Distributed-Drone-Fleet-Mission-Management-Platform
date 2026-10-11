# AI Workflow

How I used AI tools while building SkyFleet: what they produced, what I wrote myself, what I changed or rejected, and where AI review caught real bugs.

My rule for the project: **AI can explain, scaffold and review, but I must be able to explain and defend every line in the repo.** Tests were written as the spec before the implementation, and every component was run and deliberately broken by me to confirm it behaves as claimed.

---

## Tools and how I used them

| Tool | Used for |
|---|---|
| **Claude (chat)** | Mentor and reviewer: lesson plans, concepts, test specs, scaffolding for plumbing code, code review of my implementations, debugging help from my terminal output, drafting docs |
| **Claude Code** | Terminal agent in the repo (Claude Pro), working under rules in `CLAUDE.md`: state a plan first, small diffs, never write secrets, don't edit `docs/` |
| **ChatGPT** | Initial project proposal; wrote `contracts/.../topics.py` |
| **Cursor** | Used briefly at the start; its output was discarded (see below) |

---

## Division of work

### What AI provided
- **Test suites as specifications** for each component. I implemented code to make them pass and did not edit the tests to get green results.
- **Plumbing and boilerplate:** MQTT client setup in the drone and services, FastAPI app scaffolds and connection pools, the command worker's main loop, SQL schemas, Docker Compose file, `geo.py` (distance and heading math), React hooks for the WebSocket and command polling, `App.tsx` layout and CSS.
- **Drafts of `LEARNING.md` and `README.md`**, written from my own experiment results and reviewed by me.

### What I wrote (the core logic in each lesson)
<!-- Verify this list: remove anything an AI tool wrote for you. -->
- Telemetry contract fields and validation rules (`TelemetryV1`, `DroneStatus`)
- First version of the message envelope, including the timezone validator that rejects naive datetimes and normalizes to UTC
- Drone physics: `step()` and `to_telemetry()`
- `TelemetryStore.save()`: both writes in one transaction
- The latest-state rule in SQL: `WHERE EXCLUDED.occurred_at > drone_latest_state.occurred_at`
- Telemetry service `on_message` with poison-message handling
- Telemetry read API endpoints (`get_drone`, `drone_history`)
- Gateway error translation (`call_telemetry`), later generalized to `call_upstream`
- Live view conversion (`to_live_message`)
- Dashboard merge rule (`mergeDrone`) and poll guard (`applyPoll`)
- Command state transition table and `apply()`
- `CommandStore.record_ack()` with row locking
- Command API `create_command` (idempotent replay returns 200)
- Outbox decision logic (`decide()`: expiry checked before attempts)
- Drone-side command validation and execution (`_reject_reason`, `_execute`)
- Gateway command proxy (`create_command`)

---

## Where AI review caught real bugs

| My code | Problem found in review | Fix |
|---|---|---|
| Envelope used `source` and a required string `schema_version` | Didn't match the contract (`producer`, integer `version`); with `extra="ignore"`, producer data was **silently dropped** | Renamed fields, integer version with default 1, added `correlation_id` |
| Battery reported with `round()` | Rounding can over-report charge (19.6% → 20%), a safety risk near alert thresholds | Switched to `math.floor` |
| Latest-state upsert I pasted was missing `status = EXCLUDED.status` | Drone status would never change after its first message | Restored the missing columns |
| Gateway WebSocket returned 404 although all tests passed | Plain `uvicorn` has no WebSocket support; the test client doesn't use uvicorn | Installed `uvicorn[standard]`; lesson: tests only prove what they exercise |
| Command state machine (Lesson 7) | No transition for a command that expires **before** it is ever sent; the outbox would crash on it | Added `(PENDING, GAVE_UP) → TIMED_OUT` with a test |

---

## What I rejected or changed

- **Cursor-generated code (start of project).** Cursor created a health endpoint, schema and README edits that I hadn't reviewed. I discarded all of it and restarted the repo from a clean skeleton, then set up rules so AI tools must propose a plan before editing.
- **ChatGPT's project scope.** The proposal used three brokers (MQTT, RabbitMQ, Redis) plus DynamoDB, Lambda and IoT Core. I kept the multi-service design but cut it to one broker for device traffic (MQTT) and Postgres, so every component would actually be finished and understood.
- **ChatGPT's `topics.py`.** Kept after review (correct and tested); I wrote the explanation of its validation logic in `LEARNING.md` to make sure I understood it.

---

## Debugging I did from evidence

AI helped interpret output, but these conclusions came from experiments I ran:
- A 2.5-minute gap in telemetry looked like message loss. Querying the stored positions showed the drone had restarted (back at its start point), so the messages never existed.
- An apparently "missing" second in the logs was timestamp drift; counting messages (44 sent, 44 stored) proved nothing was lost.
- Measured Last Will timing: instant on `kill -9` (OS closes the socket) vs. 15 s on a frozen process (1.5 × keepalive).
- A command showed `TIMED_OUT` because my acknowledgement arrived after 15 s; this exposed that retry timing must match real ack latency.

---

## Log

New entries go here: date · what I asked · what the tool produced · what I changed or rejected · what I learned.

<!-- Example:
- 2026-10-12 · Claude Code: scaffold the Fleet service package · created pyproject and api.py skeleton · rejected its extra DB table for sites; kept one table · learned to check generated schemas against the contract first
-->

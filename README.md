# SkyFleet

**A distributed drone fleet and command platform: virtual drones, live telemetry, and reliable cloud-to-drone commands.**

SkyFleet is a learning project that models the core problems of operating drones from the cloud: telemetry arriving late, duplicated or out of order; commands that get lost, retried or delivered after they're stale; and services that crash mid-operation. Every failure mode below was reproduced on purpose and the measured behaviour is documented in [`LEARNING.md`](LEARNING.md).

<!-- Add your demo recording here: drag the .mov/.gif into this file on GitHub -->

---

## What it does

- **Virtual drones** fly over Pune and publish telemetry once per second over MQTT.
- **Live map dashboard** (React + Leaflet) shows each drone's position, battery and status, and marks a drone **NO SIGNAL** after 5 s of silence.
- **Commands from the dashboard:** click the map to send a drone there (GOTO), or press **Land** / **Return home**. The command status is shown live: `PENDING → SENT → ACCEPTED → COMPLETED`, or `REJECTED` / `FAILED` / `TIMED_OUT`.
- **Commands survive failures:** retries with expiry, idempotency at three layers, and a transactional outbox, so a double-click, a lost acknowledgement or a crashed worker never causes a command to run twice or silently disappear.

---

## Architecture

```
                         ┌──────────────────────┐
                         │  Dashboard (React)   │
                         └──────────┬───────────┘
                            REST + WebSocket
                         ┌──────────▼───────────┐
                         │     API Gateway      │  timeouts, error translation,
                         │      (FastAPI)       │  live WebSocket fan-out
                         └───┬─────────────┬────┘
                      HTTP   │             │   HTTP
              ┌──────────────▼───┐   ┌─────▼──────────────┐
              │ Telemetry service│   │  Command service   │
              │  ingest worker   │   │  API + outbox      │
              │  + read API      │   │  worker            │
              └───┬─────────▲────┘   └──┬───────────▲─────┘
                  │         │           │           │
             Postgres       │       Postgres        │
          (telemetry DB)    │     (command DB)      │
                            │                       │
                 ┌──────────┴───────────────────────┴──────┐
                 │        MQTT broker (Mosquitto)          │
                 └──────────▲───────────────────────┬──────┘
                 telemetry, │                       │ commands
                 acks,      │                       │
                 status     │                       ▼
                 ┌──────────┴───────────────────────────────┐
                 │   Edge simulator: virtual drone +        │
                 │   command executor                       │
                 └──────────────────────────────────────────┘
```

| Component | Responsibility |
|---|---|
| `contracts/` | Shared Pydantic schemas: message envelope, telemetry, commands, acks, MQTT topic builders |
| `services/edge/` | Virtual drone physics, MQTT client, command executor with deduplication |
| `services/telemetry/` | Ingest worker (MQTT → Postgres) and read API (latest state, history) |
| `services/command/` | Command API, state machine, outbox worker (send, retry, give up), ack handling |
| `services/gateway/` | Single entry point for the browser: REST proxy and live WebSocket |
| `dashboard/` | React + TypeScript + Leaflet live map and command controls |

**MQTT topics:** `skyfleet/{site_id}/{drone_id}/telemetry | commands | command_acks | status`

---

## Key design decisions

### Telemetry
- **The database enforces correctness, not application code.** Duplicates are dropped by an `event_id` primary key with `ON CONFLICT DO NOTHING`; latest state only moves forward through a conditional upsert (`WHERE incoming.occurred_at > stored.occurred_at`). Both stay correct with several replicas writing at once, with no application-level locking.
- **History vs. latest state.** An append-only history table keeps every message (including late ones) for replay; a one-row-per-drone table serves the dashboard.
- **Event time, not arrival time.** Every message carries a UTC `occurred_at`; storing `received_at` as well measures how late data arrived.
- **Same topic, opposite needs.** The ingest worker uses QoS 1 with a persistent session (every message, replayed after downtime). The live view uses QoS 0 with a clean session (only fresh data, no replay).
- **Newer wins everywhere.** The same rule is applied in SQL, in Python and in the dashboard, so the race between a REST snapshot and the WebSocket stream can't move a drone backwards.

### Commands
- **Transactional outbox.** The API only writes a `PENDING` row. A single worker reads the outbox, marks each command `SENT` *before* publishing, and republishes anything unacknowledged. First send and retry are the same code path, and nothing is lost if the worker crashes.
- **Explicit state machine.** Transitions are a reviewed table. Duplicate and late acknowledgements are ignored; impossible events (an ack for a command never sent) raise an error. Terminal states never change.
- **Idempotency at three layers:**
  1. Browser: a `useRef` guard blocks double-clicks.
  2. API: an `Idempotency-Key` header maps a retried request to the same command (201 new, 200 replay).
  3. Drone: each `command_id` executes at most once; a duplicate gets the last acknowledgement re-sent instead of being re-executed.
- **Row locking (`SELECT … FOR UPDATE`)** prevents the retry worker and the ack handler from overwriting each other's state changes.
- **Commands expire.** Expired commands are never sent, and the drone rejects them on arrival. A newer command supersedes the active one, and a late duplicate of an old command can't undo it.

### Gateway
- Every upstream call has a **2 s timeout**. Failures are translated: unavailable → 503, timeout → 504, upstream error → 502; client errors (404, 422) are passed through. Path parameters are validated before they are used to build internal URLs.

---

## Measured behaviour

These come from experiments run locally (details in [`LEARNING.md`](LEARNING.md)):

| Scenario | Result |
|---|---|
| Drone process frozen (simulated network loss), keepalive 10 s | Broker published the drone's `offline` Last Will after **15 s** |
| Telemetry service stopped ~20 s while the drone kept flying | Broker held messages; burst delivered on restart; **44 sent, 44 stored** |
| Broker stopped ~15 s mid-flight | 15 messages queued in the drone's memory, all delivered after reconnect |
| Invalid message on the telemetry topic | Rejected and logged; service kept running |
| Same command delivered 3 times to the drone | Executed **once**; acknowledgement re-sent for the duplicates |
| Command sent to a drone that doesn't answer | 3 attempts, 5 s apart, then `TIMED_OUT` |
| Command created while the worker was down past its expiry | Never sent; marked `TIMED_OUT: expired before delivery` |

---

## Tech stack

Python 3.12 · FastAPI · Pydantic v2 · psycopg 3 · PostgreSQL 17 · MQTT (Mosquitto, paho-mqtt, aiomqtt) · React · TypeScript · Vite · Leaflet · pytest · Vitest · Docker Compose · uv workspaces

---

## Running locally

**Requirements:** Docker, [uv](https://docs.astral.sh/uv/), Node.js.

This manual setup will be replaced by a single `docker compose up` (in progress).

```bash
# 1. Infrastructure
cp deploy/.env.example deploy/.env
docker compose -f deploy/compose.yaml up -d
uv sync

# 2. Databases and schemas (first run only)
PSQL="docker compose -f deploy/compose.yaml exec -T postgres psql -U skyfleet"
for db in skyfleet_test skyfleet_command skyfleet_command_test; do $PSQL -d skyfleet -c "CREATE DATABASE $db"; done
for db in skyfleet skyfleet_test; do $PSQL -d $db < services/telemetry/sql/001_init.sql; done
for db in skyfleet_command skyfleet_command_test; do $PSQL -d $db < services/command/sql/001_init.sql; done
```

Then start each process in its own terminal (from the repo root):

| Process | Command |
|---|---|
| Telemetry ingest | `DATABASE_URL=postgresql://skyfleet:change-me-local-only@localhost:5432/skyfleet uv run python -m skyfleet_telemetry.main` |
| Telemetry API | `DATABASE_URL=postgresql://skyfleet:change-me-local-only@localhost:5432/skyfleet uv run uvicorn skyfleet_telemetry.api:app --port 8001` |
| Command API | `DATABASE_URL=postgresql://skyfleet:change-me-local-only@localhost:5432/skyfleet_command uv run uvicorn skyfleet_command.api:app --port 8002` |
| Command worker | `DATABASE_URL=postgresql://skyfleet:change-me-local-only@localhost:5432/skyfleet_command uv run python -m skyfleet_command.worker` |
| Gateway | `uv run uvicorn skyfleet_gateway.app:app --port 8000` |
| Drone | `uv run python -m skyfleet_edge.main` |
| Dashboard | `cd dashboard && npm install && npm run dev` → http://localhost:5173 |

The password above is a local development default from `.env.example`. Single-command startup is on the roadmap.

### Tests

```bash
uv run pytest -v                      # Python services (needs Postgres running)
cd dashboard && npx vitest run        # dashboard logic
```

---

## Known limitations

These are deliberate gaps, listed so they're visible rather than hidden:

- The drone buffers unsent telemetry **in memory only**; a crash during an outage loses it, and a long outage grows the buffer without limit.
- A telemetry message with a **future timestamp** would freeze that drone's latest state until real time catches up.
- The broker has **no persistence**; a broker restart loses messages held for disconnected clients.
- A drone acknowledgement that arrives **after** the cloud has given up is ignored, so a command can show `TIMED_OUT` even if the drone completed it.
- Retry timing (3 attempts, 5 s apart) is a fixed guess, not tuned from measured acknowledgement latency.
- The drone forgets which commands it has executed if it restarts.
- `site_id` is hard-coded in the dashboard (a Fleet service would own this).
- The live view broadcasts to browsers sequentially, so one slow client delays others.
- The command status uses polling; a push channel would scale better.
- No authentication yet, and MQTT runs without TLS (local development only).

---

## Roadmap

**In progress:**
- [ ] Dockerfiles for every service and single-command startup (`docker compose up`)
- [ ] Deployment on AWS (EC2, images in ECR) with a public demo URL
- [ ] GitHub Actions CI (tests on every push)

**Planned:**
- [ ] Fleet service (drones, sites) and Mission service (multi-waypoint missions)
- [ ] Durable, bounded telemetry buffer on the edge; alert service (low battery, no signal)
- [ ] Kubernetes manifests (kind), infrastructure as code (Terraform)

---

## How this was built

Built as a structured learning project: each component was designed, tested and then deliberately broken to observe failure behaviour. AI tools (Claude Code, Claude) were used as a co-engineer for explanations, boilerplate and reviews; design decisions, debugging and verification were done by me. The AI-assisted parts are logged in [`AI_WORKFLOW.md`](AI_WORKFLOW.md), and what I learned in each step is in [`LEARNING.md`](LEARNING.md).

**Author:** Adarsh Hule
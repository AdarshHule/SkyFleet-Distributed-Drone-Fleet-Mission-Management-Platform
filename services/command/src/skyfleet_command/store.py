from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from skyfleet_command.state import CommandEvent, CommandState, apply
from skyfleet_contracts import CommandAckV1, CommandType, Waypoint


def connect(url: str) -> psycopg.Connection:
    return psycopg.connect(url, autocommit=True, row_factory=dict_row)


class CommandStore:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def create(
        self,
        *,
        drone_id: str,
        site_id: str,
        command_type: CommandType,
        target: Waypoint | None,
        ttl_s: float,
        idempotency_key: str | None = None,
    ) -> tuple[dict, bool]:
        """Create a PENDING command. Returns (row, created).

        Same idempotency key twice -> the existing command, created=False.
        """
        row = self.conn.execute(
            """INSERT INTO commands (command_id, idempotency_key, drone_id, site_id, type,
                                     target_lat, target_lon, state, expires_at)
               VALUES (%(command_id)s, %(key)s, %(drone_id)s, %(site_id)s, %(type)s,
                       %(lat)s, %(lon)s, 'PENDING', now() + make_interval(secs => %(ttl)s))
               ON CONFLICT (idempotency_key) DO NOTHING
               RETURNING *""",
            {
                "command_id": uuid4(),
                "key": idempotency_key,
                "drone_id": drone_id,
                "site_id": site_id,
                "type": command_type.value,
                "lat": target.latitude if target else None,
                "lon": target.longitude if target else None,
                "ttl": ttl_s,
            },
        ).fetchone()
        if row is not None:
            return row, True
        existing = self.conn.execute(
            "SELECT * FROM commands WHERE idempotency_key = %s", (idempotency_key,)
        ).fetchone()
        return existing, False

    def get(self, command_id: UUID) -> dict | None:
        return self.conn.execute(
            "SELECT * FROM commands WHERE command_id = %s", (command_id,)
        ).fetchone()

    def _locked_state(self, command_id: UUID) -> CommandState | None:
        """Read the state and LOCK the row until the transaction ends."""
        row = self.conn.execute(
            "SELECT state FROM commands WHERE command_id = %s FOR UPDATE", (command_id,)
        ).fetchone()
        return CommandState(row["state"]) if row else None

    def mark_sent(self, command_id: UUID, retry_after_s: float) -> dict | None:
        """Record a send (first or retry). Call this BEFORE publishing."""
        with self.conn.transaction():
            state = self._locked_state(command_id)
            if state is None:
                return None
            new_state, _ = apply(state, CommandEvent.SENT)
            if new_state is not CommandState.SENT:
                return None  # already finished: nothing to send
            return self.conn.execute(
                """UPDATE commands
                   SET state = 'SENT', attempts = attempts + 1,
                       next_attempt_at = now() + make_interval(secs => %s),
                       updated_at = now()
                   WHERE command_id = %s
                   RETURNING *""",
                (retry_after_s, command_id),
            ).fetchone()

    def give_up(self, command_id: UUID, reason: str) -> bool:
        with self.conn.transaction():
            state = self._locked_state(command_id)
            if state is None:
                return False
            new_state, changed = apply(state, CommandEvent.GAVE_UP)
            if changed:
                self.conn.execute(
                    """UPDATE commands SET state = %s, reason = %s,
                           next_attempt_at = NULL, updated_at = now()
                       WHERE command_id = %s""",
                    (new_state.value, reason, command_id),
                )
            return changed

    def due_for_retry(self, limit: int = 100) -> list[dict]:
        return self.conn.execute(
            """SELECT * FROM commands
               WHERE state = 'SENT' AND next_attempt_at <= now()
               ORDER BY next_attempt_at
               LIMIT %s""",
            (limit,),
        ).fetchall()

    def record_ack(self, ack: CommandAckV1) -> bool:
        """Apply a drone ack. Returns True if the state changed."""
        with self.conn.transaction():
            state = self._locked_state(ack.command_id)
            if state is None:
                return False

            event = CommandEvent(ack.result.value)
            new_state, changed = apply(state, event)
            if not changed:
                return False

            self.conn.execute(
                """UPDATE commands
                   SET state = %s, reason = %s,
                       next_attempt_at = NULL, updated_at = now()
                   WHERE command_id = %s""",
                (new_state.value, ack.reason, ack.command_id),
            )
            return True

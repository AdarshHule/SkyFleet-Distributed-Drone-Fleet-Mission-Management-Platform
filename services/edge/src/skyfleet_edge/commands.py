from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from skyfleet_contracts import (
    AckResult,
    CommandAckV1,
    CommandRequestV1,
    CommandType,
    DroneStatus,
)
from skyfleet_edge.drone import AIRBORNE, VirtualDrone


@dataclass
class CommandExecutor:
    drone: VirtualDrone
    acks: dict[UUID, CommandAckV1] = field(default_factory=dict)
    active: UUID | None = None

    def handle(self, cmd: CommandRequestV1, now: datetime) -> list[CommandAckV1]:
        """A command arrived. Returns the acks to publish."""
        if cmd.command_id in self.acks:
            return [self.acks[cmd.command_id]]

        reason = self._reject_reason(cmd, now)
        if reason is not None:
            return [self._ack(cmd.command_id, AckResult.REJECTED, reason)]

        out = []
        if self.active is not None:
            out.append(
                self._ack(
                    self.active,
                    AckResult.FAILED,
                    f"superseded by {cmd.type}",
                )
            )

        self._execute(cmd)
        self.active = cmd.command_id
        out.append(self._ack(cmd.command_id, AckResult.ACCEPTED))
        out.extend(self.tick())
        return out

    def tick(self) -> list[CommandAckV1]:
        """Called after every physics step. Reports a finished command."""
        if self.active is not None and self.drone.status is DroneStatus.LANDED:
            done, self.active = self.active, None
            return [self._ack(done, AckResult.COMPLETED)]
        return []

    def _ack(
        self,
        command_id: UUID,
        result: AckResult,
        reason: str | None = None,
    ) -> CommandAckV1:
        ack = CommandAckV1(
            command_id=command_id,
            drone_id=self.drone.drone_id,
            result=result,
            reason=reason,
        )
        self.acks[command_id] = ack
        return ack

    def _reject_reason(self, cmd: CommandRequestV1, now: datetime) -> str | None:
        """Why this command can't run, or None if it can."""
        if now >= cmd.expires_at:
            return "expired"

        if cmd.drone_id != self.drone.drone_id:
            return "wrong drone"

        if (
            cmd.type in (CommandType.LAND, CommandType.RETURN_HOME)
            and self.drone.status not in AIRBORNE
        ):
            return "not flying"

        return None

    def _execute(self, cmd: CommandRequestV1) -> None:
        """Make the drone do it."""
        match cmd.type:
            case CommandType.GOTO:
                self.drone.fly_to(cmd.target.latitude, cmd.target.longitude)
            case CommandType.RETURN_HOME:
                self.drone.return_home()
            case CommandType.LAND:
                self.drone.land()

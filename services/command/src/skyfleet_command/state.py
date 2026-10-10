from enum import StrEnum


class CommandState(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


class CommandEvent(StrEnum):
    SENT = "SENT"  # published to the drone (first send or a retry)
    ACCEPTED = "ACCEPTED"  # drone ack
    REJECTED = "REJECTED"  # drone ack
    COMPLETED = "COMPLETED"  # drone ack
    FAILED = "FAILED"  # drone ack
    GAVE_UP = "GAVE_UP"  # no ack after the last retry


TERMINAL = frozenset(
    {
        CommandState.COMPLETED,
        CommandState.REJECTED,
        CommandState.FAILED,
        CommandState.TIMED_OUT,
    }
)


class InvalidTransition(Exception):
    """An event that should be impossible in this state: a bug or a spoofed message."""


S, E = CommandState, CommandEvent

TRANSITIONS: dict[tuple[CommandState, CommandEvent], CommandState] = {
    (S.PENDING, E.SENT): S.SENT,
    (S.SENT, E.SENT): S.SENT,
    (S.SENT, E.ACCEPTED): S.ACCEPTED,
    (S.ACCEPTED, E.ACCEPTED): S.ACCEPTED,
    (S.ACCEPTED, E.COMPLETED): S.COMPLETED,
    (S.SENT, E.COMPLETED): S.COMPLETED,
    (S.SENT, E.REJECTED): S.REJECTED,
    (S.SENT, E.FAILED): S.FAILED,
    (S.SENT, E.GAVE_UP): S.TIMED_OUT,
    (S.ACCEPTED, E.FAILED): S.FAILED,
    (S.PENDING, E.GAVE_UP): S.TIMED_OUT,  # expired before it was ever sent
}


def apply(state: CommandState, event: CommandEvent) -> tuple[CommandState, bool]:
    """Return (new_state, changed).

    Terminal states ignore events. Valid transitions return the resulting state;
    impossible transitions raise InvalidTransition.
    """
    if state in TERMINAL:
        return state, False

    new_state = TRANSITIONS.get((state, event))
    if new_state is not None:
        return new_state, new_state != state

    raise InvalidTransition(f"Invalid transition from {state} on event {event}")

import pytest

from skyfleet_command.state import (
    TERMINAL,
    CommandEvent as E,
    CommandState as S,
    InvalidTransition,
    apply,
)


def test_happy_path():
    state = S.PENDING
    for event, expected in [
        (E.SENT, S.SENT),
        (E.ACCEPTED, S.ACCEPTED),
        (E.COMPLETED, S.COMPLETED),
    ]:
        state, changed = apply(state, event)
        assert state is expected
        assert changed


def test_retry_keeps_sent():
    assert apply(S.SENT, E.SENT) == (S.SENT, False)


def test_no_ack_after_retries_times_out():
    assert apply(S.SENT, E.GAVE_UP) == (S.TIMED_OUT, True)


def test_lost_accepted_ack_still_completes():
    assert apply(S.SENT, E.COMPLETED) == (S.COMPLETED, True)


def test_duplicate_accepted_ack_is_harmless():
    assert apply(S.ACCEPTED, E.ACCEPTED) == (S.ACCEPTED, False)


def test_drone_can_reject_or_fail():
    assert apply(S.SENT, E.REJECTED) == (S.REJECTED, True)
    assert apply(S.ACCEPTED, E.FAILED) == (S.FAILED, True)


@pytest.mark.parametrize("terminal", sorted(TERMINAL))
@pytest.mark.parametrize("event", list(E))
def test_terminal_states_never_change(terminal, event):
    assert apply(terminal, event) == (terminal, False)


@pytest.mark.parametrize(
    "state,event",
    [
        (S.PENDING, E.ACCEPTED),  # an ack for a command we never sent
        (S.PENDING, E.COMPLETED),
        (S.ACCEPTED, E.SENT),  # retrying after the drone already accepted
        (S.ACCEPTED, E.GAVE_UP),
    ],
)
def test_impossible_events_raise(state, event):
    with pytest.raises(InvalidTransition):
        apply(state, event)


def test_command_can_expire_before_being_sent():
    assert apply(S.PENDING, E.GAVE_UP) == (S.TIMED_OUT, True)

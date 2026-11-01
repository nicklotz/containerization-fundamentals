import pytest

from bagtrack.checkpoints import CHECKPOINTS, IllegalMove, check_move, next_checkpoint


def test_checkpoints_are_in_journey_order():
    assert CHECKPOINTS == ("checked_in", "security", "sorted", "loaded", "unloaded", "claimed")


@pytest.mark.parametrize("current, expected", list(zip(CHECKPOINTS, CHECKPOINTS[1:])))
def test_next_checkpoint(current, expected):
    assert next_checkpoint(current) == expected


def test_claimed_is_the_last_checkpoint():
    assert next_checkpoint("claimed") is None


def test_unknown_checkpoint_is_an_error():
    with pytest.raises(ValueError):
        next_checkpoint("lost")


def test_move_to_next_checkpoint_is_allowed():
    check_move("sorted", "loaded")  # no exception


@pytest.mark.parametrize(
    "current, target",
    [
        ("checked_in", "sorted"),  # skips security
        ("loaded", "sorted"),  # goes backwards
        ("security", "security"),  # same checkpoint again
    ],
)
def test_other_moves_are_refused(current, target):
    with pytest.raises(IllegalMove, match="The next checkpoint is"):
        check_move(current, target)


def test_no_move_after_claimed():
    with pytest.raises(IllegalMove, match="last checkpoint"):
        check_move("claimed", "checked_in")

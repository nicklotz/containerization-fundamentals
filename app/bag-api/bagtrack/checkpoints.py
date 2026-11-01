"""The checkpoints a bag passes, in order, and the rule for moving between them.

This module has no web or database code, so the rule is easy to test on its own.
"""

from typing import Literal, get_args

# Every bag passes these checkpoints in this order.
Checkpoint = Literal["checked_in", "security", "sorted", "loaded", "unloaded", "claimed"]
CHECKPOINTS: tuple[str, ...] = get_args(Checkpoint)


class IllegalMove(ValueError):
    """A scan that skips a checkpoint, repeats one, or goes backwards."""


def next_checkpoint(current: str) -> str | None:
    """Return the checkpoint after `current`, or None if `current` is the last one."""
    if current not in CHECKPOINTS:
        raise ValueError(f"unknown checkpoint {current!r}")
    position = CHECKPOINTS.index(current)
    if position == len(CHECKPOINTS) - 1:
        return None
    return CHECKPOINTS[position + 1]


def check_move(current: str, target: str) -> None:
    """Raise IllegalMove unless `target` is the checkpoint right after `current`.

    The message completes a sentence that starts with "Bag BT123456".
    """
    expected = next_checkpoint(current)
    if expected is None:
        raise IllegalMove(f"cannot move from '{current}' because it is the last checkpoint")
    if target != expected:
        raise IllegalMove(
            f"cannot move from '{current}' to '{target}'. The next checkpoint is '{expected}'"
        )

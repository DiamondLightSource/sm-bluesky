from typing import Any

from bluesky import Msg
from bluesky.simulators import assert_message_and_return_remaining


def check_msg_set(msgs: list[Msg], obj: Any, value: Any) -> list[Msg]:
    return assert_message_and_return_remaining(
        msgs,
        lambda msg: msg.command == "set" and msg.obj is obj and msg.args[0] == value,
    )


def check_msg_wait(msgs: list[Msg], wait_group: str, wait: bool = False) -> list[Msg]:
    wait_msg = (
        {"group": wait_group}
        if wait
        else {"group": wait_group, "error_on_timeout": True, "timeout": None}
    )
    return assert_message_and_return_remaining(
        msgs,
        lambda msg: msg.command == "wait"
        and msg.obj is None
        and msg.kwargs == wait_msg,
    )


def check_mv_wait(
    msgs: list[Msg], wait_group: str, timeout: float | None = None
) -> list[Msg]:
    return assert_message_and_return_remaining(
        msgs,
        lambda msg: msg.command == "wait"
        and msg.obj is None
        and msg.kwargs == {"group": wait_group, "timeout": timeout},
    )

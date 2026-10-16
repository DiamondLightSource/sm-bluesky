import pytest

from sm_bluesky.common.math_functions import (
    cal_range_num,
    step_size_to_step_num,
    to_float,
)


@pytest.mark.parametrize(
    "test_input, expected_output",
    [
        (
            [5, -5, 0.1],
            (10, 0, 200),
        ),
        (
            [50.6, 55.4, 15],
            (-4.8, 106, 15),
        ),
        (
            [
                -1.1,
                -2.5,
                31,
            ],
            (1.4, -3.6, 1),
        ),
    ],
)
def test_slit_cal_range_num(
    test_input: list[float], expected_output: tuple[float]
) -> None:
    assert cal_range_num(*test_input) == pytest.approx(expected_output, 0.01)


@pytest.mark.parametrize(
    "start, end, step_size, expected",
    [
        (0.0, 10.0, 1.0, 10),
        (10.0, 0.0, 2.5, 4),
        (-5.0, 5.0, 3.0, 3),
    ],
)
def test_step_size_to_step_num(
    start: float, end: float, step_size: float, expected: int
) -> None:
    assert step_size_to_step_num(start, end, step_size) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (1, 1.0),
        (2.5, 2.5),
        ("-3.14", -3.14),
        (" 42 ", 42.0),
        ("1e-4", 1e-4),
        (None, None),
        ("not_a_number", None),
        (float("nan"), None),
        (float("inf"), None),
        (float("-inf"), None),
        ([], None),
        ({}, None),
    ],
)
def test_to_float(value, expected):
    assert to_float(value) == expected

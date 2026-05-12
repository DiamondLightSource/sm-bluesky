import math
from collections.abc import Mapping, Sequence

import pytest
from bluesky import RunEngine
from bluesky.protocols import Readable, Reading
from dodal.devices.electron_analyser.base import (
    AbstractEnergySource,
    BaseRegion,
    BaseSequence,
    DualEnergySource,
    GenericElectronAnalyserDetector,
)
from ophyd_async.sim import SimMotor

from sm_bluesky.electron_analyser.plans.analyser_scans import (
    analysercount,
    analyserscan,
    grid_analyserscan,
)
from tests.electron_analyser.util import (
    assert_mapped_data_equals_expected,
    expected_analyser_config,
)


def add_energy_source_monitor(energy_source: AbstractEnergySource) -> list[float]:
    energy_values = []

    def energy_monitor(reading: dict[str, Reading[float]], *args, **kwargs) -> None:
        value = reading[energy_source.energy.name]["value"]
        energy_values.append(value)

    energy_source.energy.subscribe_reading(energy_monitor)
    return energy_values


def assert_analyserscan_config(
    run_engine_documents: Mapping[str, list[dict[str, Reading]]],
    analyser: GenericElectronAnalyserDetector,
    sequence: BaseSequence[BaseRegion],
    energy_values: list[float],
) -> None:
    """Check that the configuration for the analyser device is correct."""
    drv = analyser._controller.driver

    configuration_region_names = []

    for i, descriptor in enumerate(run_engine_documents["descriptor"]):
        analyser_config = descriptor["configuration"][analyser.name]["data"]

        region_name = analyser_config[drv.region_name.name]
        configuration_region_names.append(region_name)

        region = sequence.get_region_by_name(region_name)
        assert region is not None

        epics_region = region.prepare_for_epics(energy_values[i])

        assert_mapped_data_equals_expected(
            analyser_config, expected_analyser_config(drv, epics_region)
        )

    assert configuration_region_names == sequence.get_enabled_region_names(), (
        "The saved region names are not same as the sequence region names!"
    )


def assert_other_devices_config(
    run_engine_documents: Mapping[str, list[dict[str, Reading]]],
    extra_detectors: Sequence[Readable],
    motors: Sequence[SimMotor],
) -> None:
    for descriptor in run_engine_documents["descriptor"]:
        for m in motors:
            assert descriptor["configuration"][m.name]["data"]
        for d in extra_detectors:
            assert descriptor["configuration"][d.name]["data"]


def assert_event_data(
    run_engine_documents: Mapping[str, list[dict[str, Reading]]],
    analyser: GenericElectronAnalyserDetector,
    sequence: BaseSequence,
    extra_detectors: Sequence[Readable],
    motors: Sequence[SimMotor],
    motor_iterations: int,
) -> None:
    number_of_regions = sequence.get_enabled_regions()
    assert (
        len(run_engine_documents["event"]) == len(number_of_regions) * motor_iterations
    )
    drv = analyser._controller.driver

    for event in run_engine_documents["event"]:
        event_data = event["data"]
        assert drv.spectrum.name in event_data
        assert drv.image.name in event_data
        assert drv.total_intensity.name in event_data
        for det in extra_detectors:
            assert det.name in event_data
        for m in motors:
            assert m.name in event_data


@pytest.fixture(params=[0, 1, 2])
def extra_detectors(
    request: pytest.FixtureRequest,
) -> list[Readable]:
    return [SimMotor("det" + str(i + 1)) for i in range(request.param)]


async def test_analysercount(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict[str, Reading]]],
    sim_analyser: GenericElectronAnalyserDetector,
    sequence: BaseSequence,
    extra_detectors: Sequence[Readable],
    dual_energy_source: DualEnergySource,
) -> None:
    energy_monitor_values = add_energy_source_monitor(dual_energy_source)
    run_engine(analysercount(sim_analyser, sequence, extra_detectors))
    assert_analyserscan_config(
        run_engine_documents,
        sim_analyser,
        sequence,
        energy_monitor_values,
    )
    assert_other_devices_config(run_engine_documents, extra_detectors, [])
    assert_event_data(
        run_engine_documents, sim_analyser, sequence, extra_detectors, [], 1
    )


@pytest.mark.parametrize(
    "args",
    [
        [SimMotor("motor1"), -10, 10],
        [SimMotor("motor1"), -10, 10, SimMotor("motor2"), -1, 1],
    ],
)
async def test_analyserscan(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict[str, Reading]]],
    sim_analyser: GenericElectronAnalyserDetector,
    sequence: BaseSequence,
    extra_detectors: Sequence[Readable],
    args: list[SimMotor | int],
    dual_energy_source: DualEnergySource,
) -> None:
    energy_monitor_values = add_energy_source_monitor(dual_energy_source)
    motor_iterations = 3
    run_engine(
        analyserscan(
            sim_analyser, sequence, extra_detectors, args, num=motor_iterations
        )
    )
    assert_analyserscan_config(
        run_engine_documents,
        sim_analyser,
        sequence,
        energy_monitor_values,
    )
    motors = [a for a in args if isinstance(a, SimMotor)]
    assert_other_devices_config(run_engine_documents, extra_detectors, motors)
    assert_event_data(
        run_engine_documents,
        sim_analyser,
        sequence,
        extra_detectors,
        motors,
        motor_iterations,
    )


@pytest.mark.parametrize(
    "args",
    [
        [SimMotor("motor1"), 1, 3, 3],
        [SimMotor("motor1"), 1, 3, 3, SimMotor("motor2"), 1, 2, 2],
    ],
)
async def test_grid_analyserscan(
    run_engine: RunEngine,
    run_engine_documents: Mapping[str, list[dict[str, Reading]]],
    sim_analyser: GenericElectronAnalyserDetector,
    sequence: BaseSequence,
    extra_detectors: Sequence[Readable],
    args: list[SimMotor | int],
    dual_energy_source: DualEnergySource,
) -> None:
    energy_monitor_values = add_energy_source_monitor(dual_energy_source)
    run_engine(grid_analyserscan(sim_analyser, sequence, extra_detectors, args))
    assert_analyserscan_config(
        run_engine_documents,
        sim_analyser,
        sequence,
        energy_monitor_values,
    )

    motors = [a for a in args if isinstance(a, SimMotor)]
    # For args, start at index 3, get every 4th value
    dimensions: list[int] = [v for v in args[3::4] if isinstance(v, int)]
    motor_iterations = math.prod(dimensions)
    assert_other_devices_config(run_engine_documents, extra_detectors, motors)
    assert_event_data(
        run_engine_documents,
        sim_analyser,
        sequence,
        extra_detectors,
        motors,
        motor_iterations,
    )

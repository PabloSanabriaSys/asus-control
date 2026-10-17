from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from asus_control.commands import AsusCtl, AuraBus
from asus_control.controller import HardwareController
from asus_control.fans import FanService
from asus_control.hardware import HardwareService
from asus_control.models import Brightness, FanMode, HardwareState, Profile
from asus_control.sensors import SysfsSensors
from asus_control.tasks import TaskRunner
from tests.conftest import FakeRunner
from tests.fake_asusd import FakeAsusd


@contextmanager
def no_lock() -> Iterator[None]:
    yield


def wait_until(condition: Callable[[], bool], timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise AssertionError("tiempo de espera agotado")
        QCoreApplication.processEvents()
        time.sleep(0.005)


class Recorder:
    def __init__(self, controller: HardwareController) -> None:
        self.states: list[HardwareState] = []
        self.notices: list[tuple[str, bool]] = []
        self.profiles: list[Profile | None] = []
        controller.state_changed.connect(self.states.append)
        controller.notice.connect(lambda text, error: self.notices.append((text, error)))
        controller.profile_checked.connect(self.profiles.append)


@pytest.fixture
def asusd() -> FakeAsusd:
    return FakeAsusd()


@pytest.fixture
def controller(qt_app: QApplication, asusd: FakeAsusd) -> Iterator[HardwareController]:
    client = AsusCtl(asusd)
    no_aura = FakeRunner(lambda _args: "")
    service = HardwareService(
        client, AuraBus(no_aura), FanService(client, no_lock), SysfsSensors(Path("/nonexistent"))
    )
    tasks = TaskRunner()
    yield HardwareController(service, tasks)
    tasks.shutdown()


def test_refresh_publishes_state(controller: HardwareController) -> None:
    recorder = Recorder(controller)

    controller.refresh()
    wait_until(lambda: bool(recorder.states))

    assert recorder.states[0].profile is Profile.BALANCED


def test_action_reports_success_and_new_state(
    controller: HardwareController, asusd: FakeAsusd
) -> None:
    recorder = Recorder(controller)

    controller.set_brightness(Brightness.LOW)
    wait_until(lambda: bool(recorder.states))

    assert asusd.brightness == "Low"
    assert recorder.notices == [("Iluminación: Bajo.", False)]
    assert recorder.states[-1].brightness is Brightness.LOW
    assert not controller.busy


def test_action_failure_is_reported_as_error(
    controller: HardwareController, asusd: FakeAsusd
) -> None:
    asusd.profile = "Quiet"
    recorder = Recorder(controller)

    controller.set_fan_mode(FanMode.ULTRA)
    wait_until(lambda: bool(recorder.notices))

    message, is_error = recorder.notices[0]
    assert is_error
    assert "Balanced" in message
    assert asusd.profile == "Quiet"


def test_second_action_is_ignored_while_busy(
    controller: HardwareController, asusd: FakeAsusd
) -> None:
    recorder = Recorder(controller)

    controller.set_charge_limit(80)
    controller.set_charge_limit(100)
    wait_until(lambda: bool(recorder.notices))

    assert asusd.charge_limit == 80
    assert len(recorder.notices) == 1


def test_external_profile_change_triggers_full_refresh(
    controller: HardwareController, asusd: FakeAsusd
) -> None:
    recorder = Recorder(controller)
    controller.refresh()
    wait_until(lambda: bool(recorder.states))

    asusd.profile = "Performance"
    controller.check_profile()
    wait_until(lambda: len(recorder.states) == 2)

    assert recorder.profiles == [Profile.PERFORMANCE]
    assert recorder.states[-1].profile is Profile.PERFORMANCE

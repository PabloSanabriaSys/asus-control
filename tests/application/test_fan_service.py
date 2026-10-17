from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from asus_control.application.fan_service import FanService
from asus_control.domain.errors import FanModeError, FanModeRequiresBalancedError, LockBusyError
from asus_control.domain.models import FanMode, Profile
from tests.fakes import FakePlatform, no_lock


def make_service(platform: FakePlatform) -> FanService:
    return FanService(platform, no_lock)


@pytest.mark.parametrize("mode", list(FanMode))
def test_applies_and_confirms_every_mode(mode: FanMode) -> None:
    service = make_service(FakePlatform())

    service.apply(mode)

    assert service.read_status().mode is mode


def test_normal_only_disables_custom_curves() -> None:
    platform = FakePlatform()

    make_service(platform).apply(FanMode.NORMAL)

    writes = [call for call in platform.calls if not call.startswith("get_")]
    assert writes == ["enable_fan_curves"]


@pytest.mark.parametrize("profile", [Profile.QUIET, Profile.PERFORMANCE])
def test_refuses_outside_balanced_without_changing_profile(profile: Profile) -> None:
    platform = FakePlatform(profile=profile)

    with pytest.raises(FanModeRequiresBalancedError):
        make_service(platform).apply(FanMode.ULTRA)

    assert platform.profile is profile
    assert platform.calls == ["get_profile"]


def test_partial_failure_restores_automatic_control() -> None:
    platform = FakePlatform(fail_on={"set_fan_curve": 2})

    with pytest.raises(FanModeError) as error:
        make_service(platform).apply(FanMode.EXTRA)

    assert (error.value.mode, error.value.restored) == (FanMode.EXTRA, True)
    assert not any(curve.enabled for curve in platform.curves.values())


def test_reports_when_restoration_also_fails() -> None:
    platform = FakePlatform(failing={"enable_fan_curves"})

    with pytest.raises(FanModeError) as error:
        make_service(platform).apply(FanMode.ULTRA)

    assert error.value.restored is False


def test_unconfirmed_write_is_reported_and_recovered() -> None:
    platform = FakePlatform(ignore_writes=True)

    with pytest.raises(FanModeError) as error:
        make_service(platform).apply(FanMode.ULTRA_MEGA)

    # Las curvas nunca llegaron a activarse: el control automático sigue vigente.
    assert error.value.restored is True


def test_busy_lock_prevents_any_access() -> None:
    platform = FakePlatform()

    @contextmanager
    def busy() -> Iterator[None]:
        raise LockBusyError
        yield

    with pytest.raises(LockBusyError):
        FanService(platform, busy).apply(FanMode.EXTRA)
    assert platform.calls == []

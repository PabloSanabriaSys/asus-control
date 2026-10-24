from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from asus_control.application.power_saving_service import PowerSavingService
from asus_control.domain.errors import HardwareAccessError
from asus_control.infrastructure.asusd import AsusdLightbar, AsusdPlatform, AuraDevice
from asus_control.infrastructure.busctl import Busctl
from asus_control.infrastructure.kde_power import KdePower
from asus_control.infrastructure.power_saving_device import PowerSavingHardware
from asus_control.infrastructure.power_saving_store import FilePowerSavingStore
from tests.conftest import FakeRunner
from tests.fakes import no_lock
from tests.infrastructure.fake_asusd_bus import FakeAsusdBus


def unsupported(_args: object) -> str:
    raise HardwareAccessError("Optional KDE capability unavailable")


def device(fake: FakeAsusdBus, path: Path) -> PowerSavingHardware:
    bus = Busctl(fake, "xyz.ljones.Asusd")
    aura = AuraDevice(bus)
    missing = Busctl(FakeRunner(unsupported), "missing")
    kde = KdePower(missing, missing, path)
    kde._power = missing
    kde._screen = FakeRunner(unsupported)
    return PowerSavingHardware(AsusdPlatform(bus, aura), AsusdLightbar(bus, aura), bus, kde)


def test_asus_round_trip_restores_mixed_custom_curves_and_automation(tmp_path: Path) -> None:
    fake = FakeAsusdBus(profile=1, auto_ac=False)
    fake.curves["CPU"][1] = [12, 24, 36, 48, 60, 72, 84, 96]
    fake.curves["CPU"][3] = True
    fake.quiet_curves["MID"][3] = True
    original_curves = deepcopy(fake.curves)
    original_quiet = deepcopy(fake.quiet_curves)
    original_leds = deepcopy(fake.led_power)
    hardware = device(fake, tmp_path / "powerdevilrc")
    store = FilePowerSavingStore(tmp_path / "state.json")
    saving = PowerSavingService(hardware, store, no_lock)

    saving.set_enabled(True)
    assert fake.profile == 2
    assert fake.charge_limit == 100
    assert not fake.auto_ac and not fake.auto_battery
    assert fake.brightness == 0
    assert fake.armoury["panel_overdrive"] == 0
    assert fake.armoury["dgpu_disable"] == 0
    assert not any(c[3] for c in fake.curves.values())
    assert not any(c[3] for c in fake.quiet_curves.values())
    assert fake.led_power[0] == original_leds[0]
    assert fake.led_power[1] == [2, False, False, False, False]
    assert "display.refresh" in saving.status().unavailable
    assert "gpu.configuration" in saving.status().unavailable

    # New service, same disk backup, different capabilities: restoration must not recapture.
    PowerSavingService(device(fake, tmp_path / "config"), store, no_lock).set_enabled(False)
    assert fake.profile == 1
    assert not fake.auto_ac and fake.auto_battery
    assert fake.brightness == 3
    assert fake.armoury["panel_overdrive"] == 1
    assert fake.curves == original_curves
    assert fake.quiet_curves == original_quiet
    assert fake.led_power == original_leds
    assert fake.charge_limit == 60
    assert store.load() is None


def test_absent_lightbar_is_never_written(tmp_path: Path) -> None:
    fake = FakeAsusdBus(power_zones=[1])
    hardware = device(fake, tmp_path / "config")
    saving = PowerSavingService(hardware, FilePowerSavingStore(tmp_path / "state"), no_lock)
    saving.set_enabled(True)
    saving.set_enabled(False)
    assert not any(call[0] == "set-property" and call[4] == "LedPower" for call in fake.calls)


def test_new_sessions_never_capture_screen_brightness(tmp_path: Path) -> None:
    hardware = device(FakeAsusdBus(), tmp_path / "config")
    capture = hardware.capture()
    assert "display.brightness" not in {s.key for s in capture.settings}
    assert "display.brightness" not in capture.unavailable


def test_external_charge_limit_change_is_reverted_then_original_is_restored(tmp_path: Path) -> None:
    fake = FakeAsusdBus(charge_limit=80)
    saving = PowerSavingService(
        device(fake, tmp_path / "config"), FilePowerSavingStore(tmp_path / "state"), no_lock
    )
    saving.set_enabled(True)
    assert fake.charge_limit == 100
    fake.charge_limit = 60
    assert not next(c for c in saving.inspect().checks if c.key == "battery.chargeLimit").confirmed
    saving.reconcile()
    assert fake.charge_limit == 100
    saving.set_enabled(False)
    assert fake.charge_limit == 80

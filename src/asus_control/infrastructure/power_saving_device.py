"""Snapshot-capable settings; every target has an exact, readable inverse."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from functools import partial

from asus_control.application.ports import LightbarPort, PlatformPort
from asus_control.domain.errors import HardwareAccessError
from asus_control.domain.models import Brightness, Fan, FanCurve, LightbarState, Profile
from asus_control.domain.power_saving import PowerSavingCapture, SavedSetting
from asus_control.infrastructure.asusd import PROFILE_CODES
from asus_control.infrastructure.busctl import Busctl
from asus_control.infrastructure.gpu import AsusGpu
from asus_control.infrastructure.kde_power import KdePower, encode, policy_targets

PLATFORM_PATH = "/xyz/ljones"
PLATFORM_INTERFACE = "xyz.ljones.Platform"


@dataclass(frozen=True)
class _Control:
    read: Callable[[], str]
    write: Callable[[str], None]
    target: Callable[[str], str]


def _fixed(value: str) -> Callable[[str], str]:
    return lambda _original: value


class PowerSavingHardware:
    def __init__(
        self, platform: PlatformPort, lightbar: LightbarPort, bus: Busctl, kde: KdePower
    ) -> None:
        self._platform = platform
        self._lightbar = lightbar
        self._bus = bus
        self._kde = kde
        self._gpu = AsusGpu(bus)
        self._controls = self._build_controls()

    def _build_controls(self) -> dict[str, _Control]:
        # Reload desktop policy first; it can affect the active profile and brightness.
        controls = {
            "desktop.policy": _Control(
                self._read_policy,
                self._kde.write_policy,
                self._policy_target,
            )
        }
        for key, name in (
            ("platform.autoAc", "ChangePlatformProfileOnAc"),
            ("platform.autoBattery", "ChangePlatformProfileOnBattery"),
        ):
            controls[key] = _Control(
                partial(self._read_bool, name),
                partial(self._write_bool, name),
                _fixed("false"),
            )
        for profile in (Profile.BALANCED, Profile.QUIET):
            controls[f"fans.{profile.value.lower()}"] = _Control(
                partial(self._read_fans, profile),
                partial(self._write_fans, profile),
                self._automatic_fans,
            )
        controls.update(
            {
                "lighting.lightbar": _Control(
                    self._read_lightbar,
                    self._write_lightbar,
                    _fixed(encode(asdict(LightbarState(False, False, False, False)))),
                ),
                "display.refresh": _Control(
                    self._kde.read_refresh,
                    self._kde.write_refresh,
                    lambda _value: self._kde.refresh_target(),
                ),
                "display.brightness": _Control(
                    self._kde.read_legacy_brightness,
                    self._kde.write_legacy_brightness,
                    lambda value: value,
                ),
                "panel.overdrive": _Control(
                    self._read_overdrive, self._write_overdrive, _fixed("0")
                ),
                "lighting.keyboard": _Control(
                    lambda: self._platform.get_brightness().value,
                    lambda value: self._platform.set_brightness(Brightness(value)),
                    _fixed(Brightness.OFF.value),
                ),
                "battery.chargeLimit": _Control(
                    lambda: str(self._platform.get_charge_limit()),
                    lambda value: self._platform.set_charge_limit(int(value)),
                    _fixed("100"),
                ),
                "gpu.configuration": _Control(
                    self._gpu.read,
                    self._gpu.write,
                    self._gpu.integrated_target,
                ),
                # Restore the profile last, after PowerDevil reload and asusd automatic settings.
                "platform.profile": _Control(
                    lambda: self._platform.get_profile().value,
                    lambda value: self._platform.set_profile(Profile(value)),
                    _fixed(Profile.QUIET.value),
                ),
            }
        )
        return controls

    def capture(self) -> PowerSavingCapture:
        settings: list[SavedSetting] = []
        unavailable: list[str] = []
        # Verify the essential control before collecting optional capabilities.
        self._platform.get_profile()
        for key, control in self._controls.items():
            if key == "display.brightness":
                continue  # Restore old snapshots only; never manage screen brightness again.
            try:
                original = self.read(key)
                target = control.target(original)
            except HardwareAccessError:
                if key in ("platform.profile", "battery.chargeLimit"):
                    raise
                unavailable.append(key)
            else:
                settings.append(SavedSetting(key, original, target))
        return PowerSavingCapture(tuple(settings), tuple(unavailable))

    def restart_required(self, key: str, value: str) -> bool:
        return key == "gpu.configuration" and self._gpu.restart_required(value)

    def read(self, key: str) -> str:
        try:
            return self._controls[key].read()
        except (KeyError, ValueError, TypeError, StopIteration) as exc:
            raise HardwareAccessError(f"Cannot read {key}: {exc}") from exc

    def write(self, key: str, value: str) -> None:
        try:
            self._controls[key].write(value)
        except (KeyError, ValueError, TypeError) as exc:
            raise HardwareAccessError(f"Cannot write {key}: {exc}") from exc

    def _read_bool(self, name: str) -> str:
        value = self._bus.get_property(PLATFORM_PATH, PLATFORM_INTERFACE, name)
        if type(value) is not bool:
            raise HardwareAccessError(f"Invalid boolean: {name}")
        return encode(value)

    def _write_bool(self, name: str, value: str) -> None:
        self._bus.set_property(PLATFORM_PATH, PLATFORM_INTERFACE, name, "b", json.loads(value))

    def _read_fans(self, profile: Profile) -> str:
        return encode(
            [asdict(curve) for _, curve in sorted(self._platform.get_fan_curves(profile).items())]
        )

    def _write_fans(self, profile: Profile, value: str) -> None:
        curves = [
            FanCurve(Fan(item["fan"]), tuple(item["pwm"]), tuple(item["temps"]), item["enabled"])
            for item in json.loads(value)
        ]
        self._platform.enable_fan_curves(profile, False)
        for curve in curves:
            self._platform.set_fan_curve(profile, curve)
        for curve in curves:
            self._bus.call(
                PLATFORM_PATH,
                "xyz.ljones.FanCurves",
                "SetProfileFanCurveEnabled",
                "usb",
                PROFILE_CODES[profile],
                curve.fan.value,
                curve.enabled,
            )

    @staticmethod
    def _automatic_fans(original: str) -> str:
        return encode([dict(item, enabled=False) for item in json.loads(original)])

    def _read_lightbar(self) -> str:
        state = self._lightbar.read()
        if state is None:
            raise HardwareAccessError("No lightbar support")
        return encode(asdict(state))

    def _write_lightbar(self, value: str) -> None:
        self._lightbar.write(LightbarState(**json.loads(value)))

    def _read_policy(self) -> str:
        self._kde.check_policy_support()
        return self._kde.read_policy(
            [
                *policy_targets(True),
                *(
                    f"{p}][Display/UseProfileSpecificDisplayBrightness"
                    for p in ("AC", "Battery", "LowBattery")
                ),
            ]
        )

    def _policy_target(self, original: str) -> str:
        targets = policy_targets(self._kde.can_suspend())
        return encode(dict(json.loads(original), **targets))

    def _read_overdrive(self) -> str:
        value = self._bus.get_property(
            "/xyz/ljones/asus_armoury/panel_overdrive", "xyz.ljones.AsusArmoury", "CurrentValue"
        )
        if type(value) is not int or value not in (0, 1):
            raise HardwareAccessError("Invalid panel overdrive value")
        return encode(value)

    def _write_overdrive(self, value: str) -> None:
        self._bus.set_property(
            "/xyz/ljones/asus_armoury/panel_overdrive",
            "xyz.ljones.AsusArmoury",
            "CurrentValue",
            "i",
            int(value),
        )

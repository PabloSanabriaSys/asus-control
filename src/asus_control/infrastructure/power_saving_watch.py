"""Small user-session worker. No hardware reads or writes while battery saving is off."""

from __future__ import annotations

import logging
import signal
import threading
import time

from asus_control.application.power_saving_service import PowerSavingService
from asus_control.domain.errors import AsusControlError
from asus_control.infrastructure.sysfs import SysfsSensors

logger = logging.getLogger(__name__)
CHECK_SECONDS = 15
RECONCILE_SECONDS = 60


def watch(saving: PowerSavingService) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda _signum, _frame: stopped.set())
    signal.signal(signal.SIGINT, lambda _signum, _frame: stopped.set())
    sensors = SysfsSensors()
    last_reconcile = float("-inf")
    previous_ac: bool | None = None
    sleep_offset = time.clock_gettime(time.CLOCK_BOOTTIME) - time.monotonic()
    while not stopped.is_set():
        try:
            session = saving.status()
            if session is not None:
                battery = sensors.read_battery()
                ac_online = battery.ac_online if battery else None
                offset = time.clock_gettime(time.CLOCK_BOOTTIME) - time.monotonic()
                if (
                    time.monotonic() - last_reconcile >= RECONCILE_SECONDS
                    or ac_online != previous_ac
                    or offset - sleep_offset > 1
                    or session.pending
                ):
                    saving.reconcile()
                    last_reconcile = time.monotonic()
                previous_ac = ac_online
                sleep_offset = offset
            else:
                last_reconcile = float("-inf")
        except AsusControlError:
            logger.exception("Battery-saving reconciliation will be retried")
        stopped.wait(CHECK_SECONDS)
    return 0

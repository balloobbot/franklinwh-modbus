"""FranklinWH aGate control over Modbus TCP.

The aGate speaks the SunSpec IEEE 1547 profile — models 1, 502 and 701-715 —
plus a block of manufacturer registers at 15500. All of it is reached through
`modbus-connection <https://github.com/home-assistant-libs/modbus-connection>`_,
whose typed components and planned block reads replace the pysunspec2 client
this library used to drive.

Example::

    import asyncio
    from franklinwh_modbus import AGate, VirtualMode, VirtualModeController

    async def main() -> None:
        agate = AGate("192.168.1.100")
        await agate.async_connect()
        print(agate.battery_status())

        modes = VirtualModeController(agate)
        await modes.async_set_mode(VirtualMode.SELF_CONSUMPTION)
        await modes.async_run(duration_s=3600)
        await agate.async_close()

    asyncio.run(main())
"""

from __future__ import annotations

from .curves import CurveError, CurvePoint, read_curve, read_trip_curve, write_curve
from .device import AGate, AGateError, UpdateReport
from .models import MODELS
from .models.extensions import Extensions, OnGridMode
from .modes import VirtualModeController, run_with_signal_handling
from .safety import SAFETY_MARGIN_PCT, check_state, validate_soc_safety
from .schedule import DEFAULT_SCHEDULE, TOUSchedule
from .sequencer import Sequencer, SequenceError, TransitionValidationError
from .sync import SyncAGate
from .types import (
    ALARM_BITS,
    DEFAULT_MAX_POWER_W,
    ONGRID_MODES,
    PICS_STATUS,
    BatteryCommand,
    ControlMode,
    HealthStatus,
    VirtualMode,
)
from .writing import WriteRejected, write_across, write_many, write_verified

__version__ = "0.10.0"

__all__ = [
    "ALARM_BITS",
    "DEFAULT_MAX_POWER_W",
    "DEFAULT_SCHEDULE",
    "MODELS",
    "ONGRID_MODES",
    "PICS_STATUS",
    "SAFETY_MARGIN_PCT",
    "AGate",
    "AGateError",
    "BatteryCommand",
    "ControlMode",
    "CurveError",
    "CurvePoint",
    "Extensions",
    "HealthStatus",
    "OnGridMode",
    "SequenceError",
    "Sequencer",
    "SyncAGate",
    "TOUSchedule",
    "TransitionValidationError",
    "UpdateReport",
    "VirtualMode",
    "VirtualModeController",
    "WriteRejected",
    "check_state",
    "read_curve",
    "read_trip_curve",
    "run_with_signal_handling",
    "validate_soc_safety",
    "write_curve",
    "write_many",
    "write_across",
    "write_verified",
]

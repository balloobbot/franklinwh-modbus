"""A blocking facade over :class:`~franklinwh_modbus.device.AGate`.

modbus-connection is async all the way down, which is right for the library and
wrong for the two things that consume it here: a rich terminal UI with a raw
keyboard thread, and an argparse CLI. Both are blocking loops, and rewriting
them around an event loop would buy nothing.

So this owns one background event loop in a daemon thread and submits
coroutines to it. Everything the async device exposes is here without the
``async_`` prefix, so the two surfaces stay recognisably the same.
"""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING, Any

from .device import AGate

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from .device import UpdateReport
    from .models.extensions import Extensions, OnGridMode
    from .types import BatteryCommand, HealthStatus

__all__ = ["SyncAGate"]


class SyncAGate:
    """Drive an :class:`AGate` from synchronous code."""

    def __init__(self, host: str, **options: Any) -> None:
        """Create the device and the loop it runs on; nothing connects yet."""
        self._device = AGate(host, **options)
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop, name=f"franklinwh-{host}", daemon=True
        )
        self._thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run[T](self, coroutine: Coroutine[Any, Any, T]) -> T:
        """Run a coroutine on the background loop and wait for its result."""
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop).result()

    # -- lifecycle ------------------------------------------------------------

    @property
    def device(self) -> AGate:
        """The async device underneath, for code that can await."""
        return self._device

    @property
    def connected(self) -> bool:
        """Whether the link is up."""
        return self._device.connected

    def connect(self) -> None:
        """Connect, scan the model chain and take the first reading."""
        self._run(self._device.async_connect())

    def reconnect(self) -> bool:
        """Re-establish a dropped link; ``False`` if it could not be made."""
        try:
            self._run(self._device.async_connect())
        except Exception:  # noqa: BLE001 — the caller only needs the verdict
            return False
        return True

    def disconnect(self) -> None:
        """Drop the link, keeping the device reusable."""
        self._run(self._device.async_disconnect())

    def close(self) -> None:
        """Close the connection and stop the background loop."""
        try:
            self._run(self._device.async_close())
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=5)

    def __enter__(self) -> SyncAGate:
        self.connect()
        return self

    def __exit__(self, *exception: object) -> None:
        self.close()

    def update(self) -> UpdateReport:
        """Refresh every component, reporting which ones came back."""
        return self._run(self._device.async_update())

    def update_readings(self) -> UpdateReport:
        """Refresh only what the aGate measures."""
        return self._run(self._device.async_update_readings())

    def update_settings(self) -> UpdateReport:
        """Refresh only what the aGate has been configured to do."""
        return self._run(self._device.async_update_settings())

    def read_raw(self) -> dict[str, dict[int, int | bool]]:
        """Every register this device reads, undecoded — for diagnostics."""
        return self._run(self._device.async_read_raw())

    # -- reads (all served from the last update) ------------------------------

    @property
    def models(self) -> dict[int, Any]:
        """The discovered models, by SunSpec model ID."""
        return self._device.models

    @property
    def extensions(self) -> Extensions:
        """The FranklinWH manufacturer register block."""
        return self._device.extensions

    def model(self, model_id: int) -> Any:
        """One discovered model, or ``None``."""
        return self._device.model(model_id)

    def nameplate(self) -> dict[str, str]:
        """Manufacturer, model, serial and firmware version."""
        return self._device.nameplate()

    def battery_status(self) -> dict[str, Any]:
        """State of charge and DC-side battery telemetry."""
        return self._device.battery_status()

    def grid_status(self) -> dict[str, Any]:
        """AC-side measurements."""
        return self._device.grid_status()

    def solar_status(self) -> dict[str, Any]:
        """PV production."""
        return self._device.solar_status()

    def control_status(self) -> dict[str, Any]:
        """The active power setpoint and its reversion state."""
        return self._device.control_status()

    def native_mode(self) -> dict[str, Any]:
        """The FranklinWH operating mode and both SOC reserves."""
        return self._device.native_mode()

    def home_load_w(self) -> float:
        """Home load in watts."""
        return self._device.home_load_w()

    def effective_reserve_level(self) -> tuple[int | None, str]:
        """The SOC reserve the active mode honours."""
        return self._device.effective_reserve_level()

    def alarms(self) -> dict[str, Any]:
        """The alarm bitfields, with the system alarm decoded."""
        return self._device.alarms()

    def blocking_alarms(self) -> tuple[bool, list[str]]:
        """Whether control is safe right now, and why not if it is not."""
        return self._device.blocking_alarms()

    def check_state(self) -> dict[str, Any]:
        """What the device is doing, and whether something else is driving it."""
        return self._device.check_state()

    def validate_soc_safety(
        self, target_soc: float, current_soc: float, operation: str
    ) -> tuple[bool, str, dict[str, Any]]:
        """Whether a charge or discharge to ``target_soc`` is safe to start."""
        return self._device.validate_soc_safety(target_soc, current_soc, operation)

    def lifetime_energy(self) -> dict[str, float]:
        """Lifetime accumulators."""
        return self._device.lifetime_energy()

    def healthcheck(self) -> HealthStatus:
        """Whether the device is in a state worth driving."""
        return self._device.healthcheck()

    @property
    def max_charge_w(self) -> float:
        """The battery's charge rate ceiling."""
        return self._device.max_charge_w

    @property
    def max_discharge_w(self) -> float:
        """The battery's discharge rate ceiling."""
        return self._device.max_discharge_w

    # -- writes ---------------------------------------------------------------

    def set_native_mode(self, mode: OnGridMode | int) -> None:
        """Set the operating mode, preserving both reserves."""
        self._run(self._device.async_set_native_mode(mode))

    def set_self_consumption_reserve(self, percent: int) -> None:
        """Set the SOC floor held in Self-Consumption mode."""
        self._run(self._device.async_set_self_consumption_reserve(percent))

    def set_tou_reserve(self, percent: int) -> None:
        """Set the SOC floor held in Time-of-Use mode."""
        self._run(self._device.async_set_tou_reserve(percent))

    def send_command(
        self, command: BatteryCommand, *, duration_s: float | None = None
    ) -> float:
        """Drive the battery to a power setpoint; returns the percent written."""
        return self._run(
            self._device.async_send_command(command, duration_s=duration_s)
        )

    def clear_alarms(self) -> None:
        """Pulse the alarm-reset register."""
        self._run(self._device.async_clear_alarms())

    def reset_control_state(self) -> None:
        """Hand control back to the device."""
        self._run(self._device.async_reset_control_state())

    def cancel_command_timer(self) -> None:
        """Cancel a pending command timeout."""
        self._loop.call_soon_threadsafe(self._device.cancel_command_timer)

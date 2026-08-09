"""Software control modes: decide a battery setpoint, then hold it.

The aGate's own modes live in a manufacturer register (see
``models.extensions``). These are the *virtual* modes: a control loop that
computes a power setpoint from solar, load and SOC each tick and writes it
through model 704. That is why the loop has to release control on the way out —
the device's own reversion timer counts down without ever reverting.

A caveat carried over unchanged from before the migration: the sign convention
is not consistent across the mode calculators. ``BatteryCommand`` documents
positive as charge, and most of the arithmetic here follows it, but
self-consumption returns ``-max_charge_w`` for "charge flat out", and both
peak-shave and the time-of-use discharge branch return a *positive* number to
discharge. These are reproduced exactly rather than corrected, because they are
what the shipped behaviour is and no hardware was available to re-tune against.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
import time
from typing import TYPE_CHECKING, Any

from .schedule import TOUSchedule
from .types import BatteryCommand, ControlMode, VirtualMode

if TYPE_CHECKING:
    from collections.abc import Callable

    from .device import AGate

_LOGGER = logging.getLogger(__name__)

#: How often the control loop recomputes and rewrites the setpoint.
TICK_INTERVAL_S = 5.0
#: Consecutive failed ticks before the loop gives up.
MAX_CONSECUTIVE_FAILURES = 5
#: How often the loop re-checks whether the grid is still there.
OFF_GRID_CHECK_INTERVAL_S = 30.0
ALARM_CHECK_INTERVAL_S = 60.0
SANITY_CHECK_INTERVAL_S = 30.0

#: Absolute SOC bounds, below/above which no charge/discharge is issued at all.
SOC_HARD_MAX = 99.5
SOC_HARD_MIN = 0.5


class VirtualModeController:
    """Hold a battery setpoint computed from the current system state."""

    def __init__(
        self,
        device: AGate,
        *,
        max_charge_soc: int = 100,
        min_discharge_soc: int | None = None,
        soc_ramp_window: int = 10,
        force_soc_limits: bool = False,
        grid_import_limit_w: float | None = None,
        grid_export_limit_w: float | None = None,
        battery_charge_limit_w: float | None = None,
        battery_discharge_limit_w: float | None = None,
    ) -> None:
        """Configure the loop against a connected device.

        ``min_discharge_soc`` defaults to whichever SOC reserve the aGate's own
        active mode honours, so the software loop does not fight it.
        """
        self.device = device
        self.mode = VirtualMode.SELF_CONSUMPTION
        self.tou = TOUSchedule()

        self.self_reserve_pct = 20
        self.backup_target_soc = 95
        self.target_soc = 100
        self.grid_zero_buffer = 100
        self.peak_shave_threshold = 2000
        self.manual_power_w = 0.0

        self.max_charge_soc = max_charge_soc
        self.soc_ramp_window = soc_ramp_window
        self.force_soc_limits = force_soc_limits

        self.grid_import_limit_w = grid_import_limit_w
        self.grid_export_limit_w = grid_export_limit_w
        self.battery_charge_limit_w = battery_charge_limit_w
        self.battery_discharge_limit_w = battery_discharge_limit_w

        if min_discharge_soc is None:
            reserve, _ = device.effective_reserve_level()
            self.min_discharge_soc = reserve if reserve is not None else 20
        else:
            self.min_discharge_soc = min_discharge_soc

        self._last_commanded_power = 0.0
        self._last_logged_power: float | None = None
        self._last_safety_reason: str | None = None
        self._warned_high_load = False
        self._off_grid_warned = False

    # -- state ----------------------------------------------------------------

    @property
    def max_charge_w(self) -> float:
        """The battery's charge ceiling, from the device's nameplate."""
        return self.device.max_charge_w

    @property
    def max_discharge_w(self) -> float:
        """The battery's discharge ceiling, from the device's nameplate."""
        return self.device.max_discharge_w

    def status(self) -> dict[str, Any]:
        """The last poll's readings, plus the quantities the modes work from."""
        readings = {
            "battery": self.device.battery_status(),
            "grid": self.device.grid_status(),
            "solar": self.device.solar_status(),
            "control": self.device.control_status(),
        }
        solar = readings["solar"].get("dc_power_w", 0.0)
        total_solar = readings["solar"].get("total_solar_w", solar)
        grid = readings["grid"].get("grid_power_w", 0.0)
        home = self.device.home_load_w() or _estimate_home_load(solar, grid)
        readings["derived"] = {
            "home_load_w": home,
            "excess_solar_w": max(total_solar - home, 0.0),
            "grid_import_w": max(grid, 0.0),
            "grid_export_w": max(-grid, 0.0),
            "total_solar_w": total_solar,
        }
        return readings

    def is_off_grid(self, status: dict[str, Any] | None = None) -> bool:
        """Whether the device has lost the grid."""
        grid = (status or self.status())["grid"]
        return grid.get("connection_state", "Connected") != "Connected"

    async def async_set_mode(self, mode: VirtualMode, **options: Any) -> float:
        """Switch mode and issue the first setpoint.

        Raises ``ValueError`` if a charging mode is asked for at or above its
        target SOC, which would otherwise sit at 0 W looking like a fault.
        """
        self.mode = mode
        for key, value in options.items():
            if not hasattr(self, key):
                raise ValueError(f"unknown mode option {key!r}")
            setattr(self, key, value)
            _LOGGER.info("set %s = %s", key, value)

        await self.device.async_update()
        soc = self.device.battery_status().get("soc", 50)
        self._log_soc_summary(soc)
        charging_modes = (VirtualMode.SELF_CONSUMPTION, VirtualMode.EMERGENCY_BACKUP)
        if mode in charging_modes and soc >= self.target_soc:
            raise ValueError(
                f"target SoC {self.target_soc}% is already reached (now {soc}%)"
            )

        _LOGGER.info("mode changed to %s", self.mode.value)
        return await self.async_execute_once()

    def _log_soc_summary(self, soc: float) -> None:
        """Log where SOC sits between the configured bounds."""
        if soc < self.target_soc:
            # ~1.6 min per percent at full charge rate on a 13.6 kWh pack.
            eta = f"ETA: +{int((self.target_soc - soc) * 1.6)}min"
        else:
            eta = "AT TARGET" if soc == self.target_soc else "ABOVE TARGET"
        _LOGGER.info(
            "SoC: %.1f%% | Target: %.1f%% | Min: %s%% | Max: %s%% | %s",
            soc,
            self.target_soc,
            self.min_discharge_soc,
            self.max_charge_soc,
            eta,
        )

    # -- setpoint calculation --------------------------------------------------

    def calculate_power(self) -> float:
        """The setpoint this mode wants right now, in watts (positive charges)."""
        status = self.status()
        solar = status["solar"].get("dc_power_w", 0.0)
        home = status["derived"]["home_load_w"]
        grid = status["grid"].get("grid_power_w", 0.0)
        soc = status["battery"].get("soc", 50)

        power = self._calculator()(solar, home, grid, soc)
        power = self._apply_soc_limits(power, soc)
        power = self._apply_pcs_limits(power, status)

        # On-grid the aGate protects its own inverter; off-grid it does not.
        if self.is_off_grid(status):
            safe, reason, limited = self._inverter_safety(status, power)
            if not safe:
                if reason != self._last_safety_reason:
                    _LOGGER.error(
                        "off-grid safety: %s — using %.0fW", reason, limited
                    )
                    self._last_safety_reason = reason
                return limited
            self._last_safety_reason = None
        return power

    def _calculator(self) -> Callable[[float, float, float, float], float]:
        """The power function for the active mode."""
        return {
            VirtualMode.SELF_CONSUMPTION: self._calc_self_consumption,
            VirtualMode.EMERGENCY_BACKUP: self._calc_emergency_backup,
            VirtualMode.TIME_OF_USE: self._calc_time_of_use,
            VirtualMode.GRID_ZERO: self._calc_grid_zero,
            VirtualMode.PEAK_SHAVE: self._calc_peak_shave,
            VirtualMode.MANUAL: self._calc_manual,
        }.get(self.mode, self._calc_self_consumption)

    def _calc_self_consumption(
        self, solar: float, home: float, grid: float, soc: float
    ) -> float:
        """Cover the house from solar, then the battery; charge to target."""
        if soc < self.target_soc:
            # Below target the vendor app charges flat out, so match it.
            return -self.max_charge_w
        excess = solar - home
        if excess < 0:
            return max(home - solar, -self.max_discharge_w)
        return min(excess, self.max_charge_w)

    def _calc_emergency_backup(
        self, solar: float, home: float, grid: float, soc: float
    ) -> float:
        """Hold the pack charged for an outage."""
        target = self.target_soc or self.backup_target_soc
        if soc >= target:
            return 0.0
        return min((target - soc) / 100 * 5000 * 10, self.max_charge_w)

    def _calc_grid_zero(
        self, solar: float, home: float, grid: float, soc: float
    ) -> float:
        """Keep the meter at zero in both directions."""
        net_load = home - solar
        if net_load > 0:
            return max(-min(net_load, self.max_discharge_w), -self.max_discharge_w)
        if soc < self.target_soc:
            return min(-net_load, self.max_charge_w)
        return 0.0

    def _calc_peak_shave(
        self, solar: float, home: float, grid: float, soc: float
    ) -> float:
        """Discharge only while the house is over the peak threshold."""
        if home > self.peak_shave_threshold and soc > self.min_discharge_soc + 5:
            return max(min(home - solar, self.max_discharge_w), -self.max_discharge_w)
        return 0.0

    def _calc_time_of_use(
        self, solar: float, home: float, grid: float, soc: float
    ) -> float:
        """Follow the tariff schedule."""
        strategy = self.tou.get_strategy()
        min_soc = self.tou.get_min_soc()
        max_soc = self.tou.get_max_soc()

        match strategy:
            case "charge":
                if soc < min(max_soc, self.target_soc) - 5:
                    if solar > home:
                        return min(
                            solar - home + self.max_charge_w * 0.6, self.max_charge_w
                        )
                    return self.max_charge_w
                return 0.0
            case "discharge":
                if soc > max(min_soc, self.min_discharge_soc) + 5:
                    return max(
                        min(home - solar, self.max_discharge_w), -self.max_discharge_w
                    )
                return 0.0
            case "grid_zero":
                return self._calc_grid_zero(solar, home, grid, soc)
            case "solar_priority" if soc < max_soc - 5 and solar > 0:
                return min(solar, self.max_charge_w)
            case _:
                return self._calc_self_consumption(solar, home, grid, soc)

    def _calc_manual(
        self, solar: float, home: float, grid: float, soc: float
    ) -> float:
        """Whatever the caller asked for."""
        return self.manual_power_w

    # -- limits ----------------------------------------------------------------

    def _apply_soc_limits(self, power: float, soc: float) -> float:
        """Block, or ramp down, a setpoint that would push SOC past its bounds."""
        if soc >= SOC_HARD_MAX and power > 0:
            _LOGGER.warning("SoC %.1f%% at absolute maximum — blocking charge", soc)
            return 0.0
        if soc <= SOC_HARD_MIN and power < 0:
            _LOGGER.warning("SoC %.1f%% at absolute minimum — blocking discharge", soc)
            return 0.0

        window = self.soc_ramp_window
        if power > 0 and soc >= self.max_charge_soc - window:
            if soc < self.max_charge_soc:
                return power * max(1.0 - (soc - self.max_charge_soc + window) / window, 0.05)
            if not self.force_soc_limits:
                _LOGGER.info(
                    "SoC %.1f%% at max limit (%s%%) — blocking charge",
                    soc,
                    self.max_charge_soc,
                )
                return 0.0
            _LOGGER.warning("force override: SoC %.1f%% exceeds max", soc)
        if power < 0 and soc <= self.min_discharge_soc + window:
            if soc > self.min_discharge_soc:
                return power * max(1.0 - (self.min_discharge_soc + window - soc) / window, 0.05)
            if not self.force_soc_limits:
                _LOGGER.info(
                    "SoC %.1f%% at min limit (%s%%) — blocking discharge",
                    soc,
                    self.min_discharge_soc,
                )
                return 0.0
            _LOGGER.warning("force override: SoC %.1f%% below min", soc)
        return power

    def _apply_pcs_limits(self, power: float, status: dict[str, Any]) -> float:
        """Clamp the setpoint to the configured battery and grid flow limits."""
        if power > 0 and self.battery_charge_limit_w is not None:
            power = min(power, self.battery_charge_limit_w)
        if power < 0 and self.battery_discharge_limit_w is not None:
            power = max(power, -self.battery_discharge_limit_w)

        grid = status["grid"].get("grid_power_w", 0.0)
        if (
            self.grid_import_limit_w is not None
            and grid > self.grid_import_limit_w
            and power > 0
        ):
            # Charging is what is drawing the import over the limit; back it off.
            power = max(0.0, power - (grid - self.grid_import_limit_w))
        if (
            self.grid_export_limit_w is not None
            and -grid > self.grid_export_limit_w
            and power < 0
        ):
            power = min(0.0, power + (-grid - self.grid_export_limit_w))
        return power

    def _inverter_safety(
        self, status: dict[str, Any], proposed: float
    ) -> tuple[bool, str, float]:
        """Off-grid check: can the inverter actually deliver this setpoint?"""
        solar = max(status["solar"].get("dc_power_w", 0.0), 0.0)
        home = status["derived"]["home_load_w"]

        if proposed > self.max_charge_w * 1.05:
            return False, "Charge limit exceeded", self.max_charge_w
        if -proposed > self.max_discharge_w * 1.05:
            return False, "Discharge limit exceeded", -self.max_discharge_w

        available = self.max_discharge_w + solar
        if home <= available * 0.8:
            self._warned_high_load = False
            return True, "Safety check passed", proposed

        if not self._warned_high_load:
            _LOGGER.warning(
                "high load: %.0fW at %.0f%% of capacity",
                home,
                home / available * 100,
            )
            self._warned_high_load = True
        if proposed < 0 and home > available * 0.9:
            headroom = max(available - home - 500, 0.0)
            if -proposed > headroom:
                _LOGGER.error("load exceeds capacity — limiting discharge")
                return False, "Load exceeds capacity", -headroom
        return True, "Safety check passed", proposed

    # -- the loop --------------------------------------------------------------

    def verify_command_execution(
        self, tolerance_percent: float = 20.0
    ) -> tuple[bool, float, float, float]:
        """Compare the commanded setpoint against the battery's actual DC power.

        Returns ``(within_tolerance, commanded, actual, difference_percent)``.
        Reports success when nothing is being commanded.
        """
        control = self.device.control_status()
        commanded = control.get("wset_watts", 0.0)
        if control.get("wset_enabled") != 1 or not commanded:
            return True, 0.0, 0.0, 0.0
        actual = self.device.battery_status().get("battery_power_w", 0.0)
        difference = abs((actual - commanded) / commanded) * 100
        return difference <= tolerance_percent, commanded, actual, difference

    async def async_execute_once(self) -> float:
        """Recompute and write the setpoint once; returns the watts sent."""
        await self.device.async_update()
        power = self.calculate_power()
        await self.device.async_send_command(
            BatteryCommand(power_watts=power, mode=ControlMode.LIMIT_ABS)
        )
        if power != self._last_logged_power:
            _LOGGER.info("%s: %.0fW", self.mode.value, power)
            self._last_logged_power = power
        self._last_commanded_power = power
        return power

    async def async_run(
        self,
        *,
        duration_s: float | None = None,
        safety_checks: bool = False,
        stop: asyncio.Event | None = None,
    ) -> None:
        """Hold the setpoint until told to stop, then release control.

        ``safety_checks`` adds periodic alarm and setpoint-vs-actual checks; it
        costs extra reads, so it is off by default and on for unattended runs.
        The loop always releases control on the way out — nothing else will.
        """
        started = time.monotonic()
        last_tick = last_off_grid = last_alarm = last_sanity = 0.0
        failures = alarm_failures = 0
        last_reported_soc: float | None = None

        if self.is_off_grid():
            _LOGGER.warning("system is off-grid — inverter safety limits active")
        _LOGGER.info("running continuous control (safety_checks=%s)", safety_checks)

        try:
            while not (stop is not None and stop.is_set()):
                now = time.monotonic()
                elapsed = now - started
                if duration_s is not None and elapsed >= duration_s:
                    _LOGGER.info("duration expired, stopping")
                    break

                if now - last_off_grid >= OFF_GRID_CHECK_INTERVAL_S:
                    last_off_grid = now
                    self._report_off_grid()

                if now - last_tick >= TICK_INTERVAL_S:
                    last_tick = now
                    if await self._tick():
                        failures = 0
                        last_reported_soc = self._report_progress(
                            last_reported_soc, duration_s, elapsed
                        )
                        if safety_checks and self._soc_target_reached():
                            break
                    else:
                        failures += 1
                        _LOGGER.warning(
                            "tick failed (%d/%d)", failures, MAX_CONSECUTIVE_FAILURES
                        )
                        if failures >= MAX_CONSECUTIVE_FAILURES:
                            _LOGGER.error("too many failures, stopping")
                            break

                if safety_checks and failures == 0:
                    if now - last_alarm >= ALARM_CHECK_INTERVAL_S:
                        last_alarm = now
                        can_operate, blocking = self.device.blocking_alarms()
                        if can_operate:
                            alarm_failures = 0
                        else:
                            _LOGGER.error("blocking alarms: %s", ", ".join(blocking))
                            alarm_failures += 1
                            if alarm_failures >= 2:
                                break
                    if now - last_sanity >= SANITY_CHECK_INTERVAL_S:
                        last_sanity = now
                        ok, commanded, actual, _ = self.verify_command_execution()
                        if not ok:
                            _LOGGER.warning(
                                "commanded %.0fW but measured %.0fW", commanded, actual
                            )

                await asyncio.sleep(0.1)
        finally:
            await self._release_control()

    async def _tick(self) -> bool:
        """One control cycle; ``False`` if it failed for any reason."""
        try:
            await self.async_execute_once()
        except Exception:
            _LOGGER.exception("control tick failed")
            return False
        return True

    def _report_off_grid(self) -> None:
        """Log the grid state, but only when it changes."""
        off_grid = self.is_off_grid()
        if off_grid and not self._off_grid_warned:
            _LOGGER.warning("system is off-grid — inverter safety limits active")
        self._off_grid_warned = off_grid

    def _report_progress(
        self, last_soc: float | None, duration_s: float | None, elapsed: float
    ) -> float:
        """Log SOC progress when it moves; returns the SOC just reported."""
        soc = self.device.battery_status().get("soc", 0)
        if soc == last_soc:
            return soc
        power = self._last_commanded_power
        direction = "up" if power > 0 else "down" if power < 0 else "flat"
        remaining = (
            f" | {int(duration_s - elapsed)}s left" if duration_s is not None else ""
        )
        _LOGGER.info(
            "SoC: %.0f%% %s %.0fW | target: %s%%%s",
            soc,
            direction,
            abs(power),
            self.target_soc,
            remaining,
        )
        return soc

    def _soc_target_reached(self) -> bool:
        """Whether the configured SOC bound for the current direction is hit."""
        soc = self.device.battery_status().get("soc", 0)
        power = self._last_commanded_power
        if power > 0 and soc >= self.max_charge_soc:
            _LOGGER.info("max charge SoC reached: %.1f%%", soc)
            return True
        if power < 0 and soc <= self.min_discharge_soc:
            _LOGGER.info("min discharge SoC reached: %.1f%%", soc)
            return True
        return False

    async def _release_control(self) -> None:
        """Put the device back under its own control, whatever happened."""
        try:
            await self.device.async_reset_control_state()
        except Exception:
            _LOGGER.exception(
                "could not release Modbus control — the device may still be "
                "following the last setpoint; run the CLI's --stop against it"
            )
        else:
            _LOGGER.info("control released (WSetEna=0)")


def _estimate_home_load(solar: float, grid: float) -> float:
    """Estimate house load when the extension register does not answer.

    Deliberately does not use the last commanded battery power: that would
    close a feedback loop between the setpoint and the load it is computed
    from. Bounded to a plausible domestic range.
    """
    if grid > 0:
        estimate = max(solar + grid * 0.5, 300)  # importing
    elif grid < 0:
        estimate = max(solar + grid, 200)  # exporting; grid is negative
    else:
        estimate = max(solar, 300)
    return max(200.0, min(estimate, 15000.0))


async def run_with_signal_handling(
    controller: VirtualModeController,
    *,
    duration_s: float | None = None,
    safety_checks: bool = False,
) -> None:
    """Run the loop until SIGINT/SIGTERM, then shut it down cleanly."""
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    for signal_number in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(signal_number, stop.set)
    try:
        await controller.async_run(
            duration_s=duration_s, safety_checks=safety_checks, stop=stop
        )
    finally:
        for signal_number in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError, ValueError):
                loop.remove_signal_handler(signal_number)

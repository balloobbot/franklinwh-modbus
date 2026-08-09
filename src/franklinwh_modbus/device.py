"""The aGate as one connected device.

Everything the library reads comes from a single pooled poll: the SunSpec
models and the FranklinWH extension block are members of one ``ComponentGroup``,
so ``async_update()`` is a handful of block reads and every view below is
computed from what that poll left behind rather than going back to the wire.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from modbus_connection import ModbusTcpParams
from modbus_connection.model import ComponentGroup
from modbus_connection.model.sunspec import SunSpecMapShiftError, scan
from modbus_connection.tmodbus import ModbusConnection

from .models import MODELS
from .models.extensions import Extensions, OnGridMode
from .types import ALARM_BITS, BatteryCommand, HealthStatus
from .writing import WriteRejected, write_many, write_verified

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit
    from modbus_connection.model import Component
    from modbus_connection.model.sunspec import SunSpecComponent

_LOGGER = logging.getLogger(__name__)

#: Without these the library cannot do its job: telemetry, battery and control.
REQUIRED_MODELS = (701, 704, 713)

#: The aGate answers its whole map from address 0 and returns
#: ILLEGAL_DATA_ADDRESS at 40000, so 0 is the base rather than a legacy quirk.
DEFAULT_BASE_ADDRESS = 0

#: The unit ID FranklinWH ships.
DEFAULT_UNIT_ID = 2

#: The device wants a beat between control phases; writing the enable register
#: immediately after the setpoint has been seen to leave the setpoint behind.
CONTROL_SETTLE_S = 0.3
ENABLE_SETTLE_S = 0.5

#: Below this the battery is neither charging nor discharging in any useful
#: sense — M713.Sta reads 0 on this firmware, so power direction is the only
#: signal for battery state.
IDLE_DEADBAND_W = 50.0

_CONNECTION_STATES = {0: "Disconnected", 1: "Connected", 2: "Fault"}
_INVERTER_STATES = {
    0: "Off",
    1: "Sleeping",
    2: "Starting",
    3: "Running",
    4: "Throttled",
    5: "Shutting Down",
    6: "Fault",
    7: "Standby",
    8: "Test",
    9: "Manufacturing",
}
_LOC_REM_LABELS = {0: "Remote", 1: "Local"}

#: System alarm bits that stop the device doing anything useful.
_BLOCKING_ALARM_BITS = (1 << 0) | (1 << 6) | (1 << 7) | (1 << 13) | (1 << 14)
#: DC port electrical faults.
_BLOCKING_DC_PORT_BITS = 0x3F


class AGateError(Exception):
    """The device is not usable for what was asked of it."""


def _value(raw: Any) -> Any:
    """Unwrap an ``IntEnum``/``IntFlag`` decode back to a plain number."""
    return int(raw) if isinstance(raw, int) else raw


def _scaled(raw: Any, digits: int | None = None) -> float:
    """A decoded point as a number, with an unimplemented point reading 0."""
    if raw is None:
        return 0.0
    return round(float(raw), digits) if digits is not None else float(raw)


class AGate:
    """A connected FranklinWH aGate."""

    def __init__(
        self,
        host: str,
        *,
        port: int = 502,
        unit_id: int = DEFAULT_UNIT_ID,
        timeout: float = 10.0,
        base_address: int = DEFAULT_BASE_ADDRESS,
        message_spacing: float = 0.05,
        max_charge_w: float | None = None,
        max_discharge_w: float | None = None,
    ) -> None:
        self._connection = ModbusConnection(
            ModbusTcpParams(host=host, port=port),
            timeout=timeout,
            message_spacing=message_spacing,
        )
        self._unit_id = unit_id
        self._base_address = base_address
        self._override_max_charge_w = max_charge_w
        self._override_max_discharge_w = max_discharge_w
        self._unit: ModbusUnit | None = None
        self._models: dict[int, SunSpecComponent] = {}
        self._extensions: Extensions | None = None
        self._group: ComponentGroup | None = None
        self._command_timer: asyncio.Task[None] | None = None
        self._extensions_writable: bool | None = None

    # -- lifecycle ------------------------------------------------------------

    @property
    def connected(self) -> bool:
        """Whether the link is up."""
        return self._connection.connected

    @property
    def models(self) -> dict[int, SunSpecComponent]:
        """The discovered models, by SunSpec model ID."""
        return self._models

    @property
    def extensions(self) -> Extensions:
        """The FranklinWH manufacturer register block."""
        if self._extensions is None:
            raise AGateError("not connected")
        return self._extensions

    def model(self, model_id: int) -> SunSpecComponent | None:
        """One discovered model, or ``None`` if this device does not carry it."""
        return self._models.get(model_id)

    def _require(self, model_id: int) -> Any:
        """One discovered model, or raise naming what is missing."""
        component = self._models.get(model_id)
        if component is None:
            raise AGateError(f"model {model_id} is not present on this device")
        return component

    async def async_connect(self) -> None:
        """Connect, walk the model chain, and take the first reading.

        Raises ``AGateError`` if the device is missing a model the library
        needs, and ``ModbusConnectionError`` if the link cannot be made.
        """
        await self._connection.connect()
        self._unit = self._connection.for_unit(self._unit_id)
        discovered = await scan(self._unit, self._base_address)
        _LOGGER.debug("discovered SunSpec models: %s", sorted(discovered))

        self._models = {}
        for model_id, component_class in MODELS.items():
            located = discovered.first(model_id)
            if located is not None:
                self._models[model_id] = component_class(self._unit, located)
        missing = [m for m in REQUIRED_MODELS if m not in self._models]
        if missing:
            raise AGateError(f"device is missing required model(s): {missing}")

        self._extensions = Extensions(self._unit)
        self._group = ComponentGroup(
            self._unit, [*self._models.values(), self._extensions]
        )
        await self.async_update()

    async def async_disconnect(self) -> None:
        """Drop the link, cancelling any pending command timeout."""
        self.cancel_command_timer()
        await self._connection.disconnect()

    async def async_close(self) -> None:
        """Close the connection permanently."""
        self.cancel_command_timer()
        await self._connection.close()

    async def async_update(self) -> None:
        """Refresh every component in one pooled read.

        Raises ``AGateError`` if the model chain has moved under us — which on
        this device also means the curve models' counts have changed, since the
        components were generated against a specific set of them.
        """
        if self._group is None:
            raise AGateError("not connected")
        try:
            await self._group.async_update()
        except SunSpecMapShiftError as err:
            raise AGateError(
                f"{err}. The components are generated for a specific firmware's"
                " layout; a model whose length no longer matches usually means"
                " the device reports different curve counts (NPt / NCrv /"
                " NCrvSet) than the ones this build was generated for"
            ) from err

    # -- telemetry ------------------------------------------------------------

    def nameplate(self) -> dict[str, str]:
        """Manufacturer, model, serial and firmware version, from model 1."""
        common = self._models.get(1)
        if common is None:
            return {}
        return {
            "manufacturer": (common.mn or "").strip(),
            "model": (common.md or "").strip(),
            "serial": (common.sn or "").strip(),
            "version": (common.vr or "").strip(),
            "options": (common.opt or "").strip(),
        }

    def battery_status(self) -> dict[str, Any]:
        """State of charge and DC-side battery telemetry (models 713 and 714).

        ``battery_power_w`` follows the device's own sign convention: positive
        is power leaving the battery.
        """
        storage = self._require(713)
        status: dict[str, Any] = {
            "soc": _scaled(storage.so_c, 1),
            "soh": _scaled(storage.so_h, 1),
            "wh_rating": _scaled(storage.wh_rtg),
            "wh_available": _scaled(storage.wh_avail),
            # Always 0 on this firmware; kept because callers report it.
            "status_raw": _value(storage.sta),
        }
        ports = self._dc_ports()
        if not ports:
            return status

        total_power = sum(_scaled(port.dcw) for port in ports)
        status["battery_power_w"] = total_power
        if total_power < -IDLE_DEADBAND_W:
            status["battery_state"] = "Charging"
        elif total_power > IDLE_DEADBAND_W:
            status["battery_state"] = "Discharging"
        else:
            status["battery_state"] = "Idle"

        status["battery_current_a"] = self._dc_current(ports, total_power)
        temperatures = [_scaled(port.tmp, 1) for port in ports if port.tmp is not None]
        status["battery_temp_c"] = round(max(temperatures), 1) if temperatures else 0
        status["individual_batteries"] = [
            {
                "port": index + 1,
                "power_w": _scaled(port.dcw),
                "voltage_v": _scaled(port.dcv),
                "current_a": _scaled(port.dca),
                "temp_c": _scaled(port.tmp, 1),
            }
            for index, port in enumerate(ports)
        ]
        return status

    def _dc_ports(self) -> list[Component]:
        """The model 714 port blocks, one per parallel battery stack."""
        measure_dc = self._models.get(714)
        return list(measure_dc.prt) if measure_dc is not None else []

    @staticmethod
    def _dc_current(ports: list[Component], total_power: float) -> float:
        """Total DC current, derived from power when the device omits DCA.

        This firmware leaves DCA unimplemented (it reads 0), so the current has
        to come from the power and the mean of the voltages that are live.
        """
        measured = [_scaled(port.dca) for port in ports if port.dca]
        if measured:
            return round(sum(measured), 2)
        voltages = [_scaled(port.dcv) for port in ports if _scaled(port.dcv) > 0]
        if not voltages:
            return 0.0
        return round(total_power / (sum(voltages) / len(voltages)), 2)

    def grid_status(self) -> dict[str, Any]:
        """AC-side measurements from model 701."""
        ac = self._require(701)
        voltage = _scaled(ac.lnv, 1)
        current = _scaled(ac.a, 1)
        return {
            "grid_power_w": _scaled(ac.w),
            "grid_va": _scaled(ac.va),
            "grid_var": _scaled(ac.var),
            "voltage_v": voltage,
            "frequency_hz": _scaled(ac.hz, 2),
            "current_a": current,
            "power_factor": _scaled(ac.pf, 3),
            "ambient_temp_c": _scaled(ac.tmp_amb, 1),
            "cabinet_temp_c": _scaled(ac.tmp_cab, 1),
            "connection_state": _CONNECTION_STATES.get(
                _value(ac.conn_st), f"Unknown({ac.conn_st})"
            ),
            "inverter_state": _INVERTER_STATES.get(
                _value(ac.inv_st), f"Unknown({ac.inv_st})"
            ),
            "grid_mode": _grid_mode(_value(ac.der_mode) or 0),
            "ac_type": _ac_type(voltage),
            "grid_export_wh": round(_scaled(ac.tot_wh_inj)),
            "grid_import_wh": round(_scaled(ac.tot_wh_abs)),
        }

    def solar_status(self) -> dict[str, Any]:
        """PV production, from model 502 where present and the extensions."""
        module = self._models.get(502)
        ac_power = _scaled(module.out_pw) if module is not None else 0.0
        battery_dc = sum(_scaled(port.dcw) for port in self._dc_ports())
        extensions = self.extensions
        total = _scaled(extensions.pv_output_p)
        status: dict[str, Any] = {
            "ac_power_w": ac_power or total,
            # Historically named for solar; it is the battery's DC side.
            "dc_power_w": battery_dc,
            "battery_dc_power_w": battery_dc,
            "extension": {
                "pv_installed": bool(extensions.pv_use),
                "remote_pv_installed": bool(extensions.ap_box_pv_use),
                "total_solar": total,
                "proximal_solar": _scaled(extensions.proximal_pv_output_p),
                "remote1_solar": _scaled(extensions.remote1_pv),
                "remote2_solar": _scaled(extensions.remote2_pv),
                "total_generation_wh": _scaled(extensions.pv_output_wh),
                "proximal_generation_wh": _scaled(extensions.proximal_output_wh),
            },
        }
        if total > 0:
            status["total_solar_w"] = total
        return status

    def home_load_w(self) -> float:
        """Home load, from the high-resolution mirror when it answers."""
        return _scaled(self.extensions.home_load_w)

    def control_status(self) -> dict[str, Any]:
        """The active power setpoint and its reversion state (models 704, 715)."""
        control = self._require(704)
        lifecycle = self._models.get(715)
        loc_rem = _value(lifecycle.loc_rem_ctl) if lifecycle is not None else None
        return {
            "wset_enabled": _value(control.w_set_ena),
            "wset_mode": _value(control.w_set_mod),
            "wset_watts": _scaled(control.w_set),
            "wset_pct": _scaled(control.w_set_pct),
            "wset_revert_watts": control.w_set_rvrt,
            "wset_revert_time_s": control.w_set_rvrt_tms,
            "wset_revert_remain_s": control.w_set_rvrt_rem,
            "loc_rem_ctl": loc_rem,
            "loc_rem_ctl_name": (
                _LOC_REM_LABELS.get(loc_rem, f"Unknown({loc_rem})")
                if loc_rem is not None
                else "N/A"
            ),
        }

    def native_mode(self) -> dict[str, Any]:
        """The FranklinWH operating mode and both SOC reserves."""
        extensions = self.extensions
        mode = extensions.mode
        raw = extensions.on_grid_mode
        return {
            "mode_raw": _value(raw),
            "mode": mode,
            "mode_name": mode.name.replace("_", " ").title() if mode else f"Unknown({raw})",
            "self_reserve_pct": _value(extensions.self_reserve),
            "tou_reserve_pct": _value(extensions.tou_reserve),
        }

    def effective_reserve_level(self) -> tuple[int | None, str]:
        """The SOC reserve the active mode actually honours."""
        status = self.native_mode()
        match status["mode"]:
            case OnGridMode.SELF_CONSUMPTION:
                return status["self_reserve_pct"], "Self-Consumption reserve"
            case OnGridMode.TIME_OF_USE:
                return status["tou_reserve_pct"], "Time-of-Use reserve"
            case OnGridMode.EMERGENCY_BACKUP:
                return 100, "Emergency Backup holds full charge"
            case _:
                return None, "no reserve applies in this mode"

    # -- alarms ---------------------------------------------------------------

    def alarms(self) -> dict[str, Any]:
        """The alarm bitfields, with the system alarm decoded to bit names."""
        ac = self._models.get(701)
        measure_dc = self._models.get(714)
        storage = self._models.get(713)
        system = _value(ac.alrm) if ac is not None and ac.alrm else 0
        return {
            "system_alrm": system,
            "dc_port_alrm": (
                _value(measure_dc.prt_alrms)
                if measure_dc is not None and measure_dc.prt_alrms
                else 0
            ),
            "battery_sta": (
                _value(storage.sta) if storage is not None and storage.sta else 0
            ),
            "decoded": {
                name: bool(system & (1 << bit)) for bit, name in ALARM_BITS.items()
            },
        }

    def blocking_alarms(self) -> tuple[bool, list[str]]:
        """Whether control is safe right now, and why not if it is not."""
        current = self.alarms()
        blocking = []
        if current["system_alrm"] & _BLOCKING_ALARM_BITS:
            blocking.append(f"System alarm: 0x{current['system_alrm']:08X}")
        if current["dc_port_alrm"] & _BLOCKING_DC_PORT_BITS:
            blocking.append(f"DC port alarm: 0x{current['dc_port_alrm']:08X}")
        if current["battery_sta"] == 6:
            blocking.append("BATTERY_FAULT")
        return not blocking, blocking

    # -- ratings --------------------------------------------------------------

    @property
    def max_charge_w(self) -> float:
        """The battery's charge rate ceiling, from model 702 unless overridden."""
        if self._override_max_charge_w is not None:
            return self._override_max_charge_w
        capacity = self._models.get(702)
        rating = _scaled(capacity.w_cha_rte_max_rtg) if capacity else 0.0
        return rating or _scaled(capacity.w_max_rtg) if capacity else 0.0

    @property
    def max_discharge_w(self) -> float:
        """The battery's discharge rate ceiling, from model 702."""
        if self._override_max_discharge_w is not None:
            return self._override_max_discharge_w
        capacity = self._models.get(702)
        rating = _scaled(capacity.w_dis_cha_rte_max_rtg) if capacity else 0.0
        return rating or _scaled(capacity.w_max_rtg) if capacity else 0.0

    # -- control --------------------------------------------------------------

    async def async_set_native_mode(self, mode: OnGridMode | int) -> None:
        """Set the operating mode, preserving both reserves.

        Writing 15507 on its own resets the two reserve registers that follow
        it, so all three go out in one FC16 with the reserves rewritten to what
        they already hold.

        Raises ``WriteRejected`` if the device keeps the old mode, which is
        what happens when the installer has not enabled "SPAN Modbus".
        """
        mode = OnGridMode(int(mode))
        extensions = self.extensions
        await write_many(
            extensions,
            {
                "on_grid_mode": int(mode),
                "self_reserve": _value(extensions.self_reserve),
                "tou_reserve": _value(extensions.tou_reserve),
            },
            settle=CONTROL_SETTLE_S,
        )
        await extensions.async_update()

    async def async_set_self_consumption_reserve(self, percent: int) -> None:
        """Set the SOC floor held in Self-Consumption mode."""
        await write_verified(
            self.extensions, "self_reserve", percent, settle=CONTROL_SETTLE_S
        )
        await self.extensions.async_update()

    async def async_set_tou_reserve(self, percent: int) -> None:
        """Set the SOC floor held in Time-of-Use mode."""
        await write_verified(
            self.extensions, "tou_reserve", percent, settle=CONTROL_SETTLE_S
        )
        await self.extensions.async_update()

    async def async_send_command(
        self,
        command: BatteryCommand,
        *,
        duration_s: float | None = None,
    ) -> float:
        """Drive the battery to a power setpoint through model 704.

        Returns the percentage actually written. ``power_watts`` is positive to
        charge; the device's own WSetPct convention is the opposite sign, and
        the inversion happens here.

        ``duration_s`` arms a software timeout that resets control when it
        expires. It is not optional for unattended use: the hardware's own
        WSetRvrtTms counts down but never reverts anything, so nothing else
        will put the device back.

        Raises ``AGateError`` if an alarm blocks control and ``WriteRejected``
        if the device does not take the setpoint.
        """
        safe, reasons = self.blocking_alarms()
        if not safe:
            raise AGateError(f"cannot control while alarms are active: {reasons}")

        control = self._require(704)
        watts = command.power_watts
        rated = self.max_charge_w if watts > 0 else self.max_discharge_w
        if not rated:
            raise AGateError("device reports no charge/discharge rating to scale by")
        percent = min(100.0, abs(watts) / rated * 100.0)
        # Positive means discharge to the device, the opposite of our convention.
        target = -percent if watts > 0 else percent

        self.cancel_command_timer()
        # Phase 1: stop, so the new setpoint is never briefly applied at the old
        # enable state. Phase 2: set it. Phase 3: enable. The device needs a
        # beat between each, and each is read back before moving on.
        await write_verified(control, "w_set_ena", 0, settle=CONTROL_SETTLE_S)
        await write_many(
            control,
            {"w_set_mod": 0, "w_set_pct": target},
            settle=CONTROL_SETTLE_S,
        )
        await write_verified(control, "w_set_ena", 1, settle=ENABLE_SETTLE_S)
        await control.async_update()

        if duration_s:
            self._arm_command_timer(duration_s)
        return percent

    async def async_reset_control_state(self) -> None:
        """Hand control back to the device: disable the setpoint and zero it."""
        control = self._require(704)
        await write_verified(control, "w_set_ena", 0, settle=CONTROL_SETTLE_S)
        await write_many(control, {"w_set_pct": 0.0}, settle=CONTROL_SETTLE_S)
        await control.async_update()

    def _arm_command_timer(self, duration_s: float) -> None:
        """Schedule a control reset once ``duration_s`` has passed."""

        async def _expire() -> None:
            await asyncio.sleep(duration_s)
            _LOGGER.warning(
                "command timeout (%.0fs) expired — resetting control", duration_s
            )
            try:
                await self.async_reset_control_state()
            except (AGateError, WriteRejected, OSError):
                _LOGGER.exception("failed to reset control after timeout")

        self._command_timer = asyncio.create_task(_expire())

    def cancel_command_timer(self) -> None:
        """Cancel a pending command timeout, if one is armed."""
        if self._command_timer is not None:
            self._command_timer.cancel()
            self._command_timer = None

    @property
    def command_timer_active(self) -> bool:
        """Whether a command timeout is currently armed."""
        return self._command_timer is not None and not self._command_timer.done()

    # -- health ---------------------------------------------------------------

    def healthcheck(self) -> HealthStatus:
        """Summarise whether the device is in a state worth driving."""
        safe, reasons = self.blocking_alarms()
        control = self.control_status()
        battery = self.battery_status()
        details = {
            "alarms": self.alarms(),
            "control": control,
            "battery": battery,
            "native_mode": self.native_mode(),
        }
        if not safe:
            return HealthStatus(
                healthy=False,
                message="alarms are blocking operation",
                recommendations=["clear the alarms before issuing control"],
                details=details,
            )
        if control["loc_rem_ctl"] == 1 and control["wset_enabled"]:
            return HealthStatus(
                healthy=False,
                message="remote setpoint is enabled while the device reports Local",
                recommendations=["call async_reset_control_state()"],
                details=details,
            )
        return HealthStatus(
            healthy=True,
            message=f"{battery.get('battery_state', 'Unknown')} at "
            f"{battery.get('soc', 0)}% SOC",
            recommendations=[],
            details=details,
        )


def _grid_mode(der_mode: int) -> str:
    """Name the operating mode carried in model 701's DERMode bitfield."""
    if der_mode & (1 << 2):
        return "PV Clipped"
    if der_mode & (1 << 1):
        return "Grid Forming"
    if der_mode & (1 << 0):
        return "Grid Following"
    return "Grid Following (default)"


def _ac_type(voltage: float) -> str:
    """Infer the AC service from the measured line-neutral voltage."""
    if 200 <= voltage <= 260:
        return "Single-Phase (230V Nominal)"
    if 100 <= voltage < 200:
        return "Single-Phase (120V Nominal)"
    if 380 <= voltage <= 420:
        return "Three-Phase (400V Line-Line)"
    return "Unknown"

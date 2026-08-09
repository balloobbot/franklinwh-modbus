"""State inspection and SOC safety checks, decided from the last poll.

Two jobs. :func:`check_state` works out whether something *other than us* is
driving the battery — the vendor's cloud API and the aGate's own modes both
move the pack without ever setting WSetEna, so the only evidence is the DC
power moving while remote control is off, read against solar, load and grid.
:func:`validate_soc_safety` refuses a target that would fight the SOC reserve
the active mode honours, since the device performs no validation of its own.

Both are pure functions of a device's current readings; neither touches the
bus. The error codes (E001-E006, W001-W002) are the ones the CLI prints and
are unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from .device import AGate

Operation = Literal["charge", "discharge"]

#: Headroom kept above the configured reserve, so a discharge stops before the
#: device's own floor rather than at it.
SAFETY_MARGIN_PCT = 5
ABSOLUTE_MIN_SOC = 5
ABSOLUTE_MAX_SOC = 100

#: Grid voltage outside this band means the connection is not usable even if
#: the device still reports ConnSt as connected.
_GRID_VOLTAGE_RANGE = (180, 270)
#: Battery power above this is somebody actively driving the pack, not drift.
_ACTIVE_POWER_W = 500
#: The same, for a setpoint we issued ourselves.
_ACTIVE_SETPOINT_W = 100
#: Grid import above this is a real import rather than measurement noise.
_MEANINGFUL_GRID_W = 500
#: Below this much PV it is night, so charging cannot be coming from solar.
_NIGHT_SOLAR_W = 100


def check_state(device: AGate) -> dict[str, Any]:
    """Summarise what the device is doing, and who is making it do that."""
    battery = device.battery_status()
    grid = device.grid_status()
    control = device.control_status()
    native = device.native_mode()
    can_operate, blocking = device.blocking_alarms()

    voltage = grid.get("voltage_v", 0)
    enabled = control.get("wset_enabled") == 1
    percent = control.get("wset_pct", 0) or 0
    # WSetPct is signed the device's way: positive discharges.
    rated = device.max_discharge_w if percent > 0 else device.max_charge_w
    commanded = percent / 100.0 * rated if enabled else 0.0
    measured = battery.get("battery_power_w", 0) or 0

    state: dict[str, Any] = {
        "soc": battery.get("soc", 0),
        "grid_power": grid.get("grid_power_w", 0),
        "grid_voltage": voltage,
        "connection_state": grid.get("connection_state", "Unknown"),
        "grid_connected": (
            grid.get("connection_state") == "Connected"
            and _GRID_VOLTAGE_RANGE[0] < voltage < _GRID_VOLTAGE_RANGE[1]
        ),
        "wset_ena": control.get("wset_enabled", 0),
        "actual_power": commanded,
        "battery_activity": _describe_activity(enabled, commanded, measured),
        "ongrid_mode": native.get("mode_name", "Unknown"),
        "ongrid_mode_raw": native.get("mode_raw", -1),
        "self_reserve_pct": native.get("self_reserve_pct", 20),
        "tou_reserve_pct": native.get("tou_reserve_pct", 20),
        "alarms": {
            "can_operate": can_operate,
            "blocking": blocking,
            "system_alrm": device.alarms()["system_alrm"],
        },
        "energy_context": {
            "solar_w": device.solar_status().get("total_solar_w", 0),
            "home_load_w": device.home_load_w(),
            "battery_dc_w": measured,
            "grid_w": grid.get("grid_power_w", 0),
        },
    }

    reserve, source = device.effective_reserve_level()
    if reserve is not None:
        state["effective_reserve"] = {
            "level": reserve,
            "source": source,
            "min_operational": reserve + SAFETY_MARGIN_PCT,
        }
    state["conflicts"] = _conflicts(state, enabled, commanded, measured)
    return state


def _describe_activity(enabled: bool, commanded: float, measured: float) -> str:
    """Name what the battery is doing, and whether we asked for it."""
    if enabled:
        if commanded < -50:
            return f"Charging ({abs(commanded):.0f}W)"
        if commanded > 50:
            return f"Discharging ({commanded:.0f}W)"
        return "Idle"
    if measured < -50:
        return f"Charging ({abs(measured):.0f}W, aGate native)"
    if measured > 50:
        return f"Discharging ({measured:.0f}W, aGate native)"
    return "Idle (no Modbus control)"


def _conflicts(
    state: dict[str, Any], enabled: bool, commanded: float, measured: float
) -> list[str]:
    """Report anything else moving the battery, in context.

    Context matters because most battery movement is correct: charging from
    excess solar in Self-Consumption is the mode working, not a conflict. Only
    movement that contradicts the energy flow is worth flagging, so entries
    that are merely informational are prefixed ``INFO:``.
    """
    context = state["energy_context"]
    solar, load, grid = context["solar_w"], context["home_load_w"], context["grid_w"]
    power = measured or commanded
    charging = measured < -_ACTIVE_POWER_W or commanded < -_ACTIVE_SETPOINT_W
    discharging = measured > _ACTIVE_POWER_W or commanded > _ACTIVE_SETPOINT_W

    if enabled:
        if charging or discharging:
            verb = "charging" if charging else "discharging"
            return [
                f"INFO: Modbus control active ({verb} {abs(power):.0f}W, "
                f"SoC {state['soc']:.1f}%) - a new command will override it"
            ]
        return []
    if not (charging or discharging):
        return []

    mode = state["ongrid_mode"]
    if mode == "Self Consumption":
        if charging:
            return [_self_consumption_charging(state, power, solar, load, grid)]
        if solar > load + _MEANINGFUL_GRID_W:
            return [
                f"aGate discharging {power:.0f}W despite excess solar "
                f"(solar {solar:.0f}W > load {load:.0f}W)"
            ]
        if load > solar + _MEANINGFUL_GRID_W:
            return [
                f"INFO: aGate discharging {power:.0f}W to serve home load "
                f"(load {load:.0f}W > solar {solar:.0f}W) - normal for this mode"
            ]
        return [
            f"aGate Self-Consumption discharging {power:.0f}W "
            f"(solar {solar:.0f}W, load {load:.0f}W)"
        ]
    if mode == "Emergency Backup" and charging:
        return [f"aGate Emergency Backup actively charging at {abs(power):.0f}W"]
    if mode == "Time Of Use":
        return [f"aGate TOU mode active and the battery is moving ({power:.0f}W)"]
    return []


def _self_consumption_charging(
    state: dict[str, Any], power: float, solar: float, load: float, grid: float
) -> str:
    """Classify a charge nobody asked for while in Self-Consumption."""
    importing = grid > _MEANINGFUL_GRID_W
    if importing and solar < _NIGHT_SOLAR_W:
        return (
            f"aGate importing {grid:.0f}W from the grid to charge the battery at "
            f"night ({abs(power):.0f}W charge, SoC {state['soc']:.1f}%)"
        )
    if importing:
        return (
            f"aGate importing {grid:.0f}W to charge the battery "
            f"({abs(power):.0f}W charge, solar {solar:.0f}W, load {load:.0f}W)"
        )
    return (
        f"INFO: aGate charging {abs(power):.0f}W from excess solar "
        f"(solar {solar:.0f}W > load {load:.0f}W) - normal for this mode"
    )


def validate_target_soc(
    device: AGate, target_soc: float, operation: Operation
) -> tuple[bool, str, dict[str, Any]]:
    """Check a target SOC against the absolute bounds and the active reserve."""
    details: dict[str, Any] = {
        "target_soc": target_soc,
        "operation": operation,
        "effective_reserve": None,
        "reserve_source": "unknown",
        "min_allowed": ABSOLUTE_MIN_SOC,
        "max_allowed": ABSOLUTE_MAX_SOC,
        "safety_margin": SAFETY_MARGIN_PCT,
    }
    if not ABSOLUTE_MIN_SOC <= target_soc <= ABSOLUTE_MAX_SOC:
        return (
            False,
            f"E001: target SoC {target_soc:.1f}% is outside the absolute safe "
            f"range ({ABSOLUTE_MIN_SOC}-{ABSOLUTE_MAX_SOC}%)",
            details,
        )

    reserve, source = device.effective_reserve_level()
    details["effective_reserve"] = reserve
    details["reserve_source"] = source
    if reserve is None:
        return True, "target SoC validated", details

    floor = reserve + SAFETY_MARGIN_PCT
    details["min_allowed"] = max(floor, ABSOLUTE_MIN_SOC)
    if operation == "discharge" and target_soc < floor:
        return (
            False,
            f"E002: target SoC {target_soc:.1f}% conflicts with the reserve "
            f"({reserve}% from {source}) plus a {SAFETY_MARGIN_PCT}% safety "
            f"margin; the minimum allowed is {floor:.1f}%",
            details,
        )
    if operation == "charge" and target_soc < reserve:
        details["warning"] = (
            f"W001: target SoC {target_soc:.1f}% is below the configured reserve "
            f"({reserve}% from {source}); the battery may not charge as expected"
        )
    return True, "target SoC validated", details


def validate_soc_safety(
    device: AGate, target_soc: float, current_soc: float, operation: Operation
) -> tuple[bool, str, dict[str, Any]]:
    """Check a target against both the reserve and where the pack is now."""
    valid, message, details = validate_target_soc(device, target_soc, operation)
    if not valid:
        return valid, message, details
    details["current_soc"] = current_soc

    if operation == "discharge" and target_soc >= current_soc:
        return (
            False,
            f"E003: a discharge target ({target_soc:.1f}%) must be below the "
            f"current SoC ({current_soc:.1f}%)",
            details,
        )
    if operation == "charge" and target_soc <= current_soc:
        return (
            False,
            f"E005: a charge target ({target_soc:.1f}%) must be above the "
            f"current SoC ({current_soc:.1f}%)",
            details,
        )

    reserve, source = device.effective_reserve_level()
    if reserve is not None and operation == "discharge":
        distance = current_soc - reserve
        if distance <= SAFETY_MARGIN_PCT + 2:
            details["proximity_warning"] = (
                f"W002: the current SoC ({current_soc:.1f}%) is only "
                f"{distance:.1f}% above the reserve ({reserve}% from {source}); "
                f"the discharge will stop with minimal margin"
            )
    return True, "SoC safety validation passed", details

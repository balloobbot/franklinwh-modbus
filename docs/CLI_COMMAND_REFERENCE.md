# CLI Command Reference

The `franklinwh_cli.py` tool is the primary interface for controlling and monitoring FranklinWH aGate systems via Modbus TCP. It supports both native hardware modes and advanced virtual software orchestration.

## 1. Connection & Global Options

| Option | Alias | Default | Description |
|:-------|:------|:--------|:------------|
| `-i` | `--ip` | **Required** | Target aGate IP address. |
| `-p` | `--port` | `502` | Modbus TCP port. |
| `-u` | `--unit` | `2` | Modbus Unit ID (aGate default is 2). |
| `-b` | `--base-address` | `40000` | Start address for SunSpec discovery. |
| `-t` | `--timeout` | `10.0` | Connection timeout in seconds. |

## 2. Operating Modes

### Native Hardware Mode (`--mode`)
Switches the aGate's native firmware operating mode via Register 15507.
- **Values**: `backup`, `self-consumption` (or `self`, `sc`), `tou`.
- **Note**: Requires "SPAN Modbus" unlock. The CLI performs a read-back verification to ensure the hardware accepted the change.

### Virtual Software Mode (`--vmode`)
Runs a software-orchestrated control loop using standard SunSpec Model 704 commands.
- **Values**: `self_consumption`, `emergency_backup`, `time_of_use`, `peak_shave`, `manual`.
- **Note**: Does not require SPAN unlock. Operates by overriding aGate logic with direct charge/discharge commands.

## 3. Direct Battery Control

| Option | Argument | Description |
|:-------|:---------|:------------|
| `--charge` | `WATTS` | Force charge from grid at specific wattage. |
| `--discharge` | `WATTS` | Force discharge to home/grid at specific wattage. |
| `--max-charge` | - | Charge at the device's maximum rated nameplate power. |
| `--max-discharge` | - | Discharge at the device's maximum rated nameplate power. |
| `--standby` | - | Set battery to 0W idle (grid powers home). |
| `--power` | `WATTS` | Legacy alias: Positive=Charge, Negative=Discharge. |

## 4. Control Parameters & Safety

| Option | Default | Description |
|:-------|:--------|:------------|
| `--target-soc` | `100` | Target SoC for charge/discharge operations. |
| `--reserve` | `20` | SoC reserve level for Self-Consumption/TOU modes. |
| `--threshold` | `2000` | Power threshold (W) for Peak Shave mode. |
| `--duration` | - | Run the command for N seconds and then exit. |
| `--revert` | - | **Safety**: Auto-release control after N seconds (Software watchdog). |
| `--target-soc-auto` | - | Auto-stop once specific SoC % is reached. |
| `--loop` | - | Maintain control loop until target is reached. |
| `--force` | - | Override safety SoC limits (use with caution). |

## 5. Monitoring & Diagnostics

| Option | Description |
|:-------|:------------|
| `--status` | Show system summary (SoC, Power Flow, Control State). |
| `--detail` | Add granular register data and lifetime energy metrics to `--status`. |
| `--monitor` | Launch the interactive Terminal UI (TUI) dashboard. |
| `--healthcheck` | Run comprehensive system diagnostics and zombie detection. |
| `--check-alarms` | Display detailed bitfield status for all system and DC alarms. |
| `--stop` | Release Modbus control and return the aGate to native firmware mode. |

## 6. Utilities & Scheduling

| Option | Description |
|:-------|:------------|
| `--schedule-file` | Load a JSON TOU schedule for virtual mode orchestration. |
| `--show-schedule` | Visualize the contents of a schedule file. |
| `--validate-schedule`| Perform schema validation on a schedule JSON. |
| `--clear-alarms` | Attempt to reset active alarms via the `AlarmReset` register. |
| `--test-extension-write` | Check if 15507-15509 extension registers are writable (PICS check). |
| `--check-span` | Scan local network for SPAN panels to determine feature availability. |

## 7. Sequencing

| Option | Description |
|:-------|:------------|
| `--sequence` | Execute a JSON string sequence (e.g., `'[{"charge": 1000}, {"wait": 10}]'`). |
| `--sequence-file` | Execute a multi-step sequence from a JSON file. |
| `--brief` | Minimal output for automated sequencing scripts. |

## 8. Global UI

| Option | Description |
|:-------|:------------|
| `-v`, `--verbose` | Enable debug logging of SunSpec discovery and Modbus traffic. |
| `-q`, `--quiet` | Suppress all non-error output. |
| `--theme` | Set TUI theme: `dark` (default), `green`, `amber`, `white`, `paper`. |
| `--dry-run` | Simulate command execution without writing to registers. |

---

## Example Scenarios

### 1. Simple Status Check
```bash
python3 tools/franklinwh_cli.py -i 192.168.0.110 --status
```

### 2. Force Charge for 1 Hour with Safety Timeout
```bash
# Charges at 3000W, reverts to cloud control automatically after 3600s
python3 tools/franklinwh_cli.py -i 192.168.0.110 --charge 3000 --revert 3600 --loop
```

### 3. Switch Native Mode (Requires SPAN)
```bash
python3 tools/franklinwh_cli.py -i 192.168.0.110 --mode backup
```

### 4. Run Virtual Peak Shaving
```bash
python3 tools/franklinwh_cli.py -i 192.168.0.110 --vmode peak_shave --threshold 1500
```

# CLI Command Reference

*Last Updated: 2026-05-15 18:56 | Version: 1.2.0*

The `franklinwh_cli.py` tool is the primary interface for controlling and monitoring FranklinWH aGate systems via Modbus TCP. It supports both native hardware modes and advanced virtual software orchestration.

### Master Option Reference

| Category | Option | Purpose / Function | Typical Use Case |
|:---------|:-------|:-------------------|:-----------------|
| **Connection** | `-i`, `--ip` | Target device network address. | **Mandatory** for all operations. |
| | `-u`, `--unit` | Modbus Unit ID (Slave ID). | Use `2` for aGate, `1` for direct PDU access. |
| | `-t`, `--timeout` | Connection wait time (seconds). | Increase if on a high-latency WiFi link. |
| **Modes** | `--mode` | Change **Native Hardware** mode. | Switching between SC and TOU permanently. |
| | `--vmode` | Run **Virtual Software** loop. | Orchestrating Peak Shaving or Emergency Backup. |
| **Actions** | `--charge` | Import power from grid to battery. | Force charging before a storm or low-rate window. |
| | `--discharge` | Export power from battery to home/grid. | Reducing grid usage during expensive Peak periods. |
| | `--max-charge` | Force charge at full inverter rating. | Rapidly filling battery when time is limited. |
| | `--standby` | Idle the battery (0W flow). | Disabling battery usage without turning off system. |
| | `--stop` | Release Modbus control (WSetEna=0). | Returning system to cloud control after manual test. |
| **Limits** | `--target-soc` | Goal SoC for current action. | Charging battery to exactly 80% to preserve life. |
| | `--reserve` | Minimum SoC for SC/TOU modes. | Ensuring 30% is kept for outages in SC mode. |
| | `--threshold` | Power trigger for Peak Shaving. | Starting discharge only when home load exceeds 2kW. |
| | `--max-charge-soc`| Safety ceiling for charging. | Auto-stopping a charge at 95% to avoid cell stress. |
| **Safety** | `--revert` | Software watchdog timer (seconds). | **Critical Safety**: Auto-stop if your PC/script crashes. |
| | `--duration` | Total run time for a command. | Charging for exactly 30 minutes then exiting. |
| | `--force` | Bypass safety SoC checks. | Discharging below 10% during a testing emergency. |
| **Automation** | `--sequence` | Execute an in-line JSON sequence. | Enabling remote control and charging in one line. |
| | `--sequence-file`| Execute a multi-step JSON file. | Running a 10-step hardware verification test. |
| | `--schedule-file`| Load a 24h TOU JSON schedule. | Fully automating battery logic for a specific utility. |
| **Diagnostics** | `--status` | Snapshot of current metrics. | Checking SoC and current power flow via terminal. |
| | `--monitor` | Real-time TUI dashboard. | Monitoring system behavior during a manual test. |
| | `--healthcheck` | Comprehensive system scan. | Troubleshooting "Zombie States" or connection issues. |
| | `--check-alarms` | Decode hardware error bitfields. | Diagnosing battery internal faults or grid errors. |
| **UI** | `--theme` | Change dashboard color palette. | Using 'Paper' theme for high-contrast visibility. |
| | `--detail` | Enable verbose status output. | Seeing raw register values in the status summary. |

---

## Example Scenarios

### Force Charge for 1 Hour with Safety Timeout
```bash
# Charges at 3000W, reverts to cloud control automatically after 3600s
python3 tools/franklinwh_cli.py -i 192.168.0.110 --charge 3000 --revert 3600 --loop
```

### Run Virtual Peak Shaving
```bash
python3 tools/franklinwh_cli.py -i 192.168.0.110 --vmode peak_shave --threshold 1500
```

### Execute a Hardware Test Sequence
```bash
python3 tools/franklinwh_cli.py -i 192.168.0.110 --sequence-file examples/test_write_reversion.json
```

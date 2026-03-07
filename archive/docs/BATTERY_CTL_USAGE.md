# battery_ctl.py Usage Guide

## Command Format

```bash
python3 battery_ctl.py <IP> <POWER> [OPTIONS]
```

## Important Flag Understanding

### --status Flag
**Reads ONLY, makes NO changes**

```bash
# This ONLY reads current state (ignores 3000)
python3 battery_ctl.py 192.168.0.110 3000 --status  ❌ Does nothing!

# This reads current state (correct usage)
python3 battery_ctl.py 192.168.0.110 --status  ✅ View only
```

### Without --status
**Reads current state, THEN makes changes**

```bash
# This will actually discharge at 3000W
python3 battery_ctl.py 192.168.0.110 3000  ✅ Changes power!

# With verbose to see each step
python3 battery_ctl.py 192.168.0.110 3000 --verbose  ✅ Changes + debug output
```

## Common Commands

### Just View Current State
```bash
python3 battery_ctl.py 192.168.0.110 --status
```

### Change to Discharge 3000W (with paranoid debug mode)
```bash
python3 battery_ctl.py 192.168.0.110 3000 --verbose
```

### Change to Charge 2000W (with paranoid debug mode)
```bash
python3 battery_ctl.py 192.168.0.110 -2000 --verbose
```

### Set Idle (disable control, with paranoid debug mode)
```bash
python3 battery_ctl.py 192.168.0.110 0 --verbose
```

## Flag Combinations

| Command | Effect |
|---------|--------|
| `... --status` | Read only, no changes |
| `... 3000` | Read, then change to 3000W discharge |
| `... 3000 --verbose` | Read, change to 3000W, show register values |
| `... 3000 --status` | ❌ **Just reads!** (ignores 3000) |
| `... --status --verbose` | Read only (verbose has no effect in status mode) |

## Rule of Thumb

- **Want to VIEW?** → Use `--status`
- **Want to CHANGE?** → Use power value WITHOUT `--status`
- **Want PARANOID DEBUG?** → Add `--verbose` to the CHANGE command

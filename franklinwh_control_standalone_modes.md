| Component | Source | Integration Status |
|-----------|--------|-------------------|
| `FranklinWHController` | `franklinwh_control_standalone.py` | ✅ Preserved, enhanced with `timeout` |
| `VirtualModeController` | `virtual_mode_controller.py` | ✅ Integrated with adapter methods |
| `TOUSchedule` | `virtual_mode_controller.py` | ✅ Preserved with `get_current_period()` |
| `VirtualMode` enum | `virtual_mode_controller.py` | ✅ Mapped to CLI `--mode` choices |
| Safety limits | Both | ✅ Consolidated in `_apply_safety_limits()` |
| Signal handling | `virtual_mode_controller.py` | ✅ Added to `main()` |
| `atexit` cleanup | `virtual_mode_controller.py` | ✅ Preserved in class |
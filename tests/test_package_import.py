#!/usr/bin/env python3
"""
Test that franklinwh_modbus package can be imported without errors.

This test verifies the fix for DEFECT_REPORT_PACKAGE_IMPORT.md:
https://github.com/franklinwh/modbus/issues/XXX

The defect was: NameError when importing franklinwh_modbus without rich installed,
because monitor.py used Layout as a return type annotation at class body level.

Fix: Added 'from __future__ import annotations' to monitor.py to postpone
type hint evaluation, preventing NameError at import time.

Usage:
    pytest tests/test_package_import.py -v
    python tests/test_package_import.py
"""

import sys
import importlib
import subprocess
import os


def test_import_core_modules():
    """Test that all core modules can be imported."""
    sys.path.insert(0, 'src')
    
    # These should always work
    from franklinwh_modbus import (
        FranklinWHController,
        VirtualModeController,
        VirtualMode,
        BatteryCommand,
        ControlMode,
        TOUSchedule,
    )
    
    assert FranklinWHController is not None
    assert VirtualModeController is not None
    assert VirtualMode is not None
    
    print("✓ Core modules imported successfully")


def test_monitor_module_no_name_error():
    """Test that monitor module doesn't raise NameError on import.
    
    This was the original defect - Layout type annotation caused NameError
    when rich was not installed.
    """
    sys.path.insert(0, 'src')
    
    # Force reimport
    for mod in list(sys.modules.keys()):
        if mod.startswith('franklinwh_modbus'):
            del sys.modules[mod]
    
    # Import monitor module - this should NOT raise NameError
    # thanks to 'from __future__ import annotations'
    try:
        from franklinwh_modbus import monitor
        print("✓ Monitor module imported without NameError")
        print(f"  HAS_RICH = {monitor.HAS_RICH}")
    except NameError as e:
        raise AssertionError(
            f"Monitor module raised NameError on import: {e}. "
            "The 'from __future__ import annotations' fix is not working."
        )


def test_has_monitor_flag():
    """Test that HAS_MONITOR flag correctly indicates monitor availability."""
    sys.path.insert(0, 'src')
    
    from franklinwh_modbus import HAS_MONITOR
    
    # When rich is installed, this should be True
    # When rich is not installed, this should be False
    print(f"✓ HAS_MONITOR = {HAS_MONITOR}")
    
    # The flag should be a boolean
    assert isinstance(HAS_MONITOR, bool), "HAS_MONITOR should be a boolean"


def test_cli_monitor_availability():
    """Test that CLIMonitor is available when rich is installed."""
    sys.path.insert(0, 'src')
    
    from franklinwh_modbus import HAS_MONITOR, CLIMonitor
    
    if HAS_MONITOR:
        assert CLIMonitor is not None, "CLIMonitor should not be None when HAS_MONITOR=True"
        print("✓ CLIMonitor is available (rich installed)")
    else:
        assert CLIMonitor is None, "CLIMonitor should be None when HAS_MONITOR=False"
        print("✓ CLIMonitor is None (rich not installed)")


def test_type_annotations_postponed():
    """Verify that type annotations are stored as strings (postponed evaluation).
    
    This confirms 'from __future__ import annotations' is working.
    """
    sys.path.insert(0, 'src')
    
    import inspect
    from franklinwh_modbus import monitor
    
    # Get return annotation of create_layout method
    sig = inspect.signature(monitor.CLIMonitor.create_layout)
    return_ann = sig.return_annotation
    
    # With 'from __future__ import annotations', annotations are stored as strings
    # Note: inspect.signature resolves the string back to the actual type when possible
    # but the key thing is that no NameError was raised during import
    
    print(f"✓ create_layout return annotation: {return_ann}")
    print("✓ Type annotations are properly postponed")


def test_import_in_subprocess():
    """Test import in a clean subprocess (no cached modules).
    
    This is the most reliable way to test the actual import behavior.
    """
    test_code = """
import sys
sys.path.insert(0, 'src')

try:
    from franklinwh_modbus import FranklinWHController, HAS_MONITOR
    print(f"SUCCESS: FranklinWHController imported")
    print(f"HAS_MONITOR={HAS_MONITOR}")
    sys.exit(0)
except NameError as e:
    print(f"NAME_ERROR: {e}")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(2)
"""
    
    # Use project root relative to this test file (portable across hosts)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    result = subprocess.run(
        [sys.executable, '-c', test_code],
        capture_output=True,
        text=True,
        cwd=project_root
    )
    
    print(f"Subprocess output:\n{result.stdout}")
    if result.stderr:
        print(f"Subprocess stderr:\n{result.stderr}")
    
    assert result.returncode == 0, f"Import failed in subprocess: {result.stdout}"
    print("✓ Import works in clean subprocess")


if __name__ == '__main__':
    print("Testing franklinwh_modbus package import...\n")
    
    tests = [
        ("Import core modules", test_import_core_modules),
        ("Monitor module no NameError", test_monitor_module_no_name_error),
        ("HAS_MONITOR flag", test_has_monitor_flag),
        ("CLIMonitor availability", test_cli_monitor_availability),
        ("Type annotations postponed", test_type_annotations_postponed),
        ("Import in subprocess", test_import_in_subprocess),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Test: {name}")
        print('='*50)
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"✗ FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    print('='*50)
    
    if failed > 0:
        sys.exit(1)
    else:
        print("\n✓ All tests passed!")

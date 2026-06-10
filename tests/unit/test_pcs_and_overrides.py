import pytest
from unittest.mock import Mock, patch, MagicMock
from franklinwh_modbus import FranklinWHController, VirtualModeController

class TestPCSAndOverrides:
    """Unit tests for capacity overrides, capability schema loading, and VMC software PCS limits."""

    @pytest.fixture
    def mock_controller(self):
        """Create an un-connected FranklinWHController for unit testing."""
        with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
            ctrl = FranklinWHController(ip_address='127.0.0.1')
            ctrl.dev = MagicMock()
            return ctrl

    def test_constructor_overrides_priority(self):
        """Verify that constructor-provided overrides take immediate priority and bypass Model 702."""
        with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
            ctrl = FranklinWHController(
                ip_address='127.0.0.1',
                max_charge_w=7500.0,
                max_discharge_w=8500.0
            )
            # Call discover_ratings - should apply overrides and set RATED_MAX_W without accessing Model 702
            ctrl.get_model = Mock(return_value=None)
            ctrl.discover_ratings()
            
            assert ctrl.RATED_MAX_CHARGE_W == 7500.0
            assert ctrl.RATED_MAX_DISCHARGE_W == 8500.0
            assert ctrl.RATED_MAX_W == 8500.0
            ctrl.get_model.assert_not_called()

    def test_partial_overrides(self, mock_controller):
        """Verify that a single override merges cleanly with discovered Model 702 values."""
        # Override only max_charge_w, let max_discharge_w be discovered
        mock_controller._override_max_charge_w = 6000.0
        
        m702 = MagicMock()
        m702.W_SF.value = 2
        m702.WMaxRtg.value = 50
        m702.WChaRteMaxRtg.value = 50
        m702.WDisChaRteMaxRtg.value = 40  # 40 * 100 = 4000W
        
        mock_controller.get_model = Mock(return_value=m702)
        mock_controller.discover_ratings()
        
        assert mock_controller.RATED_MAX_CHARGE_W == 6000.0  # From override
        assert mock_controller.RATED_MAX_DISCHARGE_W == 4000.0  # From Model 702
        assert mock_controller.RATED_MAX_W == 6000.0

    def test_load_capability_schema(self, mock_controller):
        """Verify that modbus_capability.json loads successfully and contains valid structure."""
        schema = mock_controller.load_capability_schema()
        assert isinstance(schema, dict)
        assert "device" in schema
        assert "models" in schema
        assert "extensions" in schema
        assert schema["device"]["manufacturer"] == "FranklinWH"
        assert "702" in schema["models"]
        assert "15507" in schema["extensions"]

    def test_vmc_software_pcs_battery_limits(self, mock_controller):
        """Verify that battery charge and discharge software PCS limits clamp calculations."""
        vmc = VirtualModeController(
            mock_controller,
            battery_charge_limit_w=3000.0,
            battery_discharge_limit_w=2000.0
        )
        
        # Idle status for context
        status = {'grid': {'grid_power_w': 0.0}}
        
        # Charge clamping: 4000W -> 3000W
        clamped_charge = vmc._apply_software_pcs_limits(4000.0, status)
        assert clamped_charge == 3000.0
        
        # Safe charge below limit: 2000W -> 2000W
        safe_charge = vmc._apply_software_pcs_limits(2000.0, status)
        assert safe_charge == 2000.0
        
        # Discharge clamping: -3500W -> -2000W
        clamped_discharge = vmc._apply_software_pcs_limits(-3500.0, status)
        assert clamped_discharge == -2000.0
        
        # Safe discharge below limit: -1500W -> -1500W
        safe_discharge = vmc._apply_software_pcs_limits(-1500.0, status)
        assert safe_discharge == -1500.0

    def test_vmc_software_pcs_grid_import_limits(self, mock_controller):
        """Verify that grid import limits dynamically scale back battery charge power."""
        vmc = VirtualModeController(
            mock_controller,
            grid_import_limit_w=2000.0
        )
        
        # Grid is importing 3500W (1500W over the 2000W limit)
        status = {'grid': {'grid_power_w': 3500.0}}
        
        # Battery wants to charge at 2500W. Should scale back by 1500W -> 1000W.
        clamped = vmc._apply_software_pcs_limits(2500.0, status)
        assert clamped == 1000.0
        
        # If battery is discharging (power < 0), grid import limit shouldn't reduce it
        discharging = vmc._apply_software_pcs_limits(-1500.0, status)
        assert discharging == -1500.0

    def test_vmc_software_pcs_grid_export_limits(self, mock_controller):
        """Verify that grid export limits dynamically scale back battery discharge power."""
        vmc = VirtualModeController(
            mock_controller,
            grid_export_limit_w=1000.0
        )
        
        # Grid is exporting 1800W (-1800W, which is 800W over the 1000W export limit)
        status = {'grid': {'grid_power_w': -1800.0}}
        
        # Battery wants to discharge at -2000W (actual discharging).
        # Excess export is 800W. Discharge should scale back to -1200W.
        clamped = vmc._apply_software_pcs_limits(-2000.0, status)
        assert clamped == -1200.0
        
        # If battery is charging (power > 0), grid export limit shouldn't affect it
        charging = vmc._apply_software_pcs_limits(1500.0, status)
        assert charging == 1500.0

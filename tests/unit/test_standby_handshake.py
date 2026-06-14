import pytest
from unittest.mock import MagicMock, patch
from franklinwh_modbus import FranklinWHController

class TestStandbyHandshake:
    @pytest.fixture
    def mock_controller(self):
        with patch('franklinwh_modbus.controller.SUNSPEC_AVAILABLE', True):
            ctrl = FranklinWHController(ip_address='127.0.0.1')
            # Mock the _with_retry helper to execute immediately
            ctrl._with_retry = lambda op, *args, **kwargs: op()
            return ctrl

    def test_standby_handshake_active_vpp(self, mock_controller):
        """Test standby handshake executes when remote control is active (WSetEna=1)."""
        m704 = MagicMock()
        
        # Initial values: remote control is active
        m704.WSetEna = MagicMock(value=1)
        m704.WSetPct = MagicMock(value=50)
        m704.WSet = MagicMock(value=2500)
        
        # Track writes
        write_states = []
        
        def mock_read():
            # Simply update values to simulate register read-back
            pass
            
        def mock_write():
            # Capture the state of the registers at write time
            write_states.append({
                'WSetEna': m704.WSetEna.value,
                'WSetPct': m704.WSetPct.value,
                'WSet': m704.WSet.value
            })
            
        m704.read = mock_read
        m704.write = mock_write
        
        mock_controller.models = {704: m704}
        
        # Patch time.sleep to run instantly but track calls
        with patch('time.sleep') as mock_sleep:
            # We want to change the read back values on the final read (which checks for success)
            # In the code: m704.read() is called, then success check: success = (WSetEna == 0 and WSetPct == 0)
            # So after the second write, we want to simulate the readback of 0 values.
            # To do that, when WSetEna is written to 0, we update our mock values:
            def side_effect_write():
                mock_write()
                if m704.WSetEna.value == 0:
                    m704.WSetEna.value = 0
                    m704.WSetPct.value = 0
                    m704.WSet.value = 0
                    
            m704.write = side_effect_write
            
            success = mock_controller.reset_control_state(handshake_wait_s=1.5)
            
            assert success
            # Should have called sleep twice: once for handshake_wait_s, once for settle (0.5s)
            mock_sleep.assert_any_call(1.5)
            mock_sleep.assert_any_call(0.5)
            
            # Verify the two-stage write sequence:
            # First write: Force 0W (WSetEna=1, WSetPct=0, WSet=0)
            # Second write: Release control (WSetEna=0, WSetPct=0, WSet=0)
            assert len(write_states) == 2
            assert write_states[0] == {'WSetEna': 1, 'WSetPct': 0, 'WSet': 0}
            assert write_states[1] == {'WSetEna': 0, 'WSetPct': 0, 'WSet': 0}

    def test_standby_handshake_already_inactive(self, mock_controller):
        """Test standby handshake is skipped when remote control is inactive (WSetEna=0)."""
        m704 = MagicMock()
        
        # Initial values: remote control is inactive
        m704.WSetEna = MagicMock(value=0)
        m704.WSetPct = MagicMock(value=0)
        m704.WSet = MagicMock(value=0)
        
        write_states = []
        m704.read = MagicMock()
        m704.write = lambda: write_states.append({
            'WSetEna': m704.WSetEna.value,
            'WSetPct': m704.WSetPct.value,
            'WSet': m704.WSet.value
        })
        
        mock_controller.models = {704: m704}
        
        with patch('time.sleep') as mock_sleep:
            success = mock_controller.reset_control_state(handshake_wait_s=1.5)
            
            assert success
            # Should not call sleep with 1.5 because WSetEna was already 0.
            # It should only call sleep with 0.5 for settle.
            mock_sleep.assert_called_once_with(0.5)
            
            # Only 1 write should be captured (the final release write)
            assert len(write_states) == 1
            assert write_states[0] == {'WSetEna': 0, 'WSetPct': 0, 'WSet': 0}

    def test_standby_handshake_wait_zero(self, mock_controller):
        """Test standby handshake is skipped when handshake_wait_s is 0."""
        m704 = MagicMock()
        
        # Initial values: remote control is active
        m704.WSetEna = MagicMock(value=1)
        m704.WSetPct = MagicMock(value=50)
        m704.WSet = MagicMock(value=2500)
        
        write_states = []
        
        def side_effect_write():
            write_states.append({
                'WSetEna': m704.WSetEna.value,
                'WSetPct': m704.WSetPct.value,
                'WSet': m704.WSet.value
            })
            if m704.WSetEna.value == 0:
                m704.WSetEna.value = 0
                m704.WSetPct.value = 0
                m704.WSet.value = 0
                
        m704.read = MagicMock()
        m704.write = side_effect_write
        
        mock_controller.models = {704: m704}
        
        with patch('time.sleep') as mock_sleep:
            success = mock_controller.reset_control_state(handshake_wait_s=0)
            
            assert success
            # Should not sleep with 0
            mock_sleep.assert_called_once_with(0.5)
            
            # Direct release write (since wait is 0)
            assert len(write_states) == 1
            assert write_states[0] == {'WSetEna': 0, 'WSetPct': 0, 'WSet': 0}

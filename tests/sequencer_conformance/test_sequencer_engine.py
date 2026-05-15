import pytest
import time
from unittest.mock import MagicMock, patch, call
from src.franklinwh_modbus.sequencer import SunSpecSequencer

class TestSequencerEngine:
    """TestSuite for the Infopoint Sequencer Engine."""

    @pytest.fixture
    def mock_device(self):
        """Create a mock SunSpec device with models 704 and 713."""
        device = MagicMock()
        
        # Model 704 (Control)
        m704 = MagicMock()
        m704.WSetEna = MagicMock(value=0)
        m704.WSetEna.pdef = MagicMock(sf=None, offset=0)
        m704.WSetPct = MagicMock(value=0)
        m704.WSetPct.pdef = MagicMock(sf=None, offset=1)
        m704.WSet = MagicMock(value=0)
        m704.WSet.pdef = MagicMock(sf=None, offset=2)
        
        # Model 713 (Battery)
        m713 = MagicMock()
        m713.SoC = MagicMock(value=50)
        m713.SoC.pdef = MagicMock(sf=None, offset=0)
        
        device.models = {704: m704, 713: m713}
        return device

    def test_basic_write(self, mock_device):
        """Test that a basic write step correctly sets values."""
        seq = SunSpecSequencer(mock_device)
        steps = [
            {
                "step": "Enable",
                "writes": {"704.WSetEna": 1},
                "verify": False
            }
        ]
        
        success = seq.run_sequence(steps)
        
        assert success
        assert mock_device.models[704].WSetEna.value == 1
        mock_device.models[704].write.assert_called()

    def test_verification_loop(self, mock_device):
        """Test that the sequencer waits for a value to reflect in hardware."""
        seq = SunSpecSequencer(mock_device)
        
        # Simulate hardware being slow: first read returns 0, second returns 1
        mock_device.models[704].WSetEna.value = 1
        with patch.object(seq, 'read_value', side_effect=[0, 0, 1]):
            steps = [
                {
                    "step": "Verify Step",
                    "writes": {"704.WSetEna": 1},
                    "verify": True,
                    "verify_timeout_ms": 1000
                }
            ]
            success = seq.run_sequence(steps)
            assert success

    def test_wait_for_condition(self, mock_device):
        """Test polling a register until a condition is met."""
        seq = SunSpecSequencer(mock_device)
        
        # Simulate SoC dropping: 50 -> 48 -> 45
        with patch.object(seq, 'read_value', side_effect=[50, 48, 45]):
            steps = [
                {
                    "step": "Wait for 45%",
                    "wait_for": {
                        "point": "713.SoC",
                        "operator": "<=",
                        "value": 45,
                        "timeout_ms": 5000,
                        "poll_ms": 10
                    }
                }
            ]
            success = seq.run_sequence(steps)
            assert success

    @patch('time.sleep')
    def test_sleep_execution(self, mock_sleep, mock_device):
        """Test that sleep_ms correctly pauses execution."""
        seq = SunSpecSequencer(mock_device)
        steps = [
            {
                "step": "Pause",
                "sleep_ms": 500
            }
        ]
        
        seq.run_sequence(steps)
        mock_sleep.assert_called_with(0.5)

    def test_abort_on_failure(self, mock_device):
        """Test that the sequence stops if a write fails verification."""
        seq = SunSpecSequencer(mock_device)
        
        # Simulate verification failure (never matches)
        with patch.object(seq, 'read_value', return_value=0):
            steps = [
                {
                    "step": "Failing Step",
                    "writes": {"704.WSetEna": 1},
                    "verify": True,
                    "verify_timeout_ms": 100
                },
                {
                    "step": "Should Never Run",
                    "writes": {"704.WSetPct": 100}
                }
            ]
            success = seq.run_sequence(steps)
            assert not success
            # Second step should NOT have been called
            assert mock_device.models[704].WSetPct.value == 0

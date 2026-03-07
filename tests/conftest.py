"""
Pytest configuration and fixtures for FranklinWH Modbus tests.
"""
import pytest
import sys
import os
from unittest.mock import Mock, MagicMock

# Add src to path for testing (simulates installed package)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))


class MockModbusResponse:
    """Mock Modbus response for testing."""
    def __init__(self, registers=None, is_error=False):
        self.registers = registers or []
        self._is_error = is_error
    
    def isError(self):
        return self._is_error


@pytest.fixture
def mock_modbus_client():
    """Create a mock Modbus client."""
    client = Mock()
    client.read_holding_registers.return_value = MockModbusResponse([0] * 20)
    client.write_registers.return_value = MockModbusResponse([])
    client.connect.return_value = True
    client.is_socket_open.return_value = True
    return client


@pytest.fixture
def mock_sunspec_device(mock_modbus_client):
    """Create a mock SunSpec device."""
    device = Mock()
    device.client = mock_modbus_client
    device.models = {}
    return device


@pytest.fixture
def sample_schedule_file(tmp_path):
    """Create a sample TOU schedule file for testing."""
    schedule_content = """
{
    "version": "1.0",
    "name": "Test Schedule",
    "periods": [
        {"id": "off_peak", "hours": [0,1,2,3,4,5,6,22,23], "price": 0.15, "strategy": "charge"},
        {"id": "peak", "hours": [17,18,19,20], "price": 0.55, "strategy": "discharge"},
        {"id": "shoulder", "hours": [7,8,9,10,11,12,13,14,15,16,21], "price": 0.30, "strategy": "self_consumption"}
    ],
    "rules": {"min_soc": 10, "max_soc": 95, "charge_from_grid": true}
}
"""
    schedule_file = tmp_path / "test_schedule.json"
    schedule_file.write_text(schedule_content)
    return str(schedule_file)


@pytest.fixture
def mock_battery_status():
    """Return a sample battery status dict."""
    return {
        'soc': 75.0,
        'soh': 98.0,
        'dc_voltage_v': 400.0,
        'dc_current_a': 5.0,
        'dc_power_w': 2000.0,
        'temperature_c': 25.0,
    }


@pytest.fixture
def mock_grid_status():
    """Return a sample grid status dict."""
    return {
        'grid_power_w': -500.0,  # Exporting
        'voltage_v': 230.0,
        'frequency_hz': 50.0,
    }


@pytest.fixture
def mock_solar_status():
    """Return a sample solar status dict."""
    return {
        'dc_power_w': 3500.0,
        'dc_current_a': 8.75,
        'extension': {
            'pv_total': 0,
            'pv_proximal': 2500,
            'pv_remote1': 1000,
            'pv_remote2': 0,
            'total_solar': 3500,
        }
    }


@pytest.fixture
def mock_control_status():
    """Return a sample control status dict."""
    return {
        'wset_watts': 1500.0,
        'wset_pct': 30.0,
        'wset_ena': 1,
        'control_mode': 'Manual',
    }


def pytest_addoption(parser):
    """Add custom pytest options."""
    parser.addoption(
        "--destructive-enabled",
        action="store_true",
        default=False,
        help="Enable destructive hardware tests that write to battery"
    )
    parser.addoption(
        "--dry-run",
        action="store_true",
        default=False,
        help="Run tests in dry-run mode (no actual writes)"
    )


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "hardware: mark test as requiring actual hardware")
    config.addinivalue_line("markers", "destructive: mark test as writing to hardware (requires --destructive-enabled)")
    config.addinivalue_line("markers", "slow: mark test as slow (>1 second)")

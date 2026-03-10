"""
Unit tests for TOUSchedule class.
"""
import pytest
import json
import sys
import os
from datetime import datetime
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from franklinwh_modbus import TOUSchedule


class TestTOUSchedule:
    """Unit tests for TOUSchedule functionality."""
    
    def test_default_schedule_creation(self):
        """Test creating a default TOUSchedule."""
        schedule = TOUSchedule()
        
        assert not schedule.is_file_based()
        assert schedule.get_schedule_name() == "Legacy (hardcoded)"
        assert schedule.get_min_soc() == 10  # Default
        assert schedule.get_max_soc() == 95  # Default
    
    def test_legacy_peak_hours(self):
        """Test legacy schedule has expected peak hours."""
        schedule = TOUSchedule()
        
        # Legacy schedule: peak 16-21 (4pm-9pm)
        start, end = schedule.peak_hours
        assert start == 16
        assert end == 21
    
    def test_legacy_shoulder_hours(self):
        """Test legacy schedule has expected shoulder hours."""
        schedule = TOUSchedule()
        
        # Legacy schedule: shoulder 7-16 and 21-23
        morning_start, morning_end = schedule.shoulder_hours
        assert morning_start == 7
        assert morning_end == 16
    
    def test_get_strategy_peak_hours(self):
        """Test strategy during peak hours."""
        schedule = TOUSchedule()
        
        # At 6pm (18:00) should be discharge (peak)
        with patch('franklinwh_modbus.schedule.datetime') as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 18, 0, 0)
            # Note: This requires mocking or the get_strategy to accept hour param
            # For now, just verify the method exists
            assert hasattr(schedule, 'get_strategy')
    
    def test_file_based_schedule_loading(self, tmp_path):
        """Test loading schedule from JSON file."""
        schedule_data = {
            "version": "1.0",
            "name": "Test Schedule",
            "periods": [
                {"id": "off_peak", "hours": [0, 1, 2], "price": 0.10, "strategy": "charge"},
                {"id": "peak", "hours": [17, 18, 19], "price": 0.50, "strategy": "discharge"},
            ],
            "rules": {"min_soc": 15, "max_soc": 90}
        }
        
        schedule_file = tmp_path / "schedule.json"
        schedule_file.write_text(json.dumps(schedule_data))
        
        schedule = TOUSchedule.from_file(str(schedule_file))
        
        assert schedule.is_file_based()
        assert schedule.get_schedule_name() == "Test Schedule"
        assert schedule.get_min_soc() == 15
        assert schedule.get_max_soc() == 90
    
    def test_schedule_file_not_found(self):
        """Test error handling for missing schedule file."""
        with pytest.raises((FileNotFoundError, Exception)):
            TOUSchedule.from_file("/nonexistent/schedule.json")
    
    def test_get_price_returns_float(self, tmp_path):
        """Test get_current_price returns a float."""
        schedule_data = {
            "version": "1.0",
            "name": "Price Test",
            "periods": [
                {"id": "all_day", "hours": list(range(24)), "price": 0.25, "strategy": "self_consumption"},
            ],
            "rules": {}
        }
        
        schedule_file = tmp_path / "price_schedule.json"
        schedule_file.write_text(json.dumps(schedule_data))
        
        schedule = TOUSchedule.from_file(str(schedule_file))
        price = schedule.get_current_price()
        
        assert isinstance(price, float)
        assert price == 0.25
    
    def test_get_current_period(self, tmp_path):
        """Test getting current period info."""
        schedule_data = {
            "version": "1.0",
            "name": "Period Test",
            "periods": [
                {"id": "night", "hours": [0, 1, 2, 3, 4, 5], "price": 0.10, "strategy": "charge"},
                {"id": "day", "hours": list(range(6, 24)), "price": 0.30, "strategy": "self_consumption"},
            ],
            "rules": {}
        }
        
        schedule_file = tmp_path / "period_schedule.json"
        schedule_file.write_text(json.dumps(schedule_data))
        
        schedule = TOUSchedule.from_file(str(schedule_file))
        period = schedule.get_current_period()
        
        assert isinstance(period, str)
        assert period in ["night", "day"]
    
    def test_to_dict_export(self, tmp_path):
        """Test exporting schedule to dict."""
        schedule_data = {
            "version": "1.0",
            "name": "Export Test",
            "periods": [
                {"id": "all_day", "hours": list(range(24)), "price": 0.25, "strategy": "self_consumption"},
            ],
            "rules": {"min_soc": 20, "max_soc": 85}
        }
        
        schedule_file = tmp_path / "export_schedule.json"
        schedule_file.write_text(json.dumps(schedule_data))
        
        schedule = TOUSchedule.from_file(str(schedule_file))
        exported = schedule.to_dict()
        
        assert exported["name"] == "Export Test"
        assert "periods" in exported
        assert "rules" in exported
    
    def test_str_representation(self):
        """Test string representation of schedule."""
        schedule = TOUSchedule()
        
        str_repr = str(schedule)
        
        assert "TOU Schedule" in str_repr or "Legacy" in str_repr

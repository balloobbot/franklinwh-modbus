"""
FranklinWH Modbus Battery Manager - Time-of-Use Schedule

This module provides TOU (Time-of-Use) scheduling for battery arbitrage
and peak shaving operations.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TOUSchedule:
    """Time-of-use rate periods for arbitrage.
    
    Supports both legacy hardcoded schedules and file-based configuration.
    File-based schedules provide more flexibility with custom periods,
    strategies, and constraint rules.
    
    Example JSON schedule file:
        {
            "version": "1.0",
            "name": "My Schedule",
            "periods": [
                {"id": "peak", "hours": [17,18,19,20], "price": 0.55, "strategy": "discharge"},
                {"id": "off_peak", "hours": [0,1,2,3,4,5,6], "price": 0.15, "strategy": "charge"}
            ],
            "rules": {"min_soc": 10, "max_soc": 95}
        }
    """
    # Legacy fields (for backward compatibility)
    peak_hours: Tuple[int, int] = (16, 21)      # 4 PM - 9 PM
    shoulder_hours: Tuple[int, int] = (7, 16)    # 7 AM - 4 PM
    off_peak_hours: Tuple[int, int] = (21, 7)   # 9 PM - 7 AM
    
    peak_price: float = 0.50          # $/kWh
    shoulder_price: float = 0.25
    off_peak_price: float = 0.10
    
    # File-based schedule support
    _schedule_data: Optional[Dict] = field(default=None, repr=False)
    _source_file: Optional[str] = field(default=None, repr=False)
    
    @classmethod
    def from_file(cls, filepath: str) -> "TOUSchedule":
        """Load TOU schedule from JSON file.
        
        Args:
            filepath: Path to JSON schedule file
            
        Returns:
            TOUSchedule instance with loaded configuration
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file contains invalid JSON or schema
        """
        import json
        
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Schedule file not found: {filepath}")
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        # Validate basic schema
        cls._validate_schedule(data)
        
        # Create instance with schedule data
        instance = cls(_schedule_data=data, _source_file=str(path))
        
        # Try to populate legacy fields for compatibility
        instance._populate_legacy_fields(data)
        
        logger.info(f"Loaded TOU schedule from {filepath}: {data.get('name', 'unnamed')}")
        return instance
    
    @staticmethod
    def _validate_schedule(data: Dict) -> None:
        """Validate schedule file schema."""
        if not isinstance(data, dict):
            raise ValueError("Schedule must be a JSON object")
        
        if 'version' not in data:
            raise ValueError("Schedule must have 'version' field")
        
        if 'periods' not in data or not isinstance(data['periods'], list):
            raise ValueError("Schedule must have 'periods' array")
        
        if len(data['periods']) == 0:
            raise ValueError("Schedule must have at least one period")
        
        for i, period in enumerate(data['periods']):
            if 'id' not in period:
                raise ValueError(f"Period {i} missing 'id' field")
            if 'hours' not in period or not isinstance(period['hours'], list):
                raise ValueError(f"Period '{period.get('id', i)}' missing 'hours' array")
            if 'strategy' not in period:
                raise ValueError(f"Period '{period.get('id', i)}' missing 'strategy' field")
    
    def _populate_legacy_fields(self, data: Dict) -> None:
        """Try to populate legacy fields from schedule for backward compat."""
        # Look for known period types
        for period in data.get('periods', []):
            pid = period.get('id', '').lower()
            hours = period.get('hours', [])
            
            if 'peak' in pid and hours:
                self.peak_hours = (min(hours), max(hours) + 1)
                self.peak_price = period.get('price', self.peak_price)
            elif 'shoulder' in pid and hours:
                self.shoulder_hours = (min(hours), max(hours) + 1)
                self.shoulder_price = period.get('price', self.shoulder_price)
            elif 'off' in pid or 'valley' in pid and hours:
                self.off_peak_hours = (min(hours), max(hours) + 1)
                self.off_peak_price = period.get('price', self.off_peak_price)
    
    def is_file_based(self) -> bool:
        """Check if using file-based schedule."""
        return self._schedule_data is not None
    
    def get_schedule_name(self) -> str:
        """Get schedule name or 'Legacy' if using defaults."""
        if self._schedule_data:
            return self._schedule_data.get('name', 'Unnamed')
        return 'Legacy (hardcoded)'
    
    def get_current_period(self) -> str:
        """Determine current TOU period.
        
        Uses file-based schedule if loaded, otherwise legacy logic.
        """
        if self._schedule_data:
            hour = datetime.now().hour
            for period in self._schedule_data['periods']:
                if hour in period.get('hours', []):
                    return period['id']
            return "unknown"
        
        # Legacy logic
        hour = datetime.now().hour
        p_start, p_end = self.peak_hours
        
        if p_start <= hour < p_end:
            return "peak"
        elif self.shoulder_hours[0] <= hour < self.shoulder_hours[1]:
            return "shoulder"
        else:
            return "off_peak"
    
    def get_current_price(self) -> float:
        """Get current electricity price."""
        if self._schedule_data:
            period_id = self.get_current_period()
            for period in self._schedule_data['periods']:
                if period['id'] == period_id:
                    return period.get('price', 0.25)
            return 0.25
        
        # Legacy logic
        period = self.get_current_period()
        return getattr(self, f"{period}_price", 0.25)
    
    def get_strategy(self) -> str:
        """Get battery strategy for current period.
        
        Returns:
            Strategy name: 'charge', 'discharge', 'self_consumption', 
                          'grid_zero', or 'standby'
        """
        if self._schedule_data:
            period_id = self.get_current_period()
            for period in self._schedule_data['periods']:
                if period['id'] == period_id:
                    return period.get('strategy', 'self_consumption')
        
        # Default strategy based on legacy period
        period = self.get_current_period()
        if period == 'peak':
            return 'discharge'
        elif period == 'off_peak':
            return 'charge'
        else:
            return 'self_consumption'
    
    def get_rules(self) -> Dict[str, Any]:
        """Get constraint rules from schedule."""
        if self._schedule_data:
            return self._schedule_data.get('rules', {})
        return {}
    
    def get_min_soc(self) -> int:
        """Get minimum SoC constraint."""
        return self.get_rules().get('min_soc', 10)
    
    def get_max_soc(self) -> int:
        """Get maximum SoC constraint."""
        return self.get_rules().get('max_soc', 95)
    
    def to_dict(self) -> Dict[str, Any]:
        """Export schedule as dictionary."""
        if self._schedule_data:
            return self._schedule_data
        
        # Legacy format
        return {
            'version': '1.0 (legacy)',
            'name': 'Legacy Hardcoded',
            'periods': [
                {
                    'id': 'peak',
                    'name': 'Peak',
                    'hours': list(range(self.peak_hours[0], self.peak_hours[1])),
                    'price': self.peak_price,
                    'strategy': 'discharge'
                },
                {
                    'id': 'shoulder',
                    'name': 'Shoulder',
                    'hours': list(range(self.shoulder_hours[0], self.shoulder_hours[1])),
                    'price': self.shoulder_price,
                    'strategy': 'self_consumption'
                },
                {
                    'id': 'off_peak',
                    'name': 'Off-Peak',
                    'hours': list(range(self.off_peak_hours[0], 24)) + list(range(0, self.off_peak_hours[1])),
                    'price': self.off_peak_price,
                    'strategy': 'charge'
                }
            ]
        }
    
    def __str__(self) -> str:
        """String representation of schedule."""
        name = self.get_schedule_name()
        period = self.get_current_period()
        price = self.get_current_price()
        strategy = self.get_strategy()
        return f"{name} | Current: {period} (${price:.2f}/kWh) | Strategy: {strategy}"


# Default schedule instance for convenience
DEFAULT_SCHEDULE = TOUSchedule()

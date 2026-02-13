"""
Network Health Monitor - Ping-based WiFi Detection

This module performs ICMP ping checks to detect WiFi/unstable network connections.
Based on real-world evidence: WiFi shows 75% packet loss and massive latency spikes.
"""

import asyncio
import re
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ConnectionQuality(Enum):
    """Network connection quality classification."""
    HEALTHY = "healthy"          # Ethernet-like: <1% loss, <10ms latency
    DEGRADED = "degraded"        # Some issues: 1-10% loss, 10-50ms latency
    CRITICAL = "critical"        # WiFi/unstable: >10% loss or >50ms latency
    UNKNOWN = "unknown"          # Unable to determine


@dataclass
class PingStats:
    """Ping statistics."""
    packets_transmitted: int
    packets_received: int
    packet_loss: float  # Percentage
    min_ms: float
    avg_ms: float
    max_ms: float
    mdev_ms: float  # Standard deviation (jitter)
    
    @property
    def quality(self) -> ConnectionQuality:
        """Classify connection quality based on statistics."""
        # CRITICAL: WiFi or severely unstable
        if self.packet_loss > 10 or self.avg_ms > 50:
            return ConnectionQuality.CRITICAL
        
        # DEGRADED: Some connectivity issues
        if self.packet_loss > 1 or self.avg_ms > 10:
            return ConnectionQuality.DEGRADED
        
        # HEALTHY: Ethernet-like performance
        return ConnectionQuality.HEALTHY


class NetworkHealthMonitor:
    """Monitor network health via ICMP ping."""
    
    def __init__(self, host: str):
        """
        Initialize monitor.
        
        Args:
            host: IP address or hostname to ping
        """
        self.host = host
        self._last_stats: Optional[PingStats] = None
        self._logger = logging.getLogger(__name__)
    
    async def ping_check(self, count: int = 10, timeout: int = 5) -> Optional[PingStats]:
        """
        Run ping check and parse results.
        
        Args:
            count: Number of pings to send
            timeout: Timeout in seconds
            
        Returns:
            PingStats if successful, None if ping failed completely
        """
        try:
            # Run ping command
            cmd = ['ping', '-c', str(count), '-W', str(timeout), self.host]
            
            # Execute with timeout
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout + 5  # Extra buffer
            )
            
            output = stdout.decode('utf-8')
            
            # Parse statistics
            stats = self._parse_ping_output(output)
            if stats:
                self._last_stats = stats
                self._logger.info(
                    f"Ping check: {stats.packet_loss:.1f}% loss, "
                    f"{stats.avg_ms:.1f}ms avg, quality={stats.quality.value}"
                )
            
            return stats
            
        except asyncio.TimeoutError:
            self._logger.warning(f"Ping check timed out for {self.host}")
            return None
        except Exception as e:
            self._logger.error(f"Ping check failed: {e}")
            return None
    
    def _parse_ping_output(self, output: str) -> Optional[PingStats]:
        """
        Parse ping command output.
        
        Example output:
        10 packets transmitted, 8 received, 20% packet loss, time 9012ms
        rtt min/avg/max/mdev = 5.123/15.456/45.789/12.345 ms
        """
        try:
            # Parse packet statistics
            # Format: "N packets transmitted, M received, X% packet loss"
            packet_match = re.search(
                r'(\d+) packets transmitted, (\d+) received.*?(\d+(?:\.\d+)?)% packet loss',
                output
            )
            if not packet_match:
                return None
            
            transmitted = int(packet_match.group(1))
            received = int(packet_match.group(2))
            packet_loss = float(packet_match.group(3))
            
            # Parse RTT statistics
            # Format: "rtt min/avg/max/mdev = 1.234/5.678/9.012/3.456 ms"
            rtt_match = re.search(
                r'rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms',
                output
            )
            
            if rtt_match:
                min_ms = float(rtt_match.group(1))
                avg_ms = float(rtt_match.group(2))
                max_ms = float(rtt_match.group(3))
                mdev_ms = float(rtt_match.group(4))
            else:
                # No RTT data (100% packet loss)
                min_ms = avg_ms = max_ms = mdev_ms = 0.0
            
            return PingStats(
                packets_transmitted=transmitted,
                packets_received=received,
                packet_loss=packet_loss,
                min_ms=min_ms,
                avg_ms=avg_ms,
                max_ms=max_ms,
                mdev_ms=mdev_ms
            )
            
        except Exception as e:
            self._logger.error(f"Failed to parse ping output: {e}")
            return None
    
    @property
    def last_stats(self) -> Optional[PingStats]:
        """Get last ping statistics."""
        return self._last_stats
    
    @property
    def connection_quality(self) -> ConnectionQuality:
        """Get current connection quality assessment."""
        if self._last_stats is None:
            return ConnectionQuality.UNKNOWN
        return self._last_stats.quality


# TODO: Integration points
# 1. Add to main.py - run ping check on startup
# 2. Add periodic check every 5 minutes
# 3. Expose stats via /api/health endpoint
# 4. Show warning modal on dashboard if CRITICAL

#!/usr/bin/env python3
"""
FranklinWH CLI Dashboard Monitor

A terminal-based dashboard that mirrors the web dashboard functionality
with real-time updates and interactive control.

Usage:
    python franklinwh_cli.py -i 192.168.0.110 --monitor
    python franklinwh_monitor.py -i 192.168.0.110 --refresh 2

Keyboard Shortcuts:
    c       Enter charge mode (prompts for watts)
    d       Enter discharge mode (prompts for watts)
    s       Standby (0W)
    m       Max charge
    M       Max discharge
    +       Increase power by 100W
    -       Decrease power by 100W
    r       Reset control (release to idle)
    R       Toggle auto-refresh
    1-9     Set refresh rate (1-9 seconds)
    q       Quit
    Ctrl+C  Quit
"""

import time
import sys
import signal
import threading
import select
import tty
import termios
import os
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque

try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.live import Live
    from rich.table import Table
    from rich.text import Text
    from rich.progress import Progress, BarColumn, TextColumn
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from .controller import FranklinWHController
from .types import BatteryCommand, ControlMode


@dataclass
class MonitorConfig:
    """Configuration for the monitor."""
    ip_address: str
    port: int = 502
    unit_id: int = 2
    timeout: float = 10.0
    refresh_rate: float = 5.0
    use_rich: bool = True
    theme: str = "dark"  # dark, light
    max_history: int = 720  # 60 minutes at 5s intervals


@dataclass
class PowerFlowData:
    """Power flow snapshot."""
    solar_w: float = 0.0
    home_w: float = 0.0
    battery_w: float = 0.0
    grid_w: float = 0.0
    battery_state: str = "IDLE"  # CHARGING, DISCHARGING, IDLE
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SolarData:
    """Solar input breakdown (AC-coupled)."""
    total_w: float = 0.0
    proximal_w: float = 0.0
    remote1_w: float = 0.0
    remote2_w: float = 0.0
    

class KeyboardInput:
    """Non-blocking keyboard input handler for terminal."""
    
    def __init__(self):
        self.key_queue = []
        self.running = False
        self.thread = None
        self.old_settings = None
        
    def _setup_terminal(self):
        """Set terminal to raw mode for single key input."""
        if sys.stdin.isatty():
            self.old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
            
    def _restore_terminal(self):
        """Restore terminal to original settings."""
        if self.old_settings and sys.stdin.isatty():
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
            
    def _read_input(self):
        """Background thread to read keyboard input."""
        self._setup_terminal()
        try:
            while self.running:
                # Use select for non-blocking check with timeout
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    key = sys.stdin.read(1)
                    if key:
                        self.key_queue.append(key)
        finally:
            self._restore_terminal()
            
    def start(self):
        """Start the input thread."""
        self.running = True
        self.thread = threading.Thread(target=self._read_input, daemon=True)
        self.thread.start()
        
    def stop(self):
        """Stop the input thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.5)
            
    def get_key(self) -> Optional[str]:
        """Get next key from queue (non-blocking)."""
        if self.key_queue:
            return self.key_queue.pop(0)
        return None
        
    def clear(self):
        """Clear key queue."""
        self.key_queue.clear()


@dataclass
class SystemData:
    """Complete system state for display."""
    # Power flow
    power_flow: PowerFlowData = field(default_factory=PowerFlowData)
    
    # Battery DC
    soc: float = 0.0
    soh: float = 0.0
    reserve_soc: float = 20.0
    target_soc: float = 100.0
    dc_power: float = 0.0
    dc_current: float = 0.0
    battery_temp: float = 0.0
    available_wh: float = 0.0
    rated_wh: float = 0.0
    
    # AC Power
    ac_voltage: float = 0.0
    ac_current: float = 0.0
    ac_frequency: float = 0.0
    ac_pf: float = 0.0
    ac_va: float = 0.0
    ac_var: float = 0.0
    ac_type: str = "Single-Phase"
    
    # Solar (AC-coupled)
    solar: SolarData = field(default_factory=SolarData)
    
    # Temperatures
    cabinet_temp: float = 0.0
    ambient_temp: float = 0.0
    
    # Lifetime energy (Wh)
    lifetime_injected: float = 0.0
    lifetime_absorbed: float = 0.0
    lifetime_discharged: float = 0.0
    lifetime_charged: float = 0.0
    lifetime_generated: float = 0.0
    
    # System info
    serial: str = ""
    model: str = ""
    firmware: str = ""
    grid_connected: bool = False
    grid_mode: str = "Unknown"  # Grid Following, Grid Forming
    operating_mode: str = "Self-Consumption"
    wset_ena: int = 0
    control_source: str = "Cloud API"
    
    # Alarms
    active_alarms: List[str] = field(default_factory=list)
    extension_writable: bool = False
    
    # History for sparkline
    history: deque = field(default_factory=lambda: deque(maxlen=720))


class CLIMonitor:
    """Terminal-based dashboard monitor for FranklinWH battery."""
    
    def __init__(self, config: MonitorConfig):
        self.config = config
        self.console = Console(theme=self._get_theme()) if HAS_RICH else None
        self.controller: Optional[FranklinWHController] = None
        self.data = SystemData()
        self.running = False
        self.paused = False
        self.current_power = 0  # Current commanded power
        self.input_handler = KeyboardInput()
        self.command_prompt = ""  # Current command being entered
        self.show_prompt = False  # Whether to show command input
        self.prompt_buffer = ""   # Buffer for numeric input
        self.prompt_mode = None   # 'charge' or 'discharge'
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        
    def _get_theme(self):
        """Get Rich theme based on config."""
        if self.config.theme == "dark":
            return None  # Default is dark
        # Could add custom theme here
        return None
        
    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully."""
        self.running = False
        
    def connect(self) -> bool:
        """Connect to the FranklinWH device."""
        try:
            self.controller = FranklinWHController(
                ip_address=self.config.ip_address,
                port=self.config.port,
                unit_id=self.config.unit_id,
                timeout=self.config.timeout
            )
            self.controller.connect()
            return True
        except Exception as e:
            if self.console:
                self.console.print(f"[red]Connection failed: {e}[/red]")
            else:
                print(f"Connection failed: {e}")
            return False
            
    def disconnect(self):
        """Disconnect and cleanup."""
        if self.controller:
            try:
                self.controller.disconnect()
            except:
                pass
            self.controller = None
            
    def _read_extension_registers(self) -> dict:
        """Read FranklinWH extension registers for additional data."""
        if not self.controller or not hasattr(self.controller, 'dev') or not self.controller.dev:
            return {}
            
        try:
            client = self.controller.dev.client
            unit = self.controller.unit_id
            
            # Solar breakdown (15502-15505)
            solar_regs = client.read_holding_registers(15502, 4, slave=unit)
            # Grid power (15506), Home load (15507)
            extra_regs = client.read_holding_registers(15506, 2, slave=unit)
            # Cabinet temp (15516), Ambient temp (15517)
            temp_regs = client.read_holding_registers(15516, 2, slave=unit)
            
            result = {}
            if solar_regs and not solar_regs.isError():
                result['pv_total'] = self._uint16_to_int(solar_regs.registers[0])
                result['pv_proximal'] = self._uint16_to_int(solar_regs.registers[1])
                result['pv_remote1'] = self._uint16_to_int(solar_regs.registers[2])
                result['pv_remote2'] = self._uint16_to_int(solar_regs.registers[3])
                
            if extra_regs and not extra_regs.isError():
                result['grid_import_export'] = self._uint16_to_int(extra_regs.registers[0])
                result['home_load'] = self._uint16_to_int(extra_regs.registers[1])
                
            if temp_regs and not temp_regs.isError():
                result['cabinet_temp'] = temp_regs.registers[0] / 10.0 if temp_regs.registers[0] != 0xFFFF else 0
                result['ambient_temp'] = temp_regs.registers[1] / 10.0 if temp_regs.registers[1] != 0xFFFF else 0
                
            return result
        except Exception as e:
            return {}
            
    def _uint16_to_int(self, value: int) -> int:
        """Convert unsigned 16-bit to signed."""
        if value >= 32768:
            return value - 65536
        return value
        
    def _read_model_714(self) -> dict:
        """Read Model 714 for battery DC data."""
        try:
            m714 = self.controller.get_model(714)
            if not m714:
                return {}
            m714.read()
            
            sf_w = self.controller._get_scale_factor(m714, 'DCW_SF')
            sf_a = self.controller._get_scale_factor(m714, 'DCA_SF')
            sf_tmp = self.controller._get_scale_factor(m714, 'Tmp_SF')
            
            return {
                'dc_power': m714.DCW.value * (10 ** sf_w) if m714.DCW.value is not None else 0,
                'dc_current': m714.DCA.value * (10 ** sf_a) if hasattr(m714, 'DCA') and m714.DCA.value is not None else 0,
                'battery_temp': m714.Tmp.value * (10 ** sf_tmp) if hasattr(m714, 'Tmp') and m714.Tmp.value is not None else 0,
            }
        except Exception as e:
            return {}
            
    def _read_model_701_extra(self) -> dict:
        """Read extra fields from Model 701 (current, PF)."""
        try:
            m701 = self.controller.get_model(701)
            if not m701:
                return {}
            m701.read()
            
            sf_a = self.controller._get_scale_factor(m701, 'A_SF')
            sf_pf = self.controller._get_scale_factor(m701, 'PF_SF')
            
            current = 0
            if hasattr(m701, 'A') and m701.A.value is not None:
                current = m701.A.value * (10 ** sf_a)
            elif hasattr(m701, 'AphA') and m701.AphA.value is not None:
                current = m701.AphA.value * (10 ** sf_a)
                
            pf = 0
            if hasattr(m701, 'PF') and m701.PF.value is not None:
                pf = m701.PF.value * (10 ** sf_pf)
                
            return {
                'current_a': current,
                'power_factor': pf,
            }
        except Exception as e:
            return {}
            
    def _read_nameplate_strings(self) -> dict:
        """Read nameplate and extract string values."""
        try:
            m1 = self.controller.get_model(1)
            if not m1:
                return {}
            m1.read()
            
            def get_point_str(model, point_name):
                pt = getattr(model, point_name, None)
                if pt is None:
                    return ''
                if hasattr(pt, 'value'):
                    val = pt.value
                    if isinstance(val, bytes):
                        return val.decode('utf-8', errors='ignore').strip('\x00').strip()
                    return str(val).strip() if val else ''
                return str(pt).strip() if pt else ''
                
            return {
                'manufacturer': get_point_str(m1, 'Mn'),
                'model': get_point_str(m1, 'Md'),
                'serial': get_point_str(m1, 'SN'),
                'version': get_point_str(m1, 'Vr'),
                'options': get_point_str(m1, 'Opt'),
            }
        except Exception as e:
            return {}
        
    def fetch_data(self) -> bool:
        """Fetch all data from the device."""
        if not self.controller:
            return False
            
        try:
            # Read all status methods
            battery = self.controller.read_battery_status()
            grid = self.controller.read_grid_status()
            solar = self.controller.read_solar_status()
            control = self.controller.read_control_status()
            native = self.controller.read_native_mode()
            ext = self._read_extension_registers()
            
            # Read additional model data
            m714_data = self._read_model_714()
            m701_extra = self._read_model_701_extra()
            nameplate = self._read_nameplate_strings()
            
            # Get extension solar data if available
            ext_solar = solar.get('extension', {})
            solar_total = ext_solar.get('total_solar', abs(solar.get('ac_power_w', 0)))
            
            # Battery DC power (from M714 or fallback)
            # Note: DCW positive = discharging, negative = charging
            battery_dc = m714_data.get('dc_power', 0)
            
            # Grid power: positive = exporting TO grid, negative = importing FROM grid
            # Flip sign for display: positive = importing (consuming from grid)
            grid_raw = grid.get('grid_power_w', 0)
            grid_display = -grid_raw  # Flip: export positive becomes import positive
            
            # Update Power Flow
            self.data.power_flow.solar_w = solar_total
            self.data.power_flow.battery_w = battery_dc
            self.data.power_flow.grid_w = grid_display
            
            # Calculate home load: consumption = solar + battery_discharge + grid_import
            # battery_dc: positive = discharge (adds), negative = charge (subtracts)
            # So: home = solar + battery_dc - grid_raw
            # Where grid_raw positive = export (subtract from home), negative = import (add to home)
            self.data.power_flow.home_w = solar_total + battery_dc - grid_raw
            
            # Determine battery state
            if battery_dc < -50:
                self.data.power_flow.battery_state = "CHARGING"
            elif battery_dc > 50:
                self.data.power_flow.battery_state = "DISCHARGING"
            else:
                self.data.power_flow.battery_state = "IDLE"
                
            # Update Battery DC
            self.data.soc = battery.get('soc', self.data.soc)
            self.data.soh = battery.get('soh', self.data.soh)
            self.data.dc_power = battery_dc
            self.data.dc_current = m714_data.get('dc_current', 0)
            self.data.battery_temp = m714_data.get('battery_temp', 0)
            self.data.available_wh = battery.get('wh_available', 0)
            self.data.rated_wh = battery.get('wh_rating', 0)
            self.data.reserve_soc = native.get('self_reserve_pct', 20.0)
            
            # Update AC Power
            self.data.ac_voltage = grid.get('voltage_v', 0)
            self.data.ac_current = m701_extra.get('current_a', 0)
            self.data.ac_frequency = grid.get('frequency_hz', 0)
            self.data.ac_pf = m701_extra.get('power_factor', 0)
            self.data.ac_va = grid.get('grid_va', 0)
            self.data.ac_var = grid.get('grid_var', 0)
            self.data.ac_type = grid.get('ac_type', 'Single-Phase')
            self.data.grid_connected = grid.get('connection_state') == 'Connected'
            self.data.grid_mode = grid.get('grid_mode', 'Unknown')
            
            # Update Solar (AC-coupled)
            self.data.solar.total_w = solar_total
            self.data.solar.proximal_w = ext_solar.get('pv_proximal', solar_total)
            self.data.solar.remote1_w = ext_solar.get('pv_remote1', 0)
            self.data.solar.remote2_w = ext_solar.get('pv_remote2', 0)
            
            # Update Temperatures
            self.data.cabinet_temp = ext.get('cabinet_temp', 0)
            self.data.ambient_temp = ext.get('ambient_temp', 0)
            
            # Update System Info
            self.data.serial = nameplate.get('serial', '')
            self.data.model = nameplate.get('model', 'aGate X')
            self.data.firmware = nameplate.get('version', '')
            self.data.operating_mode = native.get('mode_name', 'Self-Consumption')
            self.data.wset_ena = control.get('wset_enabled', 0)
            self.data.control_source = 'Modbus' if control.get('wset_enabled') else 'Cloud API'
            self.data.extension_writable = False
            
            # Update Lifetime Energy (from accumulators if available)
            # These would come from M715 or extension registers
            
            # Add to history for sparkline
            self.data.history.append({
                'timestamp': datetime.now(),
                'battery_w': self.data.power_flow.battery_w,
                'solar_w': self.data.power_flow.solar_w,
                'grid_w': self.data.power_flow.grid_w
            })
            
            return True
        except Exception as e:
            return False
            
    def create_layout(self) -> Layout:
        """Create the Rich layout structure."""
        # Main layout with header and body
        layout = Layout(name="root")
        
        # Header
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )
        
        # Body splits
        layout["body"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1)
        )
        
        # Left column
        layout["left"].split_column(
            Layout(name="power_flow", size=8),
            Layout(name="soc_bar", size=5),
            Layout(name="dc_power", size=10)
        )
        
        # Right column
        layout["right"].split_column(
            Layout(name="ac_power", size=8),
            Layout(name="solar", size=10),
            Layout(name="lifetime", size=6)
        )
        
        return layout
        
    def render_header(self) -> Panel:
        """Render the header panel."""
        title = f"FranklinWH Monitor - {self.config.ip_address}:{self.config.port}"
        refresh = f"Refresh: {self.config.refresh_rate:.0f}s"
        status = "PAUSED" if self.paused else "LIVE"
        
        content = Text()
        content.append(title, style="bold cyan")
        content.append(f" | {refresh}", style="dim")
        content.append(f" | [{status}]", style="green" if not self.paused else "yellow")
        
        return Panel(content, box=box.SIMPLE, padding=(0, 1))
        
    def render_power_flow(self) -> Panel:
        """Render Power Flow Summary panel."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Source", style="cyan", justify="left")
        table.add_column("Power", style="white", justify="right")
        table.add_column("State", style="green", justify="left")
        table.add_column("Flow", style="dim", justify="center")
        
        pf = self.data.power_flow
        
        # Solar
        solar_icon = "→" if pf.solar_w > 0 else " "
        table.add_row("Solar", f"{pf.solar_w:>6.0f}W", "Producing", solar_icon)
        
        # Home
        home_icon = "←" if pf.home_w > 0 else " "
        table.add_row("Home", f"{pf.home_w:>6.0f}W", "Consuming", home_icon)
        
        # Battery
        battery_state = pf.battery_state
        battery_style = "green" if battery_state == "CHARGING" else "yellow" if battery_state == "DISCHARGING" else "dim"
        battery_icon = "↓" if battery_state == "CHARGING" else "↑" if battery_state == "DISCHARGING" else "○"
        table.add_row("Battery", f"{abs(pf.battery_w):>6.0f}W", f"[{battery_style}]{battery_state}[/{battery_style}]", battery_icon)
        
        # Grid
        grid_state = "IMPORTING" if pf.grid_w < 0 else "EXPORTING" if pf.grid_w > 0 else "IDLE"
        grid_icon = "←" if pf.grid_w < 0 else "→" if pf.grid_w > 0 else "○"
        table.add_row("Grid", f"{abs(pf.grid_w):>6.0f}W", grid_state, grid_icon)
        
        return Panel(table, title="[bold]Power Flow Summary[/bold]", border_style="blue", box=box.ROUNDED)
        
    def render_soc_bar(self) -> Panel:
        """Render SoC bar with reserve indicator."""
        soc = self.data.soc
        reserve = self.data.reserve_soc
        target = self.data.target_soc
        
        # Create text representation of bar
        bar_width = 30
        filled = int((soc / 100) * bar_width)
        reserve_pos = int((reserve / 100) * bar_width)
        
        bar_text = Text()
        for i in range(bar_width):
            if i < reserve_pos:
                char = "█" if i < filled else "░"
                style = "red" if i < filled else "dim red"
            elif i < filled:
                char = "█"
                style = "green"
            else:
                char = "░"
                style = "dim"
            bar_text.append(char, style=style)
            
        # Info line
        info = Text()
        info.append(f"SoC: {soc:.1f}%", style="bold cyan")
        info.append(f" | Reserve: {reserve:.0f}%", style="dim")
        info.append(f" | Target: {target:.0f}%", style="dim")
        info.append(f" | Mode: {self.data.operating_mode}", style="yellow")
        
        content = Text.assemble(bar_text, "\n", info)
        
        return Panel(content, title="[bold]Battery State of Charge[/bold]", border_style="green", box=box.ROUNDED)
        
    def render_dc_power(self) -> Panel:
        """Render DC Power (Battery) panel."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style="cyan")
        table.add_column("Value", style="white", justify="right")
        table.add_column("Unit", style="dim")
        
        table.add_row("Power", f"{self.data.dc_power:,.0f}", "W")
        table.add_row("Current", f"{self.data.dc_current:.1f}", "A")
        table.add_row("SoC", f"{self.data.soc:.1f}", "%")
        table.add_row("SoH", f"{self.data.soh:.1f}", "%")
        table.add_row("Temperature", f"{self.data.battery_temp:.1f}", "°C")
        table.add_row("Available", f"{self.data.available_wh/1000:.1f}", "kWh")
        table.add_row("Rated", f"{self.data.rated_wh/1000:.1f}", "kWh")
        
        return Panel(table, title="[bold]DC Power (Battery)[/bold]", border_style="magenta", box=box.ROUNDED)
        
    def render_ac_power(self) -> Panel:
        """Render AC Power panel."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style="cyan")
        table.add_column("Value", style="white", justify="right")
        table.add_column("Unit", style="dim")
        
        table.add_row("Voltage", f"{self.data.ac_voltage:.1f}", "V")
        table.add_row("Current", f"{self.data.ac_current:.1f}", "A")
        table.add_row("Frequency", f"{self.data.ac_frequency:.2f}", "Hz")
        table.add_row("Power Factor", f"{self.data.ac_pf:.3f}", "")
        table.add_row("Apparent Power", f"{self.data.ac_va:.0f}", "VA")
        table.add_row("Reactive Power", f"{self.data.ac_var:.0f}", "VAR")
        table.add_row("Type", self.data.ac_type, "")
        
        return Panel(table, title=f"[bold]AC Power ({self.data.ac_type})[/bold]", border_style="yellow", box=box.ROUNDED)
        
    def render_solar(self) -> Panel:
        """Render Solar AC Inputs panel."""
        solar = self.data.solar
        
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Source", style="cyan")
        table.add_column("Power", style="white", justify="right")
        
        table.add_row("Total Solar", f"{solar.total_w:,.0f}W")
        table.add_row("├─ Proximal", f"{solar.proximal_w:,.0f}W")
        table.add_row("├─ Remote 1 (APbox)", f"{solar.remote1_w:,.0f}W")
        table.add_row("└─ Remote 2", f"{solar.remote2_w:,.0f}W")
        
        # Use a group instead of Text.assemble for mixed content
        from rich.console import Group
        note = Text("(Extension registers 15502-15505)", style="dim italic")
        content = Group(table, note)
        
        return Panel(content, title="[bold]Solar AC Inputs[/bold]", border_style="bright_yellow", box=box.ROUNDED)
        
    def render_lifetime(self) -> Panel:
        """Render Lifetime Energy panel."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Type", style="cyan")
        table.add_column("Energy", style="white", justify="right")
        
        table.add_row("Injected (to Grid)", f"{self.data.lifetime_injected/1e6:.2f} MWh")
        table.add_row("Absorbed (from Grid)", f"{self.data.lifetime_absorbed/1e6:.2f} MWh")
        table.add_row("Discharged", f"{self.data.lifetime_discharged/1e6:.2f} MWh")
        table.add_row("Charged", f"{self.data.lifetime_charged/1e6:.2f} MWh")
        table.add_row("Solar Generated", f"{self.data.lifetime_generated/1e6:.2f} MWh")
        
        return Panel(table, title="[bold]Lifetime Energy[/bold]", border_style="cyan", box=box.ROUNDED)
        
    def render_timeline(self) -> Optional[Panel]:
        """Render timeline sparkline (placeholder for Stage 6)."""
        # Will be implemented in Stage 6
        content = Text("Timeline chart coming in Stage 6", style="dim")
        return Panel(content, title="[bold]Power Timeline (60 min)[/bold]", border_style="blue", box=box.ROUNDED)
        
    def render_system_info(self) -> Panel:
        """Render System Info panel."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Model", self.data.model or "aGate X")
        table.add_row("Serial", self.data.serial or "Unknown")
        table.add_row("Firmware", self.data.firmware or "Unknown")
        table.add_row("Grid Connection", "Connected" if self.data.grid_connected else "Disconnected")
        table.add_row("Grid Mode", self.data.grid_mode)
        table.add_row("Cabinet Temp", f"{self.data.cabinet_temp:.1f}°C")
        table.add_row("Ambient Temp", f"{self.data.ambient_temp:.1f}°C")
        
        return Panel(table, title="[bold]Device Info[/bold]", border_style="white", box=box.ROUNDED)
        
    def render_alarms(self) -> Panel:
        """Render Alarms panel."""
        if self.data.active_alarms:
            content = Text("\n".join(f"⚠️  {alarm}" for alarm in self.data.active_alarms), style="red")
        else:
            content = Text("✓ No active alarms", style="green")
            
        if not self.data.extension_writable:
            content.append("\n⚠️  Extension: READ-ONLY (requires installer unlock)", style="yellow")
            
        return Panel(content, title="[bold]Alarms & Status[/bold]", border_style="red" if self.data.active_alarms else "green", box=box.ROUNDED)
        
    def render_footer(self) -> Panel:
        """Render footer with keyboard shortcuts or prompt."""
        if self.show_prompt and self.prompt_mode:
            # Show input prompt
            prompt_text = f"{self.prompt_mode.capitalize()} watts: {self.prompt_buffer}_"
            content = Text(prompt_text, style="bold yellow")
            content.append(" [Enter=send Esc=cancel]", style="dim")
            return Panel(content, box=box.SIMPLE, padding=(0, 1), border_style="yellow")
        else:
            # Show normal shortcuts - organized by function
            line1 = Text()
            line1.append("[c]", style="bold cyan")
            line1.append("=charge ", style="dim")
            line1.append("[d]", style="bold cyan")
            line1.append("=discharge ", style="dim")
            line1.append("[s]", style="bold cyan")
            line1.append("=standby(0W) ", style="dim")
            line1.append("[r]", style="bold cyan")
            line1.append("=release ", style="dim")
            line1.append("[q]", style="bold cyan")
            line1.append("=quit", style="dim")
            
            line2 = Text()
            line2.append("[m]", style="bold cyan")
            line2.append("=max▲ ", style="dim")
            line2.append("[M]", style="bold cyan")
            line2.append("=max▼ ", style="dim")
            line2.append("[+]", style="bold cyan")
            line2.append("=+100W ", style="dim")
            line2.append("[-]", style="bold cyan")
            line2.append("=-100W ", style="dim")
            line2.append("[R]", style="bold cyan")
            line2.append("=pause ", style="dim")
            line2.append("[1-9]", style="bold cyan")
            line2.append("=rate", style="dim")
            
            from rich.console import Group
            content = Group(line1, line2)
            
            return Panel(content, box=box.SIMPLE, padding=(0, 1))
        
    def update_display(self) -> Layout:
        """Update all panels and return the layout."""
        layout = self.create_layout()
        
        layout["header"].update(self.render_header())
        layout["footer"].update(self.render_footer())
        
        layout["power_flow"].update(self.render_power_flow())
        layout["soc_bar"].update(self.render_soc_bar())
        layout["dc_power"].update(self.render_dc_power())
        layout["ac_power"].update(self.render_ac_power())
        layout["solar"].update(self.render_solar())
        layout["lifetime"].update(self.render_lifetime())
        
        return layout
        
    def run_simple_mode(self):
        """Run in simple ANSI mode (no Rich)."""
        print("FranklinWH CLI Monitor - Simple Mode")
        print(f"Device: {self.config.ip_address}:{self.config.port}")
        print("-" * 60)
        print("Rich library not available. Install with: pip install rich")
        print("Or use: python -m pip install rich")
        print("-" * 60)
        print()
        print("Press Ctrl+C to exit")
        
        self.running = True
        try:
            while self.running:
                if not self.paused:
                    # Simple data fetch and display
                    self.fetch_data()
                    print(f"\rSoC: {self.data.soc:.1f}% | Power: {self.data.dc_power:.0f}W | "
                          f"Grid: {self.data.power_flow.grid_w:.0f}W | "
                          f"Solar: {self.data.solar.total_w:.0f}W", end="", flush=True)
                time.sleep(self.config.refresh_rate)
        except KeyboardInterrupt:
            pass
        finally:
            print("\n\nExiting...")
            self.disconnect()
            
    def _handle_key(self, key: str) -> bool:
        """Handle a single keypress. Returns False if should quit."""
        # Handle prompt mode (accumulating input)
        if self.show_prompt:
            return self._handle_prompt_key(key)
        
        # Normal mode - command shortcuts
        # Number keys 1-9 set refresh rate
        if key in '123456789':
            self.config.refresh_rate = int(key)
            return True
            
        # Quit keys
        if key in 'qQ\x03':  # q, Q, or Ctrl+C
            return False
            
        # Toggle refresh
        if key in 'R':
            self.paused = not self.paused
            return True
            
        # Standby
        if key == 's':
            self._send_command(0)
            return True
            
        # Reset control
        if key == 'r':
            if self.controller:
                self.controller.reset_control_state()
            return True
            
        # Max charge
        if key == 'm':
            if self.controller:
                self._send_command(self.controller.RATED_MAX_CHARGE_W)
            return True
            
        # Max discharge
        if key == 'M':
            if self.controller:
                self._send_command(-self.controller.RATED_MAX_DISCHARGE_W)
            return True
            
        # Increase/decrease power
        if key == '+':
            self._adjust_power(100)
            return True
        if key == '-':
            self._adjust_power(-100)
            return True
            
        # Charge mode - enter prompt mode
        if key == 'c':
            self.show_prompt = True
            self.prompt_mode = 'charge'
            self.prompt_buffer = ""
            return True
            
        # Discharge mode - enter prompt mode
        if key == 'd':
            self.show_prompt = True
            self.prompt_mode = 'discharge'
            self.prompt_buffer = ""
            return True
            
        return True
        
    def _handle_prompt_key(self, key: str) -> bool:
        """Handle key when in prompt mode."""
        # Enter - submit command
        if key in '\r\n':
            try:
                watts = int(self.prompt_buffer) if self.prompt_buffer else 0
                if self.prompt_mode == 'charge':
                    self._send_command(abs(watts))  # Positive = charge
                elif self.prompt_mode == 'discharge':
                    self._send_command(-abs(watts))  # Negative = discharge
            except ValueError:
                pass  # Invalid input, ignore
            # Exit prompt mode
            self.show_prompt = False
            self.prompt_buffer = ""
            self.prompt_mode = None
            return True
            
        # Escape or Ctrl+C - cancel prompt
        if key in '\x1b\x03':  # Escape or Ctrl+C
            self.show_prompt = False
            self.prompt_buffer = ""
            self.prompt_mode = None
            return True
            
        # Backspace
        if key in '\x7f\b':  # DEL or Backspace
            self.prompt_buffer = self.prompt_buffer[:-1]
            return True
            
        # Digits
        if key.isdigit():
            self.prompt_buffer += key
            return True
            
        return True
        
    def _send_command(self, power_w: int):
        """Send power command to battery."""
        if not self.controller:
            return
        try:
            from .types import BatteryCommand
            cmd = BatteryCommand(power_watts=power_w)
            self.controller.send_command(cmd)
            self.current_power = power_w
        except Exception as e:
            pass
            
    def _adjust_power(self, delta: int):
        """Adjust current power by delta."""
        new_power = self.current_power + delta
        self._send_command(new_power)
        
    def run(self):
        """Run the monitor with Rich."""
        if not HAS_RICH or not self.config.use_rich:
            return self.run_simple_mode()
            
        if not self.connect():
            return 1
            
        self.running = True
        self.input_handler.start()
        
        try:
            with Live(
                self.update_display(),
                console=self.console,
                screen=True,
                refresh_per_second=1/self.config.refresh_rate
            ) as live:
                while self.running:
                    # Check for keyboard input
                    key = self.input_handler.get_key()
                    if key is not None:
                        if not self._handle_key(key):
                            break
                            
                    if not self.paused:
                        self.fetch_data()
                        live.update(self.update_display())
                    time.sleep(0.1)  # Short sleep for responsive input
                    
        except KeyboardInterrupt:
            pass
        finally:
            self.input_handler.stop()
            self.disconnect()
            
        return 0


def main():
    """Main entry point for standalone monitor."""
    import argparse
    
    parser = argparse.ArgumentParser(description="FranklinWH CLI Monitor")
    parser.add_argument("-i", "--ip", required=True, help="aGate IP address")
    parser.add_argument("-p", "--port", type=int, default=502, help="Modbus port")
    parser.add_argument("-u", "--unit", type=int, default=2, help="Modbus unit ID")
    parser.add_argument("-r", "--refresh", type=float, default=5.0, help="Refresh rate (seconds)")
    parser.add_argument("--no-rich", action="store_true", help="Use simple ANSI mode")
    parser.add_argument("--theme", default="dark", choices=["dark", "light"], help="Color theme")
    
    args = parser.parse_args()
    
    config = MonitorConfig(
        ip_address=args.ip,
        port=args.port,
        unit_id=args.unit,
        refresh_rate=args.refresh,
        use_rich=not args.no_rich,
        theme=args.theme
    )
    
    monitor = CLIMonitor(config)
    return monitor.run()


if __name__ == "__main__":
    sys.exit(main())

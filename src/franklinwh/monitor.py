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
from .models import BatteryCommand, ControlMode


@dataclass
class MonitorConfig:
    """Configuration for the monitor."""
    ip_address: str
    port: int = 502
    unit_id: int = 2
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
                host=self.config.ip_address,
                port=self.config.port,
                unit_id=self.config.unit_id
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
            
    def fetch_data(self) -> bool:
        """Fetch all data from the device."""
        if not self.controller:
            return False
            
        try:
            # This will be implemented in Stage 2
            # For now, return True to allow layout testing
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
        
        note = Text("(Extension registers 15502-15505)", style="dim italic")
        
        content = Text.assemble(table, "\n", note)
        
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
        """Render footer with keyboard shortcuts."""
        shortcuts = [
            ("[c]", "charge"),
            ("[d]", "discharge"),
            ("[s]", "standby"),
            ("[+]", "+100W"),
            ("[-]", "-100W"),
            ("[m]", "max charge"),
            ("[M]", "max discharge"),
            ("[r]", "reset"),
            ("[R]", "toggle refresh"),
            ("[q]", "quit")
        ]
        
        content = Text()
        for key, action in shortcuts:
            content.append(f"{key}", style="bold cyan")
            content.append(f"={action} ", style="dim")
            
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
            
    def run(self):
        """Run the monitor with Rich."""
        if not HAS_RICH or not self.config.use_rich:
            return self.run_simple_mode()
            
        if not self.connect():
            return 1
            
        self.running = True
        
        try:
            with Live(
                self.update_display(),
                console=self.console,
                screen=True,
                refresh_per_second=1/self.config.refresh_rate
            ) as live:
                while self.running:
                    if not self.paused:
                        self.fetch_data()
                        live.update(self.update_display())
                    time.sleep(self.config.refresh_rate)
                    
        except KeyboardInterrupt:
            pass
        finally:
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

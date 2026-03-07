"""
FastAPI web server for the FranklinWH Battery Manager.
Provides REST API endpoints for the web interface and WebSocket support for real-time updates.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING
from dataclasses import asdict

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# Import components
from src.models import BatteryMode

if TYPE_CHECKING:
    from src.config_manager import ConfigManager, DeviceConfig
    from src.mqtt_handler import HomeAssistantMQTTBridge
    from src.modbus_client import FranklinWHModbusClient
    from src.connection_manager import ConnectionManager

try:
    from src.config_manager import ConfigManager, DeviceConfig
    from src.mqtt_handler import HomeAssistantMQTTBridge
    from src.modbus_client import FranklinWHModbusClient
    from src.connection_manager import ConnectionManager
except ImportError:
    # Allow importing for type checking even if deps not available
    ConfigManager = None
    DeviceConfig = None
    HomeAssistantMQTTBridge = None
    FranklinWHModbusClient = None
    ConnectionManager = None

logger = logging.getLogger(__name__)

# Request/Response models
class ModbusConfigRequest(BaseModel):
    host: str
    port: int
    unit_id: int
    base_address: int = 40000
    timeout: float = 5.0


class MQTTConfigRequest(BaseModel):
    # Broker settings
    host: Optional[str] = None
    port: Optional[int] = 1883
    username: Optional[str] = ""
    password: Optional[str] = ""
    client_id: Optional[str] = "franklinwh_bridge"
    enabled: Optional[bool] = False
    qos: Optional[int] = 0
    
    # Site configuration
    site_name: Optional[str] = "Home"
    site_id: Optional[str] = "default"
    site_description: Optional[str] = ""
    is_remote_site: Optional[bool] = False
    
    # HA Discovery settings
    discovery_prefix: Optional[str] = "homeassistant"
    state_prefix: Optional[str] = "franklinwh"
    ha_device_name: Optional[str] = ""  # Empty = use SunSpec Model
    unique_id_prefix: Optional[str] = "franklinwh"
    retain_discovery: Optional[bool] = True
    
    # Device selection
    publish_device_ids: Optional[List[str]] = None
    publish_devices: Optional[Dict[str, bool]] = None
    
    # Entity selection
    publish_battery: Optional[bool] = True
    publish_inverter: Optional[bool] = True
    publish_solar: Optional[bool] = True
    publish_home_loads: Optional[bool] = True
    publish_capacity: Optional[bool] = True
    publish_controls: Optional[bool] = True


class ThemeConfigRequest(BaseModel):
    primary_color: str = "#3b82f6"
    secondary_color: str = "#10b981"
    accent_color: str = "#f59e0b"
    mode: str = "auto"


class WidgetConfigRequest(BaseModel):
    enabled: bool = True
    position: int = 0
    color: str = "#3b82f6"
    expanded: bool = True


class SiteConfigRequest(BaseModel):
    id: str
    name: str
    description: str = ""
    is_local: bool = True

class SettingsRequest(BaseModel):
    modbus: Optional[ModbusConfigRequest] = None
    mqtt: Optional[MQTTConfigRequest] = None
    theme: Optional[ThemeConfigRequest] = None
    auto_refresh: Optional[bool] = None
    refresh_interval: Optional[int] = None
    widgets: Optional[Dict[str, WidgetConfigRequest]] = None
    sites: Optional[List[SiteConfigRequest]] = None
    log_level: Optional[str] = None
    log_retention_days: Optional[int] = None


class ModeRequest(BaseModel):
    mode: int


class ReserveRequest(BaseModel):
    value: int
    type: str = "self_consumption"  # "self_consumption" or "tou"


class PowerLimitRequest(BaseModel):
    max_charge_kw: float
    max_discharge_kw: float


class ForcePowerRequest(BaseModel):
    power_watts: int  # Positive=charge, Negative=discharge, 0=idle


class TopologyRequest(BaseModel):
    id: str
    name: str
    host: str
    port: int = 502
    unit_id: int = 1
    base_address: int = 40001
    timeout: int = 3
    enabled: bool = True
    description: str = ""

class DeviceEditRequest(BaseModel):
    name: str
    description: str = ""

class RawRegisterRequest(BaseModel):
    start_address: int
    count: int = 41
    device_id: Optional[str] = None


class WriteRegisterRequest(BaseModel):
    address: int
    value: int
    data_type: str = "uint16"  # uint16, int16, uint32, int32, float32
    device_id: Optional[str] = None


class SunSpecWriteRequest(BaseModel):
    model_id: int
    point_name: str
    value: Any
    dry_run: bool = False  # Validate only, don't actually write
    acknowledge_danger: bool = False  # User acknowledges the risk
    device_id: Optional[str] = None


class SunSpecBatchWriteRequest(BaseModel):
    points: List[Dict[str, Any]]  # List of {model_id, point_name, value}
    dry_run: bool = False
    acknowledge_danger: bool = False
    device_id: Optional[str] = None


class SunSpecPointRequest(BaseModel):
    point: str  # Format: "model_id.point_name" (e.g., "1.Mn")
    verbose: bool = False
    device_id: Optional[str] = None


class SunSpecRawRequest(BaseModel):
    raw: str  # Format: "start:count" (e.g., "15500:14")
    nz: bool = False  # Only non-zero values
    match: bool = False  # Try to match with known models
    verbose: bool = False
    device_id: Optional[str] = None


def create_app(
    connection_manager: ConnectionManager,
    mqtt_bridge: Optional[HomeAssistantMQTTBridge],
    config_manager: ConfigManager,
    mock_mode: bool = False,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Application lifespan manager."""
        logger.info("Web server starting up...")
        
        # Initialize connections from config
        config = config_manager.get()
        await connection_manager.initialize_from_config(config.devices)
        
        yield
        
        logger.info("Web server shutting down...")
        connection_manager.close_all()
    
    app = FastAPI(
        title="FranklinWH Battery Manager",
        description="Web interface for managing FranklinWH battery systems",
        version="1.0.0",
        lifespan=lifespan,
    )
    
    # Store mode indicator
    app.state.mock_mode = mock_mode
    
    # Store references
    app.state.connection_manager = connection_manager
    app.state.mqtt = mqtt_bridge
    app.state.config = config_manager
    
    # Active WebSocket connections
    app.state.websockets: list[WebSocket] = []
    
    # Mount static files
    # Check if static directory exists, if not create it
    static_path = Path("static")
    if not static_path.exists():
        static_path.mkdir()
        
    app.mount("/static", StaticFiles(directory="static"), name="static")
    
    # Jinja2 Templates
    templates = Jinja2Templates(directory="templates")
    
    @app.get("/", response_class=HTMLResponse)
    async def get_dashboard(request: Request):
        return templates.TemplateResponse("dashboard.html", {"request": request})
    
    @app.get("/topology", response_class=HTMLResponse)
    async def get_topology_page(request: Request):
        return templates.TemplateResponse("topology.html", {"request": request})

    @app.get("/diagnostics", response_class=HTMLResponse)
    async def get_diagnostics_page(request: Request):
        """Diagnostics dashboard for data source mapping and MQTT monitoring."""
        return templates.TemplateResponse("diagnostics.html", {"request": request})

    @app.get("/api/health")
    async def health(device_id: Optional[str] = None):
        """Health check endpoint with MQTT status and network quality."""
        modbus = await app.state.connection_manager.get_client(device_id)
        mqtt = app.state.mqtt
        
        mqtt_status = {
            "enabled": mqtt.is_enabled if mqtt else False,
            "status": mqtt.status.value if mqtt else "unknown",
            "connected": mqtt.is_connected if mqtt else False,
            "broker": f"{mqtt.broker_host}:{mqtt.broker_port}" if mqtt else None,
        } if mqtt else None
        
        # Get network health if available
        network_health = None
        if hasattr(app.state, 'network_monitor') and app.state.network_monitor:
            monitor = app.state.network_monitor
            stats = monitor.last_stats
            if stats:
                network_health = {
                    "quality": stats.quality.value,
                    "packet_loss": stats.packet_loss,
                    "avg_latency_ms": stats.avg_ms,
                    "max_latency_ms": stats.max_ms,
                    "jitter_ms": stats.mdev_ms,
                }
        
        return {
            "status": "ok",
            "mock_mode": getattr(app.state, 'mock_mode', False),
            "modbus_connected": modbus._connected if modbus else False,
            "mqtt": mqtt_status,
            "network": network_health,
        }
    
    @app.get("/api/diagnostics/data_sources")
    async def get_data_source_mapping(device_id: Optional[str] = None):
        """Get data source mapping for all sensors (Modbus → API → MQTT)."""
        import time
        modbus = await app.state.connection_manager.get_client(device_id)
        mqtt = app.state.mqtt
        
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        # Get current data
        data = await modbus.read_all()
        
        # Build sensor mapping
        sensors = [
            # Grid Power
            {
                "display_name": "Grid Power",
                "modbus_source": "Model 701.W",
                "modbus_register": "40001+ (AC Power)",
                "api_field": "inverter.power",
                "mqtt_topic": "inverter/power",
                "current_value": data.get("inverter_ac", {}).power_w if data.get("inverter_ac") else None,
                "unit": "W",
                "status": "live" if data.get("inverter_ac", {}).power_w is not None else "no_data",
                "entity_id": "sensor.agate_x_0091_power",
            },
            # Battery Power (DC)
            {
                "display_name": "Battery Power",
                "modbus_source": "Model 714.DCW",
                "modbus_register": "40100+ (DC Power)",
                "api_field": "battery.power",
                "mqtt_topic": "battery/power",
                "current_value": data.get("battery", {}).dc_power_w if data.get("battery") else None,
                "unit": "W",
                "status": "live" if data.get("battery", {}).dc_power_w is not None else "no_data",
                "entity_id": "sensor.franklinwh_agate_x_0091_battery_power",
            },
            # Battery SOC
            {
                "display_name": "State of Charge",
                "modbus_source": "Model 713.SoC",
                "modbus_register": "40080+ (Battery SOC)",
                "api_field": "battery.soc",
                "mqtt_topic": "battery/soc",
                "current_value": data.get("battery", {}).state_of_charge_percent if data.get("battery") else None,
                "unit": "%",
                "status": "live" if data.get("battery", {}).state_of_charge_percent is not None else "no_data",
                "entity_id": "sensor.agate_x_0091_state_of_charge",
            },
            # Battery Temperature
            {
                "display_name": "Battery Temperature",
                "modbus_source": "Model 714.Tmp",
                "modbus_register": "40100+ (Temperature)",
                "api_field": "battery.temperature",
                "mqtt_topic": "battery/temperature",
                "current_value": data.get("battery", {}).temperature_c if data.get("battery") else None,
                "unit": "°C",
                "status": "no_data" if data.get("battery", {}).temperature_c is None else "live",
                "reason": "Hardware does not provide" if data.get("battery", {}).temperature_c is None else None,
                "entity_category": "diagnostic",
                "entity_id": "sensor.agate_x_0091_battery_temperature",
            },
            # Cycle Count
            {
                "display_name": "Cycle Count",
                "modbus_source": "Model 714.NCyc",
                "modbus_register": "40100+",
                "api_field": "battery.cycles",
                "mqtt_topic": "battery/cycles",
                "current_value": data.get("battery", {}).cycle_count if data.get("battery") else None,
                "unit": "cycles",
                "status": "no_data" if data.get("battery", {}).cycle_count is None else "live",
                "reason": "Hardware does not provide" if data.get("battery", {}).cycle_count is None else None,
                "entity_category": "diagnostic",
                "entity_id": "sensor.agate_x_0091_cycle_count",
            },
            # Home Loads
            {
                "display_name": "Home Loads",
                "modbus_source": "Register 15506",
                "modbus_register": "15506 (FranklinWH Extension)",
                "api_field": "home_loads.home_loads_w",
                "mqtt_topic": "home_loads/home_loads_w",
                "current_value": data.get("home_loads", {}).home_loads_w if data.get("home_loads") else None,
                "unit": "W",
                "status": "live" if data.get("home_loads", {}).home_loads_w is not None else "no_data",
                "entity_id": "sensor.agate_x_0091_home_loads",
            },
            # Solar Power
            {
                "display_name": "Solar Power",
                "modbus_source": "Model 704.W",
                "modbus_register": "40120+ (PV Power)",
                "api_field": "solar_pv.output_power_w",
                "mqtt_topic": "solar/output_power",
                "current_value": data.get("solar_pv", {}).output_power_w if data.get("solar_pv") else None,
                "unit": "W",
                "status": "live" if data.get("solar_pv", {}).output_power_w is not None else "no_data",
                "entity_id": "sensor.agate_x_0091_solar_power",
            },
            # Max Charge Power
            {
                "display_name": "Max Charge Power",
                "modbus_source": "Model 702.WChaRteMaxRtg",
                "modbus_register": "40235 (DERCapacity)",
                "api_field": "capacity.max_charge_w",
                "mqtt_topic": "capacity/max_charge_w",
                "current_value": data.get("capacity", {}).max_charge_w if data.get("capacity") else None,
                "unit": "W",
                "status": "no_data" if not data.get("capacity", {}).max_charge_w else "live",
                "reason": "Model 702 not populated" if not data.get("capacity", {}).max_charge_w else None,
                "entity_category": "diagnostic",
                "entity_id": "sensor.agate_x_0091_max_charge_power",
            },
            # Max Discharge Power
            {
                "display_name": "Max Discharge Power",
                "modbus_source": "Model 702.WDisChaRteMaxRtg",
                "modbus_register": "40236 (DERCapacity)",
                "api_field": "capacity.max_discharge_w",
                "mqtt_topic": "capacity/max_discharge_w",
                "current_value": data.get("capacity", {}).max_discharge_w if data.get("capacity") else None,
                "unit": "W",
                "status": "no_data" if not data.get("capacity", {}).max_discharge_w else "live",
                "reason": "Model 702 not populated" if not data.get("capacity", {}).max_discharge_w else None,
                "entity_category": "diagnostic",
                "entity_id": "sensor.agate_x_0091_max_discharge_power",
            },
        ]
        
        # Add MQTT status
        mqtt_info = {
            "connected": mqtt.is_connected if mqtt else False,
            "broker": f"{mqtt.broker_host}:{mqtt.broker_port}" if mqtt else None,
            "stats": mqtt.get_stats() if mqtt and mqtt.is_connected else None,
        }
        
        return {
            "sensors": sensors,
            "mqtt": mqtt_info,
            "timestamp": time.time(),
        }
    
    @app.get("/api/data")
    async def get_data(device_id: Optional[str] = None):
        """Get current battery and inverter data."""
        modbus = await app.state.connection_manager.get_client(device_id)
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        try:
            data = await modbus.read_all()
            
            # Get extensions data if available
            # FranklinWH Extension Registers (non-SunSpec):
            # 15507: Operating Mode (1=Backup, 2=Self-Consumption, 3=TOU)
            # 15508: Reserve SOC - Self-Consumption mode reserve
            # 15509: Reserve SOC 2 - TOU mode reserve
            extensions_data = None
            try:
                from src.modbus_client_franklinwh import FranklinWHRegisterMap
                register_map = FranklinWHRegisterMap(modbus)
                metrics = await register_map.read_all_metrics()
                mode_text = await register_map.get_operating_mode_text(metrics.operating_mode)
                
                # Get extended status including TOU dispatch (if applicable)
                extended_status = await register_map.get_extended_status()
                
                # Normalize reserveSoc2 (handle unsigned int16 -> signed int8 conversion)
                reserve_soc_2_normalized = metrics.reserve_soc_2
                if reserve_soc_2_normalized is not None and reserve_soc_2_normalized > 32767:
                    reserve_soc_2_normalized = reserve_soc_2_normalized - 65536
                
                extensions_data = {
                    # SunSpec2-aligned naming (camelCase)
                    "operatingMode": metrics.operating_mode,
                    "modeText": mode_text,
                    "reserveSoc": metrics.reserve_soc,  # Register 15508
                    "reserveSoc2": reserve_soc_2_normalized,  # Register 15509
                    
                    # Snake_case aliases for API consistency
                    "operating_mode": metrics.operating_mode,
                    "mode_text": mode_text,
                    "reserve_soc": metrics.reserve_soc,
                    "reserve_soc_2": reserve_soc_2_normalized,
                    
                    # Human-readable aliases
                    "reserve_soc_self_consumption": metrics.reserve_soc,
                    "reserve_soc_tou": reserve_soc_2_normalized,
                    
                    # TOU Dispatch State (FranklinWH-specific, non-SunSpec)
                    "tou_dispatch": extended_status.get("tou_dispatch"),
                    "effective_state": extended_status.get("effective_state"),
                    "effective_state_detail": extended_status.get("effective_state_detail"),
                    
                    # Traceability: Register addresses
                    "_meta": {
                        "operating_mode_register": 15507,
                        "reserve_soc_register": 15508,
                        "reserve_soc_2_register": 15509,
                        "tou_dispatch_register": 15516,
                        "source": "franklinwh_extensions"
                    }
                }
            except Exception as e:
                logger.debug(f"Extensions not available: {e}")
                pass  # Extensions are optional
            
            return {
                "timestamp": asyncio.get_event_loop().time(),
                "device_info": {
                    "manufacturer": data.get("device_info", {}).manufacturer if data.get("device_info") else "Unknown",
                    "model": data.get("device_info", {}).model if data.get("device_info") else "Unknown",
                    "serial": data.get("device_info", {}).serial_number if data.get("device_info") else "Unknown",
                } if data.get("device_info") else None,
                "battery": {
                    "soc": data.get("battery", {}).state_of_charge_percent if data.get("battery") else None,
                    "soh": data.get("battery", {}).state_of_health_percent if data.get("battery") else None,
                    "temperature": data.get("battery", {}).temperature_c if data.get("battery") else None,
                    "cycles": data.get("battery", {}).cycle_count if data.get("battery") else None,
                    "rated_energy_wh": data.get("battery", {}).rated_energy_wh if data.get("battery") else None,
                    "available_energy_wh": data.get("battery", {}).available_energy_wh if data.get("battery") else None,
                    "status": data.get("battery", {}).status if data.get("battery") else None,
                    "status_text": data.get("battery", {}).status_text if data.get("battery") else None,
                    "power": data.get("battery", {}).dc_power_w if data.get("battery") else None,  # Model 714.DCW
                } if data.get("battery") else None,
                "inverter": {
                    # Power measurements
                    "power": data.get("inverter_ac", {}).power_w if data.get("inverter_ac") else None,
                    "voltage": data.get("inverter_ac", {}).voltage_v if data.get("inverter_ac") else None,
                    "current": data.get("inverter_ac", {}).current_a if data.get("inverter_ac") else None,
                    "frequency": data.get("inverter_ac", {}).frequency_hz if data.get("inverter_ac") else None,
                    "apparent_power_va": data.get("inverter_ac", {}).apparent_power_va if data.get("inverter_ac") else None,
                    "reactive_power_var": data.get("inverter_ac", {}).reactive_power_var if data.get("inverter_ac") else None,
                    "power_factor": data.get("inverter_ac", {}).power_factor if data.get("inverter_ac") else None,
                    # Status and wiring (Model 701)
                    "ac_type": data.get("inverter_ac", {}).ac_type if data.get("inverter_ac") else None,
                    "ac_type_text": data.get("inverter_ac", {}).ac_type_text if data.get("inverter_ac") else "Unknown",
                    "operating_state": data.get("inverter_ac", {}).operating_state if data.get("inverter_ac") else None,
                    "operating_state_text": data.get("inverter_ac", {}).operating_state_text if data.get("inverter_ac") else "Unknown",
                    "inverter_state": data.get("inverter_ac", {}).inverter_state if data.get("inverter_ac") else None,
                    "inverter_state_text": data.get("inverter_ac", {}).inverter_state_text if data.get("inverter_ac") else "Unknown",
                    "grid_connection_state": data.get("inverter_ac", {}).grid_connection_state if data.get("inverter_ac") else None,
                    "grid_connection_state_text": data.get("inverter_ac", {}).grid_connection_state_text if data.get("inverter_ac") else "Unknown",
                    "alarm": data.get("inverter_ac", {}).alarm if data.get("inverter_ac") else None,
                    "alarm_text": data.get("inverter_ac", {}).alarm_text if data.get("inverter_ac") else None,
                    "der_mode": data.get("inverter_ac", {}).der_mode if data.get("inverter_ac") else None,
                    "der_mode_text": data.get("inverter_ac", {}).der_mode_text if data.get("inverter_ac") else None,
                    # Temperatures
                    "ambient_temperature_c": data.get("inverter_ac", {}).ambient_temperature_c if data.get("inverter_ac") else None,
                    "cabinet_temperature_c": data.get("inverter_ac", {}).cabinet_temperature_c if data.get("inverter_ac") else None,
                    # Lifetime energy
                    "total_energy_injected_wh": data.get("inverter_ac", {}).total_energy_injected_wh if data.get("inverter_ac") else None,
                    "total_energy_absorbed_wh": data.get("inverter_ac", {}).total_energy_absorbed_wh if data.get("inverter_ac") else None,
                } if data.get("inverter_ac") else None,
                "capacity": {
                    "max_charge_w": data.get("capacity", {}).max_charge_w if data.get("capacity") else 5000,
                    "max_discharge_w": data.get("capacity", {}).max_discharge_w if data.get("capacity") else 5000,
                } if data.get("capacity") else {
                    # Default rated capacity for FranklinWH aGate
                    "max_charge_w": 5000,
                    "max_discharge_w": 5000,
                },
                "battery_lifetime": {
                    "dc_energy_injected_wh": data.get("battery", {}).dc_energy_injected_wh if data.get("battery") else None,
                    "dc_energy_absorbed_wh": data.get("battery", {}).dc_energy_absorbed_wh if data.get("battery") else None,
                } if data.get("battery") else None,
                "solar_pv": {
                    "output_power_w": data.get("solar_pv", {}).output_power_w if data.get("solar_pv") else None,
                    "output_energy_wh": data.get("solar_pv", {}).output_energy_wh if data.get("solar_pv") else None,
                } if data.get("solar_pv") else None,
                "home_loads": {
                    "home_loads_w": data.get("home_loads", {}).home_loads_w if data.get("home_loads") else None,
                    "pv_output_w": data.get("home_loads", {}).pv_output_w if data.get("home_loads") else None,
                    "pv_proximal_w": data.get("home_loads", {}).pv_proximal_w if data.get("home_loads") else None,
                } if data.get("home_loads") else None,
                "extensions": extensions_data,
            }
        except Exception as e:
            logger.error(f"Error reading data: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/extensions")
    async def get_extensions(device_id: Optional[str] = None):
        """Get FranklinWH extension register values."""
        modbus = await app.state.connection_manager.get_client(device_id)
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        try:
            from src.modbus_client_franklinwh import FranklinWHRegisterMap
            register_map = FranklinWHRegisterMap(modbus)
            metrics = await register_map.read_all_metrics()
            
            mode_text = await register_map.get_operating_mode_text(metrics.operating_mode)
            
            # Normalize reserveSoc2 (handle unsigned int16 -> signed int8 conversion)
            reserve_soc_2_normalized = metrics.reserve_soc_2
            if reserve_soc_2_normalized is not None and reserve_soc_2_normalized > 32767:
                reserve_soc_2_normalized = reserve_soc_2_normalized - 65536
            
            return {
                # SunSpec2-aligned naming (camelCase) - Primary
                "operatingMode": metrics.operating_mode,
                "modeText": mode_text,
                "reserveSoc": metrics.reserve_soc,  # Register 15508
                "reserveSoc2": reserve_soc_2_normalized,  # Register 15509
                
                # Structured operating mode
                "operating_mode": {
                    "raw": metrics.operating_mode,
                    "text": mode_text,
                },
                
                # Snake_case aliases for API consistency
                "mode_text": mode_text,
                "reserve_soc": metrics.reserve_soc,
                "reserve_soc_2": reserve_soc_2_normalized,
                
                # Human-readable aliases
                "reserve_soc_self_consumption": metrics.reserve_soc,
                "reserve_soc_tou": reserve_soc_2_normalized,
                
                # Raw register values (for debugging)
                "soc_raw": metrics.soc_raw,
                "soh_raw": metrics.soh_raw,
                "power_raw": metrics.power_raw,
                "voltage_raw": metrics.voltage_raw,
                "current_raw": metrics.current_raw,
                "status_flags": metrics.status_flags,
                
                # Traceability metadata
                "_meta": {
                    "operating_mode_register": 15507,
                    "reserve_soc_register": 15508,
                    "reserve_soc_2_register": 15509,
                    "source": "franklinwh_extensions"
                }
            }
        except Exception as e:
            logger.error(f"Error reading extensions: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/solar")
    async def get_solar(device_id: Optional[str] = None):
        """Get Solar PV data (Model 502)."""
        modbus = await app.state.connection_manager.get_client(device_id)
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        try:
            metrics = await modbus.get_solar_pv_metrics()
            return {
                "output_power_w": metrics.output_power_w if metrics else None,
                "output_energy_wh": metrics.output_energy_wh if metrics else None,
                "output_energy_kwh": round(metrics.output_energy_wh / 1000, 1) if metrics and metrics.output_energy_wh else None,
            }
        except Exception as e:
            logger.error(f"Error reading solar data: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/home-loads")
    async def get_home_loads(device_id: Optional[str] = None):
        """Get Home Load data (FranklinWH extension registers)."""
        modbus = await app.state.connection_manager.get_client(device_id)
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        try:
            metrics = await modbus.get_home_load_metrics()
            return {
                "home_loads_w": metrics.home_loads_w if metrics else None,
                "pv_output_w": metrics.pv_output_w if metrics else None,
                "pv_proximal_w": metrics.pv_proximal_w if metrics else None,
            }
        except Exception as e:
            logger.error(f"Error reading home load data: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/battery-lifetime")
    async def get_battery_lifetime(device_id: Optional[str] = None):
        """Get Battery Lifetime Energy data (Model 714)."""
        modbus = await app.state.connection_manager.get_client(device_id)
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        try:
            metrics = await modbus.get_battery_metrics()
            return {
                "dc_energy_injected_wh": metrics.dc_energy_injected_wh if metrics else None,
                "dc_energy_absorbed_wh": metrics.dc_energy_absorbed_wh if metrics else None,
                "dc_energy_injected_kwh": round(metrics.dc_energy_injected_wh / 1000, 1) if metrics and metrics.dc_energy_injected_wh else None,
                "dc_energy_absorbed_kwh": round(metrics.dc_energy_absorbed_wh / 1000, 1) if metrics and metrics.dc_energy_absorbed_wh else None,
                "total_throughput_kwh": round((metrics.dc_energy_injected_wh + metrics.dc_energy_absorbed_wh) / 1000, 1) if metrics and metrics.dc_energy_injected_wh and metrics.dc_energy_absorbed_wh else None,
            }
        except Exception as e:
            logger.error(f"Error reading battery lifetime data: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/mode")
    async def set_mode(request: ModeRequest, device_id: Optional[str] = None):
        """Set battery operating mode (FranklinWH extension register 15507).
        
        Mode values:
        0 = Standby
        1 = Backup Reserve
        2 = Self-Consumption
        3 = Time-of-Use
        4 = Normal
        """
        modbus = await app.state.connection_manager.get_client(device_id)
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        try:
            # Validate mode range
            if request.mode < 0 or request.mode > 4:
                raise HTTPException(status_code=400, detail=f"Invalid mode {request.mode}. Must be 0-4.")
            
            # Use the extension method which supports the 5 FranklinWH modes
            from src.modbus_client_franklinwh import FranklinWHRegisterMap
            register_map = FranklinWHRegisterMap(modbus)
            success = await register_map.set_operating_mode(request.mode)
            
            if success:
                return {"success": True, "mode": request.mode}
            else:
                raise HTTPException(status_code=400, detail="Failed to set mode")
        except Exception as e:
            logger.error(f"Error setting mode: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/reserve")
    async def set_reserve(request: ReserveRequest, device_id: Optional[str] = None):
        """Set reserve SOC (self-consumption or TOU)."""
        modbus = await app.state.connection_manager.get_client(device_id)
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        try:
            from src.modbus_client_franklinwh import FranklinWHRegisterMap
            register_map = FranklinWHRegisterMap(modbus)
            
            if request.type == "tou":
                success = await register_map.set_reserve_soc_2(request.value)
                label = "reserve_soc_2"
            else:
                success = await register_map.set_reserve_soc(request.value)
                label = "reserve_soc"
            
            if success:
                return {"success": True, label: request.value}
            else:
                raise HTTPException(status_code=400, detail=f"Failed to set {label}")
        except Exception as e:
            logger.error(f"Error setting reserve: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/reserve2")
    async def set_reserve2(request: ReserveRequest, device_id: Optional[str] = None):
        """Set reserve SOC 2."""
        modbus = await app.state.connection_manager.get_client(device_id)
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        try:
            from src.modbus_client_franklinwh import FranklinWHRegisterMap
            register_map = FranklinWHRegisterMap(modbus)
            success = await register_map.set_reserve_soc_2(request.value)
            
            if success:
                return {"success": True, "reserve_soc_2": request.value}
            else:
                raise HTTPException(status_code=400, detail="Failed to set reserve 2")
        except Exception as e:
            logger.error(f"Error setting reserve 2: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/control_status")
    async def get_control_status(device_id: Optional[str] = None):
        """Get control status including Local/Remote mode and write permissions."""
        modbus = await app.state.connection_manager.get_client(device_id)
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        try:
            # Try to read from SunSpec Model 714 (DER Storage Status) - has LocRemCtl (Local Remote Control)
            status_model = await modbus.read_model(714)
            loc_rem_ctl = None
            
            if status_model:
                try:
                    loc_rem_ctl = status_model.LocRemCtl.value if hasattr(status_model, 'LocRemCtl') else None
                except:
                    pass
            
            # If we couldn't read LocRemCtl, try to determine from extension registers
            if loc_rem_ctl is None:
                # Read register 15500 which may contain local/remote status
                # This is FranklinWH-specific
                pass
            
            # Also test write permission
            can_write = False
            write_message = "Unknown"
            
            try:
                # Quick write test on ChaGriSet
                model_715 = await modbus.read_model(715, force=True)
                if model_715:
                    try:
                        current_val = model_715.ChaGriSet.value if hasattr(model_715, 'ChaGriSet') else None
                        if current_val is not None:
                            can_write = await modbus._write_point(model_715, 'ChaGriSet', current_val)
                            write_message = "Write test passed" if can_write else "Write test failed"
                    except:
                        pass
            except Exception as e:
                write_message = f"Write test error: {str(e)}"
            
            # Interpret LocRemCtl
            # 0 = Local, 1 = Remote, 2 = Both (per SunSpec)
            control_mode = "Unknown"
            if loc_rem_ctl == 0:
                control_mode = "Local"
            elif loc_rem_ctl == 1:
                control_mode = "Remote"
            elif loc_rem_ctl == 2:
                control_mode = "Both"
            
            # Infer mode from write test if SunSpec LocRemCtl not available
            if loc_rem_ctl is None:
                if can_write:
                    control_mode = "Remote (inferred)"
                else:
                    control_mode = "Local (inferred)"
            
            # Build message based on what we found
            if can_write:
                message = f"aGate is in {control_mode} mode. Write test passed."
            else:
                if "Local" in control_mode:
                    message = f"aGate appears to be in LOCAL mode. SPAN Panel Modbus may need to be enabled by your installer."
                else:
                    message = f"aGate is in {control_mode} mode but writes are blocked. Check SPAN Panel Modbus setting."
            
            return {
                "success": True,
                "control_mode": control_mode,
                "loc_rem_ctl": loc_rem_ctl,
                "can_write": can_write,
                "write_test_message": write_message,
                "message": message,
                "warning": not can_write
            }
            
        except Exception as e:
            logger.error(f"Error getting control status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/test_write_permission")
    async def test_write_permission(device_id: Optional[str] = None):
        """Test if we have write permission by writing ChaGriSet (Grid Charge Enable) back to itself."""
        modbus = await app.state.connection_manager.get_client(device_id)
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        try:
            # Read Model 715 (DER Storage Controls)
            model = await modbus.read_model(715, force=True)
            if model is None:
                raise HTTPException(status_code=503, detail="Model 715 not available")
            
            # Get current ChaGriSet value (Grid Charge Enable)
            try:
                current_value = model.ChaGriSet.value
            except AttributeError:
                # Fallback: try reading as point
                point = model.get_point("ChaGriSet")
                if point is None:
                    raise HTTPException(status_code=503, detail="ChaGriSet point not found in Model 715")
                current_value = point.value
            
            # Try to write the same value back (no actual change)
            success = await modbus._write_point(model, 'ChaGriSet', current_value)
            
            if success:
                return {
                    "success": True,
                    "can_write": True,
                    "message": "Write permission confirmed - aGate is in REMOTE mode",
                    "tested_value": current_value
                }
            else:
                return {
                    "success": True,
                    "can_write": False,
                    "message": "Write failed - aGate may be in LOCAL mode or SPAN Modbus not enabled",
                    "tested_value": current_value
                }
                
        except Exception as e:
            logger.error(f"Error testing write permission: {e}")
            return {
                "success": False,
                "can_write": False,
                "message": f"Test failed: {str(e)}"
            }
    
    @app.post("/api/power_limits")
    async def set_power_limits(request: PowerLimitRequest, device_id: Optional[str] = None):
        """
        Set battery power limits using Model 702 (kW-based control).
        
        This endpoint:
        1. Performs safety checks (operating mode, VPP enrollment)
        2. Writes to Model 702 WChaRteMax and WDisChaRteMax
        3. Returns warnings if mode isn't Self-Consumption
        """
        modbus = await app.state.connection_manager.get_client(device_id)
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        try:
            # Import safety module
            from src.battery_control_safety import create_safety_manager
            
            
            # Get Cloud API credentials from config (optional - may not exist from old config work)
            cloud_user = None
            cloud_pass = None
            # TODO: Fix ConfigManager API access
            # try:
            #     config = config_manager.get()
            #     if hasattr(config, 'cloud_api') and config.cloud_api:
            #         cloud_user = config.cloud_api.get("username")
            #         cloud_pass = config.cloud_api.get("password")
            # except Exception:
            #     pass  # Cloud API config not set up yet, that's fine
            
            # Create safety manager (works with or without Cloud credentials)
            safety = await create_safety_manager(
                modbus_client=modbus,
                cloud_username=cloud_user,
                cloud_password=cloud_pass
            )
            
            # Safety check
            safety_result = await safety.check_battery_control_safety()
            
            # Convert kW to W for Model 702
            charge_w = int(request.max_charge_kw * 1000)
            discharge_w = int(request.max_discharge_kw * 1000)
            
            # Write to Model 702 (SunSpec2 DER AC Controls)
            try:
                # Read the model first to ensure it exists
                model_702 = await modbus.read_model(702)
                if not model_702:
                    raise HTTPException(
                        status_code=500,
                        detail="Model 702 not available on this device"
                    )
                
                # Write charge limit using RAW Modbus (bypasses pysunspec2 cache)
                charge_success, charge_error = await modbus.write_model702_raw('WChaRteMax', charge_w)
                if not charge_success:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to write charge limit: {charge_error}"
                    )
                
                # Write discharge limit using RAW Modbus
                discharge_success, discharge_error = await modbus.write_model702_raw('WDisChaRteMax', discharge_w)
                if not discharge_success:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to write discharge limit: {discharge_error}"
                    )
                
                # write_point() already verified with retry logic - success!
                logger.info(f"Battery limits applied and verified: Charge={charge_w}W, Discharge={discharge_w}W")
                
            except HTTPException:
                raise  # Re-raise HTTP exceptions
            except Exception as write_error:
                logger.error(f"Failed to write Model 702 limits: {write_error}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to write limits: {str(write_error)}"
                )
            
            # Return result with safety warnings
            return {
                "success": True,
                "charge_limit_w": charge_w,
                "discharge_limit_w": discharge_w,
                "charge_limit_kw": request.max_charge_kw,
                "discharge_limit_kw": request.max_discharge_kw,
                "safe": safety_result.safe,
                "current_mode": safety_result.current_mode,
                "warnings": safety_result.warnings,
                "vpp_check_available": safety_result.vpp_check_available,
                "auto_switch_available": safety_result.auto_switch_available,
                "cloud_api_enabled": safety_result.cloud_api_enabled
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error setting power limits: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    
    @app.post("/api/battery/force_power")
    async def force_battery_power(request: ForcePowerRequest, device_id: Optional[str] = None):
        """
        Force battery to charge or discharge at specific power using Model 704.
        
        Args:
            power_watts: Positive=charge, Negative=discharge, 0=idle
            
        Returns:
            Success status and current settings
        """
        try:
            modbus = await app.state.connection_manager.get_client(device_id)
            if not modbus:
                raise HTTPException(status_code=503, detail="Modbus client not available")
            
            # Determine action for logging
            action = 'CHARGE' if request.power_watts > 0 else 'DISCHARGE' if request.power_watts < 0 else 'IDLE'
            vpp_mode_change = "ACTIVATING VPP MODE" if request.power_watts != 0 else "DEACTIVATING VPP MODE (returning to normal)"
            
            # SAFETY CHECK 1: Power Limits (use cached nameplate ratings)
            # Use cached data for better performance
            max_power_w = 5000  # Conservative fallback
            try:
                # Try to get cached capacity from last successful data read
                if hasattr(modbus, '_cached_capacity'):
                    capacity = modbus._cached_capacity
                    if capacity and capacity.max_charge_w and capacity.max_discharge_w:
                        max_charge_w = int(capacity.max_charge_w)
                        max_discharge_w = int(capacity.max_discharge_w)
                        max_power_w = max(max_charge_w, max_discharge_w)
                        logger.debug(f"Using cached nameplate: {max_power_w}W")
            except Exception as e:
                logger.warning(f"Could not read cached capacity: {e}, using fallback {max_power_w}W")
            
            # Check against limits
            if abs(request.power_watts) > max_power_w:
                logger.warning(
                    f"❌ BATTERY CONTROL REJECTED: Power {abs(request.power_watts)}W exceeds "
                    f"nameplate limit ±{max_power_w}W"
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Power exceeds nameplate ratings: ±{max_power_w}W max"
                )
            
            # SAFETY CHECK 2: SOC Monitoring (informational only - no blocking)
            # NOTE: Users have full control over SOC limits (like FranklinWH app)
            # The aGate has configurable Max Charge SOC and Min Discharge SOC in Modbus
            # Future: Add scheduler-aware SOC limit settings (not enforcement here)
            if request.power_watts != 0:
                try:
                    soc = await modbus.get_battery_soc()
                    if soc is not None:
                        logger.info(f"Battery SOC: {soc:.1f}% - User has full control")
                except Exception as e:
                    logger.debug(f"Could not read SOC for monitoring: {e}")
            
            # AUDIT LOG: Command received (after safety checks)
            logger.warning(
                f"🔋 BATTERY CONTROL REQUEST: {action} {abs(request.power_watts)}W | "
                f"{vpp_mode_change} | "
                f"Source: API endpoint"
            )
            
            # Use Model 704 WSet for battery control (with 30-min auto-timeout)
            success, error = await modbus.write_model704_battery_control(
                power_watts=request.power_watts,
                timeout_seconds=1800  # 30 minutes
            )
            
            if not success:
                # AUDIT LOG: Command failed
                logger.error(
                    f"❌ BATTERY CONTROL FAILED: {action} {abs(request.power_watts)}W | "
                    f"Error: {error}"
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to set battery power: {error}"
                )
            
            # Success!
            action_verb = 'charging' if request.power_watts > 0 else 'discharging' if request.power_watts < 0 else 'idle'
            
            # AUDIT LOG: Command succeeded
            if request.power_watts != 0:
                logger.warning(
                    f"✅ VPP MODE ACTIVATED: Battery {action_verb} at {abs(request.power_watts)}W | "
                    f"Model 704 WSetEna=1 | Normal operation OVERRIDDEN"
                )
            else:
                logger.info(
                    f"✅ VPP MODE DEACTIVATED: Battery returned to IDLE | "
                    f"Model 704 WSetEna=0 | Normal operation RESTORED"
                )
            
            return {
                "success": True,
                "power_watts": request.power_watts,
                "action": action_verb,
                "message": f"Battery {action_verb} at {abs(request.power_watts)}W",
                "vpp_mode_active": request.power_watts != 0
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error forcing battery power: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    @app.delete("/api/battery/limits")
    async def clear_battery_limits(device_id: Optional[str] = None):
        """
        Clear battery power limits (restore to unlimited operation).
        
        Sets Model 702 WChaRteMax and WDisChaRteMax to 0 (unlimited).
        """
        modbus = await app.state.connection_manager.get_client(device_id)
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        try:
            # Use RAW Modbus to clear limits (bypasses pysunspec2 cache)
            charge_success, charge_error = await modbus.write_model702_raw('WChaRteMax', 0)
            discharge_success, discharge_error = await modbus.write_model702_raw('WDisChaRteMax', 0)
            
            if not charge_success or not discharge_success:
                error = charge_error if not charge_success else discharge_error
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to clear battery limits: {error}"
                )
            
            # write_point() already verified - success!
            logger.info("Battery limits cleared and verified (unlimited operation)")
            
            return {
                "success": True,
                "charge_limit_w": 0,
                "discharge_limit_w": 0,
                "mode": "unlimited"
            }
            
        except Exception as e:
            logger.error(f"Error clearing battery limits: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/battery/safety-status")
    async def get_battery_safety_status(device_id: Optional[str] = None):
        """
        Get current battery control safety status.
        
        Returns:
        - Current operating mode
        - VPP enrollment status (if Cloud API configured)
        - Safety warnings
        - Feature availability
        """
        modbus = await app.state.connection_manager.get_client(device_id)
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        try:
            from src.battery_control_safety import create_safety_manager
            
            
            # Get Cloud API credentials from config (optional - may not exist from old config work)
            cloud_user = None
            cloud_pass = None
            try:
                config = app.state.config.get()
                if hasattr(config, 'cloud_api') and config.cloud_api:
                    cloud_user = config.cloud_api.get("username")
                    cloud_pass = config.cloud_api.get("password")
            except Exception:
                pass  # Cloud API config not set up yet, that's fine
            
            # Create safety manager
            safety = await create_safety_manager(
                modbus_client=modbus,
                cloud_username=cloud_user,
                cloud_password=cloud_pass
            )
            
            # Safety check
            safety_result = await safety.check_battery_control_safety()
            
            # Get current limits
            model_702 = await modbus.read_model(702)
            if model_702:
                charge_val = model_702.WChaRteMax
                discharge_val = model_702.WDisChaRteMax
                # Extract value if it's a Point object
                current_charge_limit = charge_val.value if hasattr(charge_val, 'value') else (charge_val or 0)
                current_discharge_limit = discharge_val.value if hasattr(discharge_val, 'value') else (discharge_val or 0)
            else:
                current_charge_limit = 0
                current_discharge_limit = 0
            
            return {
                "safe": safety_result.safe,
                "current_mode": safety_result.current_mode,
                "current_mode_id": safety_result.current_mode_id,
                "vpp_enrolled": safety_result.vpp_enrolled,
                "vpp_programme_name": safety_result.vpp_programme_name,
                "warnings": safety_result.warnings,
                "can_auto_switch": safety_result.can_auto_switch,
                "vpp_check_available": safety_result.vpp_check_available,
                "auto_switch_available": safety_result.auto_switch_available,
                "cloud_api_enabled": safety_result.cloud_api_enabled,
                "current_limits": {
                    "charge_w": current_charge_limit,
                    "discharge_w": current_discharge_limit,
                    "charge_kw": current_charge_limit / 1000 if current_charge_limit else 0,
                    "discharge_kw": current_discharge_limit / 1000 if current_discharge_limit else 0,
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting safety status: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    
    @app.post("/api/raw_registers")
    async def read_raw_registers(request: RawRegisterRequest):
        """Read raw Modbus registers."""
        modbus = await app.state.connection_manager.get_client(request.device_id)
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        try:
            from src.modbus_client_franklinwh import FranklinWHRegisterMap
            register_map = FranklinWHRegisterMap(modbus)
            
            block = await register_map.read_raw_block(request.start_address, request.count)
            
            registers = []
            for addr, value in sorted(block.items()):
                int16 = value if value <= 32767 else value - 65536
                registers.append({
                    "addr": addr,
                    "hex": f"0x{value:04x}",
                    "uint16": value,
                    "int16": int16,
                })
            
            return {"message": "Reserve SOC updated successfully", "value": value}
        except Exception as e:
            logger.error(f"Failed to set reserve SOC: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # Battery Force Charge/Discharge (VPP Mode)
    class BatteryPowerRequest(BaseModel):
        power_watts: int

    @app.post("/api/battery/power")
    async def set_battery_power(request: BatteryPowerRequest):
        """
        Force charge/discharge battery at specified power.
        Uses Model 704 WSet with 30-minute auto-timeout (VPP mode).
        
        Safety features:
        - Nameplate power limit checks
        - SOC monitoring (informational)
        - Auto-timeout after 30 minutes
        - Full audit logging
        """
        try:
            modbus = await connection_manager.get_client("default")
            if not modbus:
                raise HTTPException(status_code=503, detail="Modbus client not available")

            power_w = request.power_watts
            
            # Determine action for logging
            if power_w > 0:
                action = "CHARGE"
                vpp_mode_change = "VPP Mode ACTIVE (30-min timeout)"
            elif power_w < 0:
                action = "DISCHARGE"
                vpp_mode_change = "VPP Mode ACTIVE (30-min timeout)"
            else:
                action = "RETURN TO AUTO"
                vpp_mode_change = "VPP Mode OFF (normal operation)"

            # SAFETY CHECK 1: Nameplate power limits
            try:
                capacity = await modbus.get_der_capacity()
                if capacity and capacity.max_charge_w and capacity.max_discharge_w:
                    max_power_w = max(capacity.max_charge_w, capacity.max_discharge_w)
                    if abs(power_w) > max_power_w:
                        logger.warning(
                            f"❌ BATTERY CONTROL REJECTED: Power {abs(power_w)}W exceeds "
                            f"nameplate limit ±{max_power_w}W"
                        )
                        raise HTTPException(
                            status_code=400,
                            detail=f"Power exceeds nameplate ratings: ±{max_power_w}W max"
                        )
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"Could not verify nameplate limits: {e}")

            # SAFETY CHECK 2: SOC monitoring (informational)
            if power_w != 0:
                try:
                    soc = await modbus.get_battery_soc()
                    if soc is not None:
                        logger.info(f"Battery SOC: {soc:.1f}% - User has full control")
                except Exception as e:
                    logger.debug(f"Could not read SOC for monitoring: {e}")

            # AUDIT LOG: Command received
            logger.warning(
                f"🔋 BATTERY CONTROL REQUEST: {action} {abs(power_w)}W | "
                f"{vpp_mode_change} | Source: Web UI /api/battery/power"
            )

            # Use Model 704 WSet for battery control
            success, error = await modbus.write_model704_battery_control(
                power_watts=power_w,
                timeout_seconds=1800  # 30 minutes auto-timeout
            )

            if not success:
                logger.error(
                    f"❌ BATTERY CONTROL FAILED: {action} {abs(power_w)}W | Error: {error}"
                )
                raise HTTPException(status_code=500, detail=f"Failed to set battery power: {error}")

            # Success!
            action_verb = 'charging' if power_w > 0 else 'discharging' if power_w < 0 else 'idle'
            
            # AUDIT LOG: Command succeeded
            if power_w != 0:
                logger.warning(
                    f"✅ BATTERY CONTROL ACTIVE: {action_verb.upper()} at {abs(power_w)}W | "
                    f"Auto-timeout in 30 minutes | Use 0W to cancel early"
                )
            else:
                logger.warning("✅ BATTERY CONTROL DISABLED: Returned to auto mode")

            return {
                "success": True,
                "power_watts": power_w,
                "action": action_verb,
                "vpp_active": power_w != 0,
                "timeout_minutes": 30 if power_w != 0 else 0
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Battery power control error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/power_limits")
    async def write_register(request: WriteRegisterRequest):
        """Write a value to a Modbus register."""
        modbus = await app.state.connection_manager.get_client(request.device_id)
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        try:
            from src.modbus_client_franklinwh import FranklinWHRegisterMap
            register_map = FranklinWHRegisterMap(modbus)
            
            success = await register_map.write_raw_register(request.address, request.value)
            
            if success:
                return {"success": True, "message": f"Wrote 0x{request.value:04x} ({request.value}) to register {request.address}"}
            else:
                raise HTTPException(status_code=500, detail="Write failed - check that aGate is in REMOTE mode")
        except Exception as e:
            logger.error(f"Error writing register: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/sunspec/{model_id}")
    async def get_sunspec_model(
        model_id: int, 
        detail: str = "values",
        compact: bool = False,
        map: bool = False,
        vals: bool = False,
        verbose: bool = False,
        device_id: Optional[str] = None
    ):
        """
        Get detailed SunSpec model information using the modbus_sunspec2_reader utility.
        
        Args:
            model_id: SunSpec model ID (1, 701, 713, etc.)
            detail: Detail level (minimal, basic, values, detailed, full)
            compact: One-line summary of model IDs
            map: Columnar list of model-id string-key
            vals: One-liner per point
            verbose: Enable verbose output
            device_id: Optional device ID for multi-device setups
            
        Returns:
            Formatted text output from the SunSpec reader
        """
        config = app.state.config.get()
        
        # Import and use the SunSpec reader utility
        import sys
        from io import StringIO
        from src.modbus_sunspec2_reader import read_sunspec_device, print_device_info
        
        try:
            # Capture stdout to get the formatted output
            old_stdout = sys.stdout
            sys.stdout = captured_output = StringIO()
            
            # Call the SunSpec reader
            device_info, error = read_sunspec_device(
                ip=config.modbus.host,
                port=config.modbus.port,
                unit=config.modbus.unit_id,
                timeout=config.modbus.timeout,
                base_address=config.modbus.base_address,
                models_to_scan={model_id},
                detail_level=detail,
                verbose=verbose,
            )
            
            # Filter to only show the requested model
            if device_info and not error:
                # Filter models to only include the requested one
                all_models = device_info.get("models", {})
                filtered_models = {}
                for key, model_data in all_models.items():
                    # Check if key matches model_id (could be int or string like "1" or "701_0")
                    key_str = str(key).split('_')[0]  # Handle "701_0" -> "701"
                    if key_str == str(model_id):
                        filtered_models[key] = model_data
                
                # Create filtered device info
                filtered_info = dict(device_info)
                filtered_info["models"] = filtered_models
                
                print_device_info(
                    filtered_info, 
                    detail_level=detail, 
                    show_vals=vals or detail == "values",
                    compact=compact,
                    map_mode=map,
                )
            
            # Restore stdout and get captured output
            sys.stdout = old_stdout
            output = captured_output.getvalue()
            
            if error:
                raise HTTPException(status_code=500, detail=error)
            
            return {
                "model_id": model_id,
                "detail_level": detail,
                "output": output
            }
            
        except HTTPException:
            raise
        except Exception as e:
            sys.stdout = sys.__stdout__  # Ensure stdout is restored
            logger.error(f"Error reading SunSpec model {model_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/sunspec_scan")
    async def scan_sunspec_models(device_id: Optional[str] = None):
        """
        Scan all available SunSpec models on the device.
        
        Returns:
            List of model IDs and formatted summary
        """
        config = app.state.config.get()
        
        import sys
        from io import StringIO
        from src.modbus_sunspec2_reader import read_sunspec_device, print_device_info
        
        try:
            old_stdout = sys.stdout
            sys.stdout = captured_output = StringIO()
            
            device_info, error = read_sunspec_device(
                ip=config.modbus.host,
                port=config.modbus.port,
                unit=config.modbus.unit_id,
                timeout=config.modbus.timeout,
                base_address=config.modbus.base_address,
                detail_level="basic",
                verbose=False,
            )
            
            if device_info and not error:
                # Print compact model list
                print_device_info(device_info, detail_level="minimal", compact=True)
                # Also print basic info
                print("\n---\n")
                print_device_info(device_info, detail_level="basic")
            
            sys.stdout = old_stdout
            output = captured_output.getvalue()
            
            if error:
                raise HTTPException(status_code=500, detail=error)
            
            return {
                "output": output
            }
            
        except HTTPException:
            raise
        except Exception as e:
            sys.stdout = sys.__stdout__
            logger.error(f"Error scanning SunSpec models: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/sunspec/write")
    async def write_sunspec_point(request: SunSpecWriteRequest):
        """
        Write a value to a SunSpec point with validation.
        
        This is SAFER than raw register writes because it:
        - Uses human-readable point names (e.g., 'WChaMax')
        - Validates values before writing
        - Supports dry-run mode for testing
        """
        if not request.acknowledge_danger:
            raise HTTPException(
                status_code=400, 
                detail="You must acknowledge the danger before writing"
            )
        
        config = app.state.config.get()
        
        # Import the readwrite module
        from src.modbus_sunspec2_readwrite import write_sunspec_point as write_point
        
        try:
            success, error = write_point(
                ip=config.modbus.host,
                port=config.modbus.port,
                unit=config.modbus.unit_id,
                timeout=config.modbus.timeout,
                base_address=config.modbus.base_address,
                model_id=request.model_id,
                point_name=request.point_name,
                value=request.value,
                validate=True,
                dry_run=request.dry_run,
                verbose=False,
            )
            
            # Log the write attempt
            action = "DRY-RUN" if request.dry_run else "WRITE"
            logger.warning(
                f"SUNSPEC {action}: Model {request.model_id}.{request.point_name} = {request.value} "
                f"(success={success}, error={error})"
            )
            
            return {
                "success": success,
                "error": error,
                "dry_run": request.dry_run,
                "model_id": request.model_id,
                "point_name": request.point_name,
                "value": request.value,
                "message": f"{'Validated' if request.dry_run else 'Wrote'} {request.point_name}={request.value}" if success else error
            }
            
        except Exception as e:
            logger.error(f"Error writing SunSpec point: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/sunspec/batch_write")
    async def batch_write_sunspec_points(request: SunSpecBatchWriteRequest):
        """
        Write multiple SunSpec points atomically (all-or-nothing).
        
        All points are validated before any are written.
        """
        if not request.acknowledge_danger:
            raise HTTPException(
                status_code=400, 
                detail="You must acknowledge the danger before writing"
            )
        
        config = app.state.config.get()
        
        from src.modbus_sunspec2_readwrite import batch_write_points
        
        try:
            # Convert points list to tuples
            points_tuples = [
                (p["model_id"], p["point_name"], p["value"])
                for p in request.points
            ]
            
            results, error = batch_write_points(
                ip=config.modbus.host,
                port=config.modbus.port,
                unit=config.modbus.unit_id,
                timeout=config.modbus.timeout,
                base_address=config.modbus.base_address,
                points_to_write=points_tuples,
                validate=True,
                dry_run=request.dry_run,
                atomic=True,  # All-or-nothing
                verbose=False,
            )
            
            # Log the batch write
            action = "DRY-RUN BATCH" if request.dry_run else "BATCH WRITE"
            success_count = sum(1 for v in results.values() if v)
            logger.warning(
                f"SUNSPEC {action}: {len(points_tuples)} points, {success_count} successful"
            )
            
            return {
                "results": results,
                "error": error,
                "dry_run": request.dry_run,
                "total": len(points_tuples),
                "successful": success_count,
                "message": f"{'Validated' if request.dry_run else 'Wrote'} {success_count}/{len(points_tuples)} points"
            }
            
        except Exception as e:
            logger.error(f"Error in batch SunSpec write: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/sunspec_point")
    async def query_sunspec_point(request: SunSpecPointRequest):
        """
        Query a specific SunSpec point (e.g., "1.Mn" for manufacturer).
        
        Format: "model_id.point_name"
        """
        config = app.state.config.get()
        
        import sys
        from io import StringIO
        from src.modbus_sunspec2_reader import read_sunspec_device
        
        try:
            old_stdout = sys.stdout
            sys.stdout = captured_output = StringIO()
            
            device_info, error = read_sunspec_device(
                ip=config.modbus.host,
                port=config.modbus.port,
                unit=config.modbus.unit_id,
                timeout=config.modbus.timeout,
                base_address=config.modbus.base_address,
                specific_point=request.point,
                verbose=request.verbose,
            )
            
            sys.stdout = old_stdout
            output = captured_output.getvalue()
            
            if error:
                raise HTTPException(status_code=500, detail=error)
            
            return {"output": output}
            
        except HTTPException:
            raise
        except Exception as e:
            sys.stdout = sys.__stdout__
            logger.error(f"Error querying SunSpec point: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/sunspec_raw")
    async def read_sunspec_raw(request: SunSpecRawRequest):
        """
        Read raw registers from SunSpec device.
        
        Format: "start:count" (e.g., "15500:14")
        """
        config = app.state.config.get()
        
        import sys
        from io import StringIO
        from src.modbus_sunspec2_reader import read_sunspec_device
        
        try:
            old_stdout = sys.stdout
            sys.stdout = captured_output = StringIO()
            
            device_info, error = read_sunspec_device(
                ip=config.modbus.host,
                port=config.modbus.port,
                unit=config.modbus.unit_id,
                timeout=config.modbus.timeout,
                base_address=config.modbus.base_address,
                raw_read_spec=request.raw,
                verbose=request.verbose,
            )
            
            # For raw reads with --match, we need to do a full scan first
            # The reader utility handles this internally
            
            sys.stdout = old_stdout
            output = captured_output.getvalue()
            
            if error:
                raise HTTPException(status_code=500, detail=error)
            
            return {"output": output}
            
        except HTTPException:
            raise
        except Exception as e:
            sys.stdout = sys.__stdout__
            logger.error(f"Error reading raw registers: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Logs API Endpoints
    
    @app.get("/api/logs")
    async def get_logs(
        level: Optional[str] = None,
        levels: Optional[List[str]] = Query(None),  # For multi-select badge filters
        source: Optional[str] = None,
        search: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ):
        """
        Get application logs with filtering.
        
        Query parameters:
        - level: Filter by single level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        - levels: Filter by multiple levels (e.g., ?levels=ERROR&levels=WARNING)
        - source: Filter by source (logger name)
        - search: Search in message and source
        - start_date: ISO format date (e.g., 2024-01-01T00:00:00)
        - end_date: ISO format date
        - limit: Max results (default 100)
        - offset: Pagination offset
        """
        try:
            from src.log_manager import log_manager
            
            # Prefer multi-select 'levels' over single 'level'
            filter_levels = levels if levels else ([level] if level else None)
            
            logs = await log_manager.get_logs(
                level=filter_levels[0] if filter_levels and len(filter_levels) == 1 else None,
                levels=filter_levels if filter_levels and len(filter_levels) > 1 else None,
                source=source,
                search=search,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                offset=offset
            )
            
            return {
                "logs": [
                    {
                        "id": log.id,
                        "timestamp": log.timestamp.isoformat(),
                        "level": log.level,
                        "source": log.source,
                        "message": log.message,
                        "metadata": log.metadata
                    }
                    for log in logs
                ],
                "total": len(logs)
            }
            
        except Exception as e:
            logger.error(f"Error getting logs: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/logs/stats")
    async def get_logs_stats():
        """Get log statistics."""
        try:
            from src.log_manager import log_manager
            stats = await log_manager.get_stats()
            return stats
            
        except Exception as e:
            logger.error(f"Error getting log stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/logs/export")
    async def export_logs(
        format: str = "json",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ):
        """
        Export logs to JSON or CSV.
        
        Query parameters:
        - format: "json" or "csv"
        - start_date: Optional start date filter
        - end_date: Optional end date filter
        """
        try:
            from src.log_manager import log_manager
            
            if format.lower() == "csv":
                content = await log_manager.export_csv(start_date, end_date)
                media_type = "text/csv"
                filename = f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            else:
                content = await log_manager.export_json(start_date, end_date)
                media_type = "application/json"
                filename = f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            from fastapi.responses import Response
            return Response(
                content=content,
                media_type=media_type,
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
            
        except Exception as e:
            logger.error(f"Error exporting logs: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/logs/clear")
    async def clear_old_logs():
        """Clear logs older than max_age_days."""
        try:
            from src.log_manager import log_manager
            await log_manager.clear_old_logs()
            return {"success": True, "message": "Old logs cleared"}
            
        except Exception as e:
            logger.error(f"Error clearing logs: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/settings")
    async def get_settings():
        """Get current settings."""
        config = app.state.config.get()
        return {
            "modbus": {
                "host": config.modbus.host,
                "port": config.modbus.port,
                "unit_id": config.modbus.unit_id,
                "base_address": config.modbus.base_address,
                "timeout": config.modbus.timeout,
            },
            "mqtt": {
                # Broker settings
                "host": config.mqtt.host,
                "port": config.mqtt.port,
                "username": config.mqtt.username,
                # Password masked for security - only indicate if set
                "has_password": bool(config.mqtt.password),
                "client_id": config.mqtt.client_id,
                "enabled": config.mqtt.enabled,
                # Site configuration
                "site_name": config.mqtt.site_name,
                "site_id": config.mqtt.site_id,
                "site_description": config.mqtt.site_description,
                "is_remote_site": config.mqtt.is_remote_site,
                # Device publishing settings
                "publish_devices": config.mqtt.publish_devices,
                # HA Discovery settings
                "discovery_prefix": config.mqtt.discovery_prefix,
                "state_prefix": config.mqtt.state_prefix,
                "ha_device_name": config.mqtt.ha_device_name,
                "unique_id_prefix": config.mqtt.unique_id_prefix,
                # Entity selection
                "publish_battery": config.mqtt.publish_battery,
                "publish_inverter": config.mqtt.publish_inverter,
                "publish_solar": config.mqtt.publish_solar,
                "publish_home_loads": config.mqtt.publish_home_loads,
                "publish_capacity": config.mqtt.publish_capacity,
                "publish_controls": config.mqtt.publish_controls,
                # Advanced
                "retain_discovery": config.mqtt.retain_discovery,
                "qos": config.mqtt.qos,
            },
            "theme": {
                "primary_color": config.theme.primary_color,
                "secondary_color": config.theme.secondary_color,
                "accent_color": config.theme.accent_color,
                "mode": config.theme.mode,
            },
            "auto_refresh": config.auto_refresh,
            "refresh_interval": config.refresh_interval,
            "widgets": {k: asdict(v) for k, v in config.widgets.items()},
            "sites": [asdict(s) for s in config.sites.values()],
            "log_level": config.log_level,
            "log_retention_days": config.log_retention_days,
        }

    @app.post("/api/settings")
    async def save_settings(request: SettingsRequest):
        """Save settings to disk."""
        try:
            config = app.state.config.get()
            
            if request.modbus:
                config.modbus.host = request.modbus.host
                config.modbus.port = request.modbus.port
                config.modbus.unit_id = request.modbus.unit_id
                config.modbus.base_address = request.modbus.base_address
                config.modbus.timeout = request.modbus.timeout
                
            if request.mqtt:
                mqtt_fields = [
                    'host', 'port', 'username', 'password', 'client_id',
                    'site_name', 'site_id', 'site_description', 'is_remote_site',
                    'discovery_prefix', 'state_prefix', 'ha_device_name', 'unique_id_prefix',
                    'publish_devices',
                    'publish_battery', 'publish_inverter', 'publish_solar', 
                    'publish_home_loads', 'publish_capacity', 'publish_controls',
                    'retain_discovery', 'qos', 'enabled'
                ]
                for field in mqtt_fields:
                    if hasattr(request.mqtt, field):
                        value = getattr(request.mqtt, field)
                        if field == 'password' and not value:
                            continue  # Don't clear password if not provided
                        setattr(config.mqtt, field, value)
                
            if request.theme:
                config.theme.mode = request.theme.mode
                config.theme.primary_color = request.theme.primary_color
                
            if request.auto_refresh is not None:
                config.auto_refresh = request.auto_refresh
                
            if request.refresh_interval is not None:
                config.refresh_interval = request.refresh_interval

            # Handle widgets if present
            if request.widgets:
                for key, w_conf in request.widgets.items():
                    if key in config.widgets:
                        config.widgets[key].enabled = w_conf.enabled
                        config.widgets[key].position = w_conf.position
                        config.widgets[key].color = w_conf.color
                        config.widgets[key].expanded = w_conf.expanded
            
            # Handle sites if present
            if request.sites:
                for site_req in request.sites:
                    if site_req.id in config.sites:
                        config.sites[site_req.id].name = site_req.name
                        config.sites[site_req.id].description = site_req.description
                        config.sites[site_req.id].is_local = site_req.is_local
            
            # Handle log settings
            if request.log_level is not None:
                config.log_level = request.log_level
                # Update root logger level
                logging.getLogger().setLevel(getattr(logging, request.log_level.upper(), logging.INFO))
            
            if request.log_retention_days is not None:
                config.log_retention_days = request.log_retention_days
                # Update log manager retention
                from src.log_manager import log_manager
                if log_manager:
                    log_manager.max_age_days = request.log_retention_days
            
            await app.state.config.save()
            return {"success": True}
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # MQTT Admin Endpoints
    
    @app.get("/mqtt-admin")
    async def mqtt_admin_page(request: Request):
        """MQTT Administration page."""
        return templates.TemplateResponse("mqtt_admin.html", {"request": request})
    
    @app.post("/api/mqtt/test")
    async def test_mqtt_connection(request: Request):
        """Test MQTT broker connection without saving."""
        try:
            data = await request.json()
            host = data.get("host", "localhost")
            port = data.get("port", 1883)
            username = data.get("username", "")
            password = data.get("password", "")
            
            # Attempt connection test using raw paho-mqtt for better compatibility
            try:
                import asyncio
                import paho.mqtt.client as mqtt
                
                # Create a temporary client
                test_client = mqtt.Client(client_id="franklinwh_test_" + str(asyncio.get_event_loop().time()))
                
                if username:
                    test_client.username_pw_set(username, password)
                
                # Connection result container
                conn_result = {"connected": False, "error": None}
                
                def on_connect(client, userdata, flags, rc):
                    if rc == 0:
                        conn_result["connected"] = True
                    else:
                        error_codes = {
                            1: "Incorrect protocol version",
                            2: "Invalid client identifier",
                            3: "Server unavailable",
                            4: "Bad username or password",
                            5: "Not authorized"
                        }
                        conn_result["error"] = error_codes.get(rc, f"Connection refused (code {rc})")
                
                def on_connect_fail(client, userdata):
                    conn_result["error"] = "Connection failed"
                
                test_client.on_connect = on_connect
                test_client.on_connect_fail = on_connect_fail
                
                # Try to connect with timeout
                try:
                    test_client.connect(host, port, keepalive=5)
                    test_client.loop_start()
                    
                    # Wait for connection result
                    for _ in range(50):  # 5 seconds timeout
                        await asyncio.sleep(0.1)
                        if conn_result["connected"] or conn_result["error"]:
                            break
                    
                    test_client.loop_stop()
                    test_client.disconnect()
                    
                    if conn_result["connected"]:
                        return {"success": True, "message": "Connection successful"}
                    else:
                        error_msg = conn_result["error"] or "Connection timeout"
                        return {"success": False, "message": error_msg}
                        
                except Exception as e:
                    return {"success": False, "message": f"Connection error: {str(e)}"}
                    
            except ImportError:
                return {"success": False, "message": "MQTT library not available"}
            except Exception as e:
                return {"success": False, "message": str(e)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/mqtt/republish")
    async def republish_discovery():
        """Republish all MQTT discovery messages."""
        mqtt = app.state.mqtt
        if not mqtt:
            raise HTTPException(status_code=503, detail="MQTT bridge not available")
        
        try:
            # Pass mqtt config to use entity selection settings
            config = app.state.config.get()
            await mqtt.setup_entities(mqtt_config=config.mqtt)
            return {"success": True, "message": "Discovery messages republished"}
        except Exception as e:
            logger.error(f"Error republishing discovery: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # MQTT Control Endpoints
    
    @app.get("/api/mqtt/status")
    async def get_mqtt_status():
        """Get detailed MQTT connection status."""
        import time
        mqtt = app.state.mqtt
        if not mqtt:
            raise HTTPException(status_code=503, detail="MQTT bridge not available")
        
        uptime_seconds = mqtt.get_uptime_seconds()
        last_connected = mqtt.last_connected_at
        stats = mqtt.get_stats()
        
        return {
            "enabled": mqtt.is_enabled,
            "status": mqtt.status.value,
            "connected": mqtt.is_connected,
            "uptime_seconds": uptime_seconds,
            "uptime_formatted": _format_uptime(uptime_seconds) if uptime_seconds else None,
            "last_connected_at": last_connected,
            "last_connected_formatted": _format_timestamp(last_connected) if last_connected else None,
            "broker": {
                "host": mqtt.broker_host,
                "port": mqtt.broker_port,
            },
            "client_id": mqtt.client_id,
            "stats": {
                "messages_published": stats["messages_published"],
                "last_publish_seconds_ago": stats["last_publish_seconds_ago"]
            }
        }
    
    def _format_uptime(seconds: int) -> str:
        """Format uptime in human-readable form."""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            mins = seconds // 60
            secs = seconds % 60
            return f"{mins}m {secs}s"
        elif seconds < 86400:
            hours = seconds // 3600
            mins = (seconds % 3600) // 60
            return f"{hours}h {mins}m"
        else:
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            return f"{days}d {hours}h"
    
    def _format_timestamp(timestamp: float) -> str:
        """Format Unix timestamp to readable string."""
        from datetime import datetime
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    
    @app.post("/api/mqtt/enable")
    async def enable_mqtt():
        """Enable MQTT bridge (starts background connection attempts)."""
        mqtt = app.state.mqtt
        if not mqtt:
            raise HTTPException(status_code=503, detail="MQTT bridge not available")
        
        if mqtt.is_enabled:
            return {"success": True, "message": "MQTT already enabled", "status": mqtt.status.value}
        
        success = await mqtt.enable()
        
        # Persist enabled state to config
        if success:
            config = app.state.config.get()
            config.mqtt.enabled = True
            await app.state.config.save()
        
        return {
            "success": success,
            "status": mqtt.status.value,
            "message": "MQTT enabled - will auto-connect in background" if success else "Failed to enable MQTT"
        }
    
    @app.post("/api/mqtt/disable")
    async def disable_mqtt():
        """Disable MQTT bridge (stops connection and publishing)."""
        mqtt = app.state.mqtt
        if not mqtt:
            raise HTTPException(status_code=503, detail="MQTT bridge not available")
        
        if not mqtt.is_enabled:
            return {"success": True, "message": "MQTT already disabled", "status": mqtt.status.value}
        
        await mqtt.disable()
        
        # Persist disabled state to config
        config = app.state.config.get()
        config.mqtt.enabled = False
        await app.state.config.save()
        
        return {
            "success": True,
            "status": mqtt.status.value,
            "message": "MQTT disabled"
        }
    
    @app.post("/api/mqtt/restart")
    async def restart_mqtt():
        """Restart MQTT bridge (disable then re-enable)."""
        mqtt = app.state.mqtt
        if not mqtt:
            raise HTTPException(status_code=503, detail="MQTT bridge not available")
        
        if mqtt.is_enabled:
            await mqtt.disable()
        
        await mqtt.enable()
        return {
            "success": True,
            "status": mqtt.status.value,
            "message": "MQTT restarted - connecting in background"
        }
    
    # Topology Endpoints
    
    @app.get("/api/topology")
    async def get_topology():
        """Get configured topology."""
        config = app.state.config.get()
        clients = app.state.connection_manager.get_all_clients()
        
        devices = []
        for dev_id, dev_conf in config.devices.items():
            client = clients.get(dev_id)
            connected = client._connected if client else False
            devices.append({
                **asdict(dev_conf),
                "connected": connected,
                "status": "Online" if connected else "Offline"
            })
            
        return {"devices": devices}

    @app.post("/api/topology")
    async def add_device(request: TopologyRequest):
        """Add or update a device in topology."""
        try:
            device_config = DeviceConfig(
                id=request.id,
                name=request.name,
                description=request.description,
                host=request.host,
                port=request.port,
                unit_id=request.unit_id,
                base_address=request.base_address,
                timeout=request.timeout,
                enabled=request.enabled
            )
            
            # ALWAYS save to config first (so device persists even if offline)
            app.state.config.add_device(device_config)
            await app.state.config.save()
            logger.info(f"Device {request.id} saved to config")
            
            # Try to connect in background (don't fail if device is offline)
            connection_error = None
            try:
                await app.state.connection_manager.add_client(device_config)
                logger.info(f"Device {request.id} connected successfully")
            except ValueError as e:
                # Validation failed - log but don't fail
                connection_error = str(e)
                logger.warning(f"Device {request.id} validation failed: {e}")
            except Exception as e:
                # Connection failed - device is offline but saved
                connection_error = str(e)
                logger.warning(f"Device {request.id} offline (will retry): {e}")
            
            return {
                "success": True, 
                "device": asdict(device_config),
                "connected": connection_error is None,
                "message": connection_error if connection_error else "Device added and connected"
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error adding device: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/topology/{device_id}")
    async def remove_device(device_id: str):
        """Remove a device from topology."""
        try:
            # Remove from connection manager first
            await app.state.connection_manager.remove_client(device_id)
            
            # Remove from config
            app.state.config.remove_device(device_id)
            await app.state.config.save()
            
            return {"success": True}
        except Exception as e:
            logger.error(f"Error removing device: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.put("/api/topology/{device_id}")
    async def update_device(device_id: str, request: DeviceEditRequest):
        """Update device name and description."""
        try:
            config = app.state.config.get()
            if device_id not in config.devices:
                raise HTTPException(status_code=404, detail="Device not found")
            
            config.devices[device_id].name = request.name
            config.devices[device_id].description = request.description
            await app.state.config.save()
            
            return {"success": True}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating device: {e}")
            raise HTTPException(status_code=500, detail=str(e))
            
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket, device_id: Optional[str] = None):
        """WebSocket endpoint for real-time updates."""
        await websocket.accept()
        app.state.websockets.append(websocket)
        
        try:
            # Send initial data
            modbus = await app.state.connection_manager.get_client(device_id)
            if modbus:
                data = await modbus.read_all()
                await websocket.send_json({
                    "type": "data",
                    "data": data,
                })
            
            # Keep connection alive and handle client messages
            while True:
                try:
                    message = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=30.0
                    )
                    
                    # Handle client requests
                    try:
                        msg = json.loads(message)
                        if msg.get("action") == "refresh":
                            modbus = await app.state.connection_manager.get_client(msg.get("device_id"))
                            if modbus:
                                data = await modbus.read_all()
                                await websocket.send_json({
                                    "type": "data",
                                    "data": data,
                                })
                    except json.JSONDecodeError:
                        pass
                    
                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    await websocket.send_json({"type": "ping"})
                    
        except WebSocketDisconnect:
            pass
        finally:
            if websocket in app.state.websockets:
                app.state.websockets.remove(websocket)
    
    # Dashboard to MQTT Publishing Endpoints
    
    class MQTTPublishRequest(BaseModel):
        topic: str
        value: Union[str, float, int, bool]
        retain: bool = False
    
    @app.post("/api/mqtt/publish")
    async def mqtt_publish(request: MQTTPublishRequest):
        """Publish a value to MQTT from dashboard."""
        mqtt = app.state.mqtt
        if not mqtt:
            raise HTTPException(status_code=503, detail="MQTT bridge not available")
        
        if not mqtt.is_connected:
            raise HTTPException(status_code=503, detail="MQTT not connected")
        
        try:
            await mqtt.publish_state(request.topic, request.value)
            return {
                "success": True,
                "topic": f"{mqtt._state_topic_base}/{request.topic}",
                "value": request.value
            }
        except Exception as e:
            logger.error(f"Error publishing to MQTT: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/mqtt/publish_grid_power")
    async def mqtt_publish_grid_power():
        """Calculate and publish grid power to MQTT."""
        mqtt = app.state.mqtt
        if not mqtt or not mqtt.is_connected:
            raise HTTPException(status_code=503, detail="MQTT not available")
        
        try:
            # Get current data
            modbus = await app.state.connection_manager.get_client()
            if not modbus:
                raise HTTPException(status_code=503, detail="Modbus not available")
            
            data = await modbus.read_all()
            home = data.get("home_loads", {}).home_loads_w if data.get("home_loads") else 0
            solar = data.get("solar_pv", {}).output_power_w if data.get("solar_pv") else 0
            battery = data.get("inverter_ac", {}).power_w if data.get("inverter_ac") else 0
            
            # Calculate grid power (positive = importing, negative = exporting)
            grid_power = (home or 0) - (solar or 0) - (battery or 0)
            
            await mqtt.publish_state("calculated/grid_power", grid_power)
            await mqtt.publish_state("calculated/grid_import", max(grid_power, 0))
            await mqtt.publish_state("calculated/grid_export", max(-grid_power, 0))
            
            return {
                "success": True,
                "grid_power": grid_power,
                "importing": max(grid_power, 0),
                "exporting": max(-grid_power, 0)
            }
        except Exception as e:
            logger.error(f"Error calculating grid power: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/api/mqtt/publish_dashboard")
    async def mqtt_publish_dashboard():
        """Publish all dashboard-calculated values to MQTT."""
        mqtt = app.state.mqtt
        if not mqtt or not mqtt.is_connected:
            raise HTTPException(status_code=503, detail="MQTT not available")
        
        try:
            modbus = await app.state.connection_manager.get_client()
            if not modbus:
                raise HTTPException(status_code=503, detail="Modbus not available")
            
            data = await modbus.read_all()
            published = []
            
            # Grid power calculations
            home = data.get("home_loads", {}).home_loads_w if data.get("home_loads") else 0
            solar = data.get("solar_pv", {}).output_power_w if data.get("solar_pv") else 0
            battery_power = data.get("inverter_ac", {}).power_w if data.get("inverter_ac") else 0
            
            grid_power = (home or 0) - (solar or 0) - (battery_power or 0)
            
            await mqtt.publish_state("calculated/grid_power", grid_power)
            await mqtt.publish_state("calculated/grid_import", max(grid_power, 0))
            await mqtt.publish_state("calculated/grid_export", max(-grid_power, 0))
            published.extend(["calculated/grid_power", "calculated/grid_import", "calculated/grid_export"])
            
            # Battery flow direction (for easier automation)
            if battery_power is not None:
                if battery_power < -50:
                    await mqtt.publish_state("calculated/battery_flow", "charging")
                elif battery_power > 50:
                    await mqtt.publish_state("calculated/battery_flow", "discharging")
                else:
                    await mqtt.publish_state("calculated/battery_flow", "standby")
                published.append("calculated/battery_flow")
            
            # Grid flow direction
            if abs(grid_power) > 50:
                if grid_power > 0:
                    await mqtt.publish_state("calculated/grid_flow", "importing")
                else:
                    await mqtt.publish_state("calculated/grid_flow", "exporting")
            else:
                await mqtt.publish_state("calculated/grid_flow", "idle")
            published.append("calculated/grid_flow")
            
            return {
                "success": True,
                "published": published,
                "values": {
                    "grid_power": grid_power,
                    "battery_flow": "charging" if battery_power < -50 else ("discharging" if battery_power > 50 else "standby"),
                    "grid_flow": "importing" if grid_power > 50 else ("exporting" if grid_power < -50 else "idle")
                }
            }
        except Exception as e:
            logger.error(f"Error publishing dashboard values: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    return app

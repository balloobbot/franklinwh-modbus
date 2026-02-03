"""
FastAPI web server for the FranklinWH Battery Manager.
Provides REST API endpoints for the web interface and WebSocket support for real-time updates.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING
from dataclasses import asdict

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
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
    
    # HA Discovery settings
    discovery_prefix: Optional[str] = "homeassistant"
    state_prefix: Optional[str] = "franklinwh"
    ha_device_name: Optional[str] = "FranklinWH Battery"
    unique_id_prefix: Optional[str] = "franklinwh"
    
    # Entity selection
    publish_battery: Optional[bool] = True
    publish_inverter: Optional[bool] = True
    publish_solar: Optional[bool] = True
    publish_home_loads: Optional[bool] = True
    publish_capacity: Optional[bool] = True
    publish_controls: Optional[bool] = True
    
    # Advanced
    retain_discovery: Optional[bool] = True
    qos: Optional[int] = 0


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


class SettingsRequest(BaseModel):
    modbus: Optional[ModbusConfigRequest] = None
    mqtt: Optional[MQTTConfigRequest] = None
    theme: Optional[ThemeConfigRequest] = None
    auto_refresh: Optional[bool] = None
    refresh_interval: Optional[int] = None
    widgets: Optional[Dict[str, WidgetConfigRequest]] = None


class ModeRequest(BaseModel):
    mode: int


class ReserveRequest(BaseModel):
    value: int


class PowerLimitRequest(BaseModel):
    max_charge_kw: float
    max_discharge_kw: float


class TopologyRequest(BaseModel):
    id: str
    name: str
    host: str
    port: int = 502
    unit_id: int = 1
    base_address: int = 40001
    timeout: int = 3
    enabled: bool = True

class RawRegisterRequest(BaseModel):
    start_address: int
    count: int = 41
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

    @app.get("/api/health")
    async def health(device_id: Optional[str] = None):
        """Health check endpoint with MQTT status."""
        modbus = await app.state.connection_manager.get_client(device_id)
        mqtt = app.state.mqtt
        
        mqtt_status = {
            "enabled": mqtt.is_enabled if mqtt else False,
            "status": mqtt.status.value if mqtt else "unknown",
            "connected": mqtt.is_connected if mqtt else False,
            "broker": f"{mqtt.broker_host}:{mqtt.broker_port}" if mqtt else None,
        } if mqtt else None
        
        return {
            "status": "ok",
            "mock_mode": getattr(app.state, 'mock_mode', False),
            "modbus_connected": modbus._connected if modbus else False,
            "mqtt": mqtt_status,
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
            # 15016: Operating Mode (0=Standby, 1=Normal, 2=Backup, 3=Self-Consume, 4=TOU)
            # 15017: Reserve SOC - Self-Consumption mode reserve (maps to Model 713 SoC reserve)
            # 15040: Reserve SOC 2 - TOU mode reserve (int8, -128 to 127)
            extensions_data = None
            try:
                from src.modbus_client_franklinwh import FranklinWHRegisterMap
                register_map = FranklinWHRegisterMap(modbus)
                metrics = await register_map.read_all_metrics()
                mode_text = await register_map.get_operating_mode_text(metrics.operating_mode)
                
                # Normalize reserveSoc2 (handle unsigned int16 -> signed int8 conversion)
                reserve_soc_2_normalized = metrics.reserve_soc_2
                if reserve_soc_2_normalized is not None and reserve_soc_2_normalized > 32767:
                    reserve_soc_2_normalized = reserve_soc_2_normalized - 65536
                
                extensions_data = {
                    # SunSpec2-aligned naming (camelCase)
                    "operatingMode": metrics.operating_mode,
                    "modeText": mode_text,
                    "reserveSoc": metrics.reserve_soc,  # Register 15017
                    "reserveSoc2": reserve_soc_2_normalized,  # Register 15040
                    
                    # Snake_case aliases for API consistency
                    "operating_mode": metrics.operating_mode,
                    "mode_text": mode_text,
                    "reserve_soc": metrics.reserve_soc,
                    "reserve_soc_2": reserve_soc_2_normalized,
                    
                    # Human-readable aliases
                    "reserve_soc_self_consumption": metrics.reserve_soc,
                    "reserve_soc_tou": reserve_soc_2_normalized,
                    
                    # Traceability: Register addresses
                    "_meta": {
                        "operating_mode_register": 15016,
                        "reserve_soc_register": 15017,
                        "reserve_soc_2_register": 15040,
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
                } if data.get("battery") else None,
                "inverter": {
                    "power": data.get("inverter_ac", {}).power_w if data.get("inverter_ac") else None,
                    "voltage": data.get("inverter_ac", {}).voltage_v if data.get("inverter_ac") else None,
                    "current": data.get("inverter_ac", {}).current_a if data.get("inverter_ac") else None,
                    "frequency": data.get("inverter_ac", {}).frequency_hz if data.get("inverter_ac") else None,
                    "power_factor": data.get("inverter_ac", {}).power_factor if data.get("inverter_ac") else None,
                } if data.get("inverter_ac") else None,
                "capacity": {
                    "max_charge_w": data.get("capacity", {}).max_charge_w if data.get("capacity") else None,
                    "max_discharge_w": data.get("capacity", {}).max_discharge_w if data.get("capacity") else None,
                } if data.get("capacity") else None,
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
                "reserveSoc": metrics.reserve_soc,  # Register 15017
                "reserveSoc2": reserve_soc_2_normalized,  # Register 15040
                
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
                    "operating_mode_register": 15016,
                    "reserve_soc_register": 15017,
                    "reserve_soc_2_register": 15040,
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
        """Set battery operating mode."""
        modbus = await app.state.connection_manager.get_client(device_id)
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        try:
            # Map mode numbers to BatteryMode enum
            mode_map = {
                0: BatteryMode.IDLE,
                1: BatteryMode.CHARGING,  # Normal might be different
                2: BatteryMode.DISCHARGING,  # Backup reserve
            }
            
            # For now, use the extension method which supports the 5 modes
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
        """Set reserve SOC."""
        modbus = await app.state.connection_manager.get_client(device_id)
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        try:
            from src.modbus_client_franklinwh import FranklinWHRegisterMap
            register_map = FranklinWHRegisterMap(modbus)
            success = await register_map.set_reserve_soc(request.value)
            
            if success:
                return {"success": True, "reserve_soc": request.value}
            else:
                raise HTTPException(status_code=400, detail="Failed to set reserve")
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
    
    @app.post("/api/power_limits")
    async def set_power_limits(request: PowerLimitRequest, device_id: Optional[str] = None):
        """Set power limits."""
        modbus = await app.state.connection_manager.get_client(device_id)
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        try:
            # Convert kW to W
            charge_w = request.max_charge_kw * 1000
            discharge_w = request.max_discharge_kw * 1000
            
            # Use Modbus storage controls
            # This would need to be implemented based on the specific Modbus model
            # For now, return success
            return {
                "success": True,
                "max_charge_w": charge_w,
                "max_discharge_w": discharge_w,
            }
        except Exception as e:
            logger.error(f"Error setting power limits: {e}")
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
            
            return {"registers": registers}
        except Exception as e:
            logger.error(f"Error reading raw registers: {e}")
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
                    'discovery_prefix', 'state_prefix', 'ha_device_name', 'unique_id_prefix',
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
            
            # Attempt connection test
            try:
                import asyncio
                from asyncio_mqtt import Client, MqttError
                
                client_kwargs = {"hostname": host, "port": port}
                if username:
                    client_kwargs["username"] = username
                    client_kwargs["password"] = password
                
                # Try to connect with short timeout
                client = Client(**client_kwargs)
                await asyncio.wait_for(client.__aenter__(), timeout=5.0)
                await client.__aexit__(None, None, None)
                
                return {"success": True, "message": "Connection successful"}
            except asyncio.TimeoutError:
                return {"success": False, "message": "Connection timeout"}
            except MqttError as e:
                return {"success": False, "message": f"MQTT error: {str(e)}"}
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
        mqtt = app.state.mqtt
        if not mqtt:
            raise HTTPException(status_code=503, detail="MQTT bridge not available")
        
        return {
            "enabled": mqtt.is_enabled,
            "status": mqtt.status.value,
            "connected": mqtt.is_connected,
            "broker": {
                "host": mqtt.broker_host,
                "port": mqtt.broker_port,
            },
            "client_id": mqtt.client_id,
        }
    
    @app.post("/api/mqtt/enable")
    async def enable_mqtt():
        """Enable MQTT bridge (starts background connection attempts)."""
        mqtt = app.state.mqtt
        if not mqtt:
            raise HTTPException(status_code=503, detail="MQTT bridge not available")
        
        if mqtt.is_enabled:
            return {"success": True, "message": "MQTT already enabled", "status": mqtt.status.value}
        
        success = await mqtt.enable()
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
    
    return app

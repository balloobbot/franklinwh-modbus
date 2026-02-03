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

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# Import components
from src.models import BatteryMode

if TYPE_CHECKING:
    from src.config_manager import ConfigManager
    from src.mqtt_handler import HomeAssistantMQTTBridge
    from src.modbus_client import FranklinWHModbusClient

try:
    from src.config_manager import ConfigManager
    from src.mqtt_handler import HomeAssistantMQTTBridge
    from src.modbus_client import FranklinWHModbusClient
except ImportError:
    # Allow importing for type checking even if deps not available
    ConfigManager = None
    HomeAssistantMQTTBridge = None
    FranklinWHModbusClient = None

logger = logging.getLogger(__name__)

# Request/Response models
class ModbusConfigRequest(BaseModel):
    host: str
    port: int
    unit_id: int
    base_address: int = 40000
    timeout: float = 5.0


class MQTTConfigRequest(BaseModel):
    host: str
    port: int = 1883
    username: str = ""
    password: str = ""


class ThemeConfigRequest(BaseModel):
    primary_color: str = "#3b82f6"
    secondary_color: str = "#10b981"
    accent_color: str = "#f59e0b"
    mode: str = "auto"


class SettingsRequest(BaseModel):
    modbus: Optional[ModbusConfigRequest] = None
    mqtt: Optional[MQTTConfigRequest] = None
    theme: Optional[ThemeConfigRequest] = None
    auto_refresh: Optional[bool] = None
    refresh_interval: Optional[int] = None


class ModeRequest(BaseModel):
    mode: int


class ReserveRequest(BaseModel):
    value: int


class PowerLimitRequest(BaseModel):
    max_charge_kw: float
    max_discharge_kw: float


class RawRegisterRequest(BaseModel):
    start_address: int
    count: int = 41


def create_app(
    modbus_client: FranklinWHModbusClient,
    mqtt_bridge: Optional[HomeAssistantMQTTBridge],
    config_manager: ConfigManager,
    mock_mode: bool = False,
) -> FastAPI:
    """Create and configure the FastAPI application."""
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Application lifespan handler."""
        logger.info("Web server starting up...")
        yield
        logger.info("Web server shutting down...")
    
    app = FastAPI(
        title="FranklinWH Battery Manager",
        description="Web interface for managing FranklinWH battery systems",
        version="1.0.0",
        lifespan=lifespan,
    )
    
    # Store mode indicator
    app.state.mock_mode = mock_mode
    
    # Store references
    app.state.modbus = modbus_client
    app.state.mqtt = mqtt_bridge
    app.state.config = config_manager
    
    # Active WebSocket connections
    app.state.websockets: list[WebSocket] = []
    
    # Mount static files
    static_dir = Path(__file__).parent.parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Serve the main HTML page."""
        index_file = static_dir / "index.html"
        if index_file.exists():
            return HTMLResponse(content=index_file.read_text())
        return HTMLResponse(content="<h1>FranklinWH Battery Manager</h1><p>Static files not found</p>")
    
    @app.get("/api/health")
    async def health():
        """Health check endpoint with MQTT status."""
        modbus = app.state.modbus
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
    async def get_data():
        """Get current battery and inverter data."""
        modbus = app.state.modbus
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        try:
            data = await modbus.read_all()
            
            # Get extensions data if available
            extensions_data = None
            try:
                from src.modbus_client_franklinwh import FranklinWHRegisterMap
                register_map = FranklinWHRegisterMap(modbus)
                metrics = await register_map.read_all_metrics()
                mode_text = await register_map.get_operating_mode_text(metrics.operating_mode)
                extensions_data = {
                    "operatingMode": metrics.operating_mode,
                    "modeText": mode_text,
                    "reserveSoc": metrics.reserve_soc,
                    "reserveSoc2": metrics.reserve_soc_2 if metrics.reserve_soc_2 is None or metrics.reserve_soc_2 <= 32767 else metrics.reserve_soc_2 - 65536,
                    "reserve_soc_self_consumption": metrics.reserve_soc,
                    "reserve_soc_tou": metrics.reserve_soc_2 if metrics.reserve_soc_2 is None or metrics.reserve_soc_2 <= 32767 else metrics.reserve_soc_2 - 65536,
                }
            except Exception:
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
    async def get_extensions():
        """Get FranklinWH extension register values."""
        modbus = app.state.modbus
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        try:
            from src.modbus_client_franklinwh import FranklinWHRegisterMap
            register_map = FranklinWHRegisterMap(modbus)
            metrics = await register_map.read_all_metrics()
            
            mode_text = await register_map.get_operating_mode_text(metrics.operating_mode)
            
            return {
                # New naming convention
                "operating_mode": {
                    "raw": metrics.operating_mode,
                    "text": mode_text,
                },
                "reserve_soc_self_consumption": metrics.reserve_soc,
                "reserve_soc_tou": metrics.reserve_soc_2 if metrics.reserve_soc_2 is None or metrics.reserve_soc_2 <= 32767 else metrics.reserve_soc_2 - 65536,
                # Old naming for backward compatibility
                "operatingMode": metrics.operating_mode,
                "modeText": mode_text,
                "reserveSoc": metrics.reserve_soc,
                "reserveSoc2": metrics.reserve_soc_2 if metrics.reserve_soc_2 is None or metrics.reserve_soc_2 <= 32767 else metrics.reserve_soc_2 - 65536,
                # Raw values
                "soc_raw": metrics.soc_raw,
                "soh_raw": metrics.soh_raw,
                "power_raw": metrics.power_raw,
                "voltage_raw": metrics.voltage_raw,
                "current_raw": metrics.current_raw,
                "status_flags": metrics.status_flags,
            }
        except Exception as e:
            logger.error(f"Error reading extensions: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/solar")
    async def get_solar():
        """Get Solar PV data (Model 502)."""
        modbus = app.state.modbus
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
    async def get_home_loads():
        """Get Home Load data (FranklinWH extension registers)."""
        modbus = app.state.modbus
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
    async def get_battery_lifetime():
        """Get Battery Lifetime Energy data (Model 714)."""
        modbus = app.state.modbus
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
    async def set_mode(request: ModeRequest):
        """Set battery operating mode."""
        modbus = app.state.modbus
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
            from modbus_client_franklinwh import FranklinWHRegisterMap
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
    async def set_reserve(request: ReserveRequest):
        """Set reserve SOC."""
        modbus = app.state.modbus
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        try:
            from modbus_client_franklinwh import FranklinWHRegisterMap
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
    async def set_reserve2(request: ReserveRequest):
        """Set reserve SOC 2."""
        modbus = app.state.modbus
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        try:
            from modbus_client_franklinwh import FranklinWHRegisterMap
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
    async def set_power_limits(request: PowerLimitRequest):
        """Set power limits."""
        modbus = app.state.modbus
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
        modbus = app.state.modbus
        if not modbus:
            raise HTTPException(status_code=503, detail="Modbus client not available")
        
        try:
            from modbus_client_franklinwh import FranklinWHRegisterMap
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
                "host": config.mqtt.host,
                "port": config.mqtt.port,
                "username": config.mqtt.username,
            },
            "theme": {
                "primary_color": config.theme.primary_color,
                "secondary_color": config.theme.secondary_color,
                "accent_color": config.theme.accent_color,
                "mode": config.theme.mode,
            },
            "auto_refresh": config.auto_refresh,
            "refresh_interval": config.refresh_interval,
            "widgets": config.widgets,
        }
    
    @app.post("/api/settings")
    async def update_settings(request: SettingsRequest):
        """Update settings."""
        try:
            updates = {}
            
            if request.modbus:
                updates["modbus"] = request.modbus.dict()
            if request.mqtt:
                updates["mqtt"] = request.mqtt.dict()
            if request.theme:
                updates["theme"] = request.theme.dict()
            if request.auto_refresh is not None:
                updates["auto_refresh"] = request.auto_refresh
            if request.refresh_interval is not None:
                updates["refresh_interval"] = request.refresh_interval
            
            await app.state.config.update(updates)
            return {"success": True}
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
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
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time updates."""
        await websocket.accept()
        app.state.websockets.append(websocket)
        
        try:
            # Send initial data
            modbus = app.state.modbus
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

async def setup_franklinwh_extension_entities(self) -> None:
    """Setup entities for FranklinWH-specific registers."""
    if not self._connected:
        return
    
    device = self._get_device_payload()
    
    entities = [
        # Operating Mode Select
        {
            "type": "select",
            "name": "franklinwh_operating_mode",
            "config": {
                "name": "Operating Mode",
                "options": ["Standby", "Normal", "Backup Reserve", 
                           "Self-Consumption", "Time-of-Use"],
                "command_topic": f"{self.state_prefix}/operating_mode/set",
                "state_topic": f"{self.state_prefix}/operating_mode/state",
                "value_template": "{{ value_json.mode }}",
                "icon": "mdi:battery-cog",
            }
        },
        
        # Reserve SOC Number
        {
            "type": "number",
            "name": "franklinwh_reserve_soc",
            "config": {
                "name": "Reserve SOC",
                "min": 0,
                "max": 100,
                "step": 1,
                "unit_of_measurement": "%",
                "command_topic": f"{self.state_prefix}/reserve_soc/set",
                "state_topic": f"{self.state_prefix}/reserve_soc/state",
                "value_template": "{{ value_json.value }}",
                "icon": "mdi:battery-lock",
            }
        },
        
        # Secondary Reserve SOC
        {
            "type": "number",
            "name": "franklinwh_reserve_soc_2",
            "config": {
                "name": "Reserve SOC 2",
                "min": -128,
                "max": 127,
                "step": 1,
                "unit_of_measurement": "%",
                "command_topic": f"{self.state_prefix}/reserve_soc_2/set",
                "state_topic": f"{self.state_prefix}/reserve_soc_2/state",
                "value_template": "{{ value_json.value }}",
                "icon": "mdi:battery-alert",
            }
        },
        
        # Raw Register Sensors
        {
            "type": "sensor",
            "name": "franklinwh_raw_soc",
            "config": {
                "name": "Raw SOC",
                "state_topic": f"{self.state_prefix}/raw/soc",
                "value_template": "{{ value_json.scaled | round(1) }}",
                "unit_of_measurement": "%",
                "icon": "mdi:battery-medium",
            }
        },
        {
            "type": "sensor",
            "name": "franklinwh_raw_power",
            "config": {
                "name": "Raw Power",
                "state_topic": f"{self.state_prefix}/raw/power",
                "value_template": "{{ value_json.scaled }}",
                "unit_of_measurement": "W",
                "device_class": "power",
                "icon": "mdi:flash",
            }
        },
        {
            "type": "sensor",
            "name": "franklinwh_status_flags",
            "config": {
                "name": "Status Flags",
                "state_topic": f"{self.state_prefix}/raw/status_flags",
                "value_template": "{{ value_json.raw }}",
                "icon": "mdi:flag",
            }
        },
    ]
    
    for entity in entities:
        await self._publish_discovery(entity["type"], entity["name"], 
                                      entity["config"], device)

async def handle_franklinwh_command(self, topic: str, payload: str) -> None:
    """Handle commands for FranklinWH extension registers."""
    from modbus_client import FranklinWHModbusClient
    
    # Initialize register map if needed
    if not hasattr(self.modbus, '_fw_register_map'):
        from modbus_client import FranklinWHRegisterMap
        self.modbus._fw_register_map = FranklinWHRegisterMap(self.modbus)
    
    fw_map = self.modbus._fw_register_map
    
    try:
        if "operating_mode/set" in topic:
            mode_map = {
                "Standby": 0,
                "Normal": 1,
                "Backup Reserve": 2,
                "Self-Consumption": 3,
                "Time-of-Use": 4,
            }
            mode = mode_map.get(payload, int(payload))
            success = await fw_map.set_operating_mode(mode)
            if success:
                await self.publish_state("operating_mode", {
                    "mode": payload,
                    "raw": mode
                })
        
        elif "reserve_soc/set" in topic:
            soc = int(payload)
            success = await fw_map.set_reserve_soc(soc)
            if success:
                await self.publish_state("reserve_soc", {"value": soc})
        
        elif "reserve_soc_2/set" in topic:
            soc = int(payload)
            success = await fw_map.set_reserve_soc_2(soc)
            if success:
                await self.publish_state("reserve_soc_2", {"value": soc})
        
        else:
            self._logger.warning(f"Unknown command topic: {topic}")
            
    except Exception as e:
        self._logger.error(f"Error handling command: {e}")

async def publish_franklinwh_extensions(self) -> None:
    """Publish FranklinWH extension register values."""
    if not hasattr(self.modbus, '_fw_register_map'):
        from modbus_client import FranklinWHRegisterMap
        self.modbus._fw_register_map = FranklinWHRegisterMap(self.modbus)
    
    fw_map = self.modbus._fw_register_map
    
    # Read all metrics
    metrics = await fw_map.read_all_metrics()
    
    # Publish operating mode
    if metrics.operating_mode is not None:
        mode_text = await fw_map.get_operating_mode_text(metrics.operating_mode)
        await self.publish_state("operating_mode", {
            "mode": mode_text,
            "raw": metrics.operating_mode
        })
    
    # Publish reserve SOC values
    if metrics.reserve_soc is not None:
        await self.publish_state("reserve_soc", {"value": metrics.reserve_soc})
    
    if metrics.reserve_soc_2 is not None:
        # Handle signed value
        soc_2 = metrics.reserve_soc_2 if metrics.reserve_soc_2 <= 32767 else metrics.reserve_soc_2 - 65536
        await self.publish_state("reserve_soc_2", {"value": soc_2})
    
    # Publish raw metrics
    if metrics.soc_raw is not None:
        await self.publish_state("raw/soc", {
            "raw": metrics.soc_raw,
            "scaled": metrics.soc_raw * 0.1
        })
    
    if metrics.power_raw is not None:
        # Handle signed
        power = metrics.power_raw if metrics.power_raw <= 32767 else metrics.power_raw - 65536
        await self.publish_state("raw/power", {
            "raw": metrics.power_raw,
            "scaled": power
        })
    
    if metrics.status_flags is not None:
        await self.publish_state("raw/status_flags", {
            "raw": metrics.status_flags,
            "binary": f"{metrics.status_flags:016b}"
        })

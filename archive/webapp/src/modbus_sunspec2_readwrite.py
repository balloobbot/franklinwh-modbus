import logging
from typing import Dict, List, Optional, Tuple, Set, Any
import sys
import sunspec2.modbus.client as client

# Add this near the top after the imports check
def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None):
    """
    Configure logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path to write logs to
    """
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Setup root logger
    logger = logging.getLogger()
    logger.setLevel(numeric_level)
    
    # Remove existing handlers
    logger.handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def write_sunspec_point(
    ip: str,
    model_id: int,
    point_name: str,
    value: Any,
    port: int = 502,
    unit: int = 1,
    timeout: float = 2.0,
    base_address: int = 40000,
    validate: bool = True,
    dry_run: bool = False,
    verbose: bool = False,
) -> Tuple[bool, Optional[str]]:
    """
    Write a value to a specific SunSpec point with validation.
    
    Args:
        ip: Device IP address
        model_id: SunSpec model ID
        point_name: Name of the point to write
        value: Value to write
        port: Modbus TCP port
        unit: Modbus unit ID
        timeout: Connection timeout
        base_address: Starting Modbus address
        validate: Perform validation before writing
        dry_run: Validate only, don't actually write
        verbose: Enable verbose output
        
    Returns:
        Tuple of (success, error_message)
    """
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Write request: {ip}:{port} Model {model_id}.{point_name} = {value}")
        
        # Connect to device
        logger.debug(f"Connecting to {ip}:{port} (unit={unit})")
        modbus_client = client.SunSpecModbusClientDeviceTCP(
            slave_id=unit,
            ipaddr=ip,
            ipport=port,
            timeout=timeout,
        )
        
        # Scan for models
        try:
            modbus_client.scan(base_addr=base_address)
        except TypeError:
            try:
                modbus_client.scan(base_address)
            except TypeError:
                try:
                    modbus_client.scan(address=base_address)
                except TypeError:
                    modbus_client.scan()
        
        logger.debug(f"Available models: {list(modbus_client.models.keys())}")
        
        # Get the model
        model = modbus_client.models.get(model_id)
        if model is None:
            model = modbus_client.models.get(str(model_id))
        
        if model is None:
            error = f"Model {model_id} not found on device"
            logger.error(error)
            modbus_client.close()
            return False, error
        
        # Handle list of models (use first instance)
        if isinstance(model, list):
            if len(model) == 0:
                error = f"Model {model_id} list is empty"
                logger.error(error)
                modbus_client.close()
                return False, error
            model = model[0]
            logger.debug(f"Using first instance of model {model_id}")
        
        # Read current model state
        logger.debug(f"Reading model {model_id}")
        model.read()
        
        # Get the point
        point = getattr(model, point_name, None)
        if point is None:
            error = f"Point {point_name} not found in model {model_id}"
            logger.error(error)
            modbus_client.close()
            return False, error
        
        # Perform validation if requested
        if validate:
            logger.debug(f"Validating write to {point_name}")
            
            # Check if point has definition
            if not hasattr(point, "pdef"):
                error = f"Point {point_name} has no definition metadata"
                logger.warning(error)
            else:
                pdef = point.pdef
                
                # Check write access
                if hasattr(pdef, "access"):
                    access = pdef.access
                    logger.debug(f"Point access level: {access}")
                    if access not in ["rw", "w"]:
                        error = f"Point {point_name} is read-only (access={access})"
                        logger.error(error)
                        modbus_client.close()
                        return False, error
                else:
                    logger.warning(f"Point {point_name} has no access attribute")
                
                # Check type compatibility
                if hasattr(pdef, "type"):
                    point_type = pdef.type
                    logger.debug(f"Point type: {point_type}")
                    
                    # Basic type validation
                    if "int" in str(point_type).lower():
                        try:
                            int(value)
                        except (ValueError, TypeError):
                            error = f"Value {value} is not valid for type {point_type}"
                            logger.error(error)
                            modbus_client.close()
                            return False, error
                
                # Check min/max range
                if hasattr(pdef, "min") and pdef.min is not None:
                    if value < pdef.min:
                        error = f"Value {value} below minimum {pdef.min}"
                        logger.error(error)
                        modbus_client.close()
                        return False, error
                
                if hasattr(pdef, "max") and pdef.max is not None:
                    if value > pdef.max:
                        error = f"Value {value} above maximum {pdef.max}"
                        logger.error(error)
                        modbus_client.close()
                        return False, error
                
                # Check enum/bitmap symbols
                if hasattr(pdef, "symbols") and pdef.symbols:
                    valid_values = list(pdef.symbols.keys())
                    if value not in valid_values:
                        error = f"Value {value} not in valid set: {valid_values}"
                        logger.error(error)
                        modbus_client.close()
                        return False, error
                    logger.debug(f"Value {value} = '{pdef.symbols[value]}'")
        
        # Perform write (unless dry run)
        if dry_run:
            logger.info(f"DRY RUN: Would write {value} to {model_id}.{point_name}")
            modbus_client.close()
            return True, "Dry run successful - validation passed"
        
        logger.info(f"Writing value {value} to {model_id}.{point_name}")
        old_value = getattr(point, "value", None)
        
        # Set the value
        point.value = value
        
        # Write the model back
        model.write()
        
        logger.info(f"Write successful: {point_name} changed from {old_value} to {value}")
        
        modbus_client.close()
        return True, None
        
    except Exception as e:
        error = f"Write failed: {str(e)}"
        logger.exception(error)
        return False, error


def batch_read_points(
    ip: str,
    points_to_read: List[Tuple[int, str]],
    port: int = 502,
    unit: int = 1,
    timeout: float = 2.0,
    base_address: int = 40000,
    include_metadata: bool = False,
    verbose: bool = False,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Read multiple points from SunSpec device efficiently.
    
    Args:
        ip: Device IP address
        points_to_read: List of (model_id, point_name) tuples
        port: Modbus TCP port
        unit: Modbus unit ID
        timeout: Connection timeout
        base_address: Starting Modbus address
        include_metadata: Include point metadata in results
        verbose: Enable verbose output
        
    Returns:
        Tuple of (results dict, error message)
        Results format: {
            "model_id.point_name": {
                "value": value,
                "model_id": model_id,
                "point_name": point_name,
                "metadata": {...}  # if include_metadata=True
            }
        }
    """
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Batch read: {len(points_to_read)} points from {ip}:{port}")
        
        # Connect to device
        logger.debug(f"Connecting to {ip}:{port} (unit={unit})")
        modbus_client = client.SunSpecModbusClientDeviceTCP(
            slave_id=unit,
            ipaddr=ip,
            ipport=port,
            timeout=timeout,
        )
        
        # Scan for models
        try:
            modbus_client.scan(base_addr=base_address)
        except TypeError:
            try:
                modbus_client.scan(base_address)
            except TypeError:
                try:
                    modbus_client.scan(address=base_address)
                except TypeError:
                    modbus_client.scan()
        
        # Group points by model for efficient reading
        points_by_model = {}
        for model_id, point_name in points_to_read:
            if model_id not in points_by_model:
                points_by_model[model_id] = []
            points_by_model[model_id].append(point_name)
        
        logger.debug(f"Reading from {len(points_by_model)} models")
        
        results = {}
        
        # Read each model once
        for model_id, point_names in points_by_model.items():
            logger.debug(f"Reading model {model_id} with {len(point_names)} points")
            
            # Get the model
            model = modbus_client.models.get(model_id)
            if model is None:
                model = modbus_client.models.get(str(model_id))
            
            if model is None:
                logger.warning(f"Model {model_id} not found, skipping")
                for point_name in point_names:
                    key = f"{model_id}.{point_name}"
                    results[key] = {
                        "value": None,
                        "model_id": model_id,
                        "point_name": point_name,
                        "error": "Model not found"
                    }
                continue
            
            # Handle list of models (use first instance)
            if isinstance(model, list):
                if len(model) == 0:
                    logger.warning(f"Model {model_id} list is empty")
                    continue
                model = model[0]
            
            # Read the entire model once
            model.read()
            logger.debug(f"Model {model_id} read complete")
            
            # Extract requested points
            for point_name in point_names:
                key = f"{model_id}.{point_name}"
                point = getattr(model, point_name, None)
                
                if point is None:
                    logger.warning(f"Point {point_name} not found in model {model_id}")
                    results[key] = {
                        "value": None,
                        "model_id": model_id,
                        "point_name": point_name,
                        "error": "Point not found"
                    }
                    continue
                
                result = {
                    "value": getattr(point, "value", None),
                    "model_id": model_id,
                    "point_name": point_name,
                }
                
                # Add metadata if requested
                if include_metadata and hasattr(point, "pdef"):
                    pdef = point.pdef
                    metadata = {}
                    
                    for attr in ["type", "units", "label", "desc", "access", 
                                 "sf", "size", "mandatory"]:
                        if hasattr(pdef, attr):
                            metadata[attr] = getattr(pdef, attr)
                    
                    if hasattr(pdef, "symbols") and pdef.symbols:
                        metadata["symbols"] = dict(pdef.symbols)
                    
                    result["metadata"] = metadata
                
                results[key] = result
                logger.debug(f"Read {key} = {result['value']}")
        
        modbus_client.close()
        logger.info(f"Batch read complete: {len(results)} points")
        return results, None
        
    except Exception as e:
        error = f"Batch read failed: {str(e)}"
        logger.exception(error)
        return None, error


def batch_write_points(
    ip: str,
    points_to_write: List[Tuple[int, str, Any]],
    port: int = 502,
    unit: int = 1,
    timeout: float = 2.0,
    base_address: int = 40000,
    validate: bool = True,
    dry_run: bool = False,
    atomic: bool = True,
    verbose: bool = False,
) -> Tuple[Dict[str, bool], Optional[str]]:
    """
    Write multiple points to SunSpec device efficiently.
    
    Args:
        ip: Device IP address
        points_to_write: List of (model_id, point_name, value) tuples
        port: Modbus TCP port
        unit: Modbus unit ID
        timeout: Connection timeout
        base_address: Starting Modbus address
        validate: Perform validation before writing
        dry_run: Validate only, don't actually write
        atomic: If True, validate ALL before writing ANY (recommended)
        verbose: Enable verbose output
        
    Returns:
        Tuple of (results dict, error message)
        Results format: {"model_id.point_name": True/False}
    """
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Batch write: {len(points_to_write)} points to {ip}:{port}")
        
        # Connect to device
        logger.debug(f"Connecting to {ip}:{port} (unit={unit})")
        modbus_client = client.SunSpecModbusClientDeviceTCP(
            slave_id=unit,
            ipaddr=ip,
            ipport=port,
            timeout=timeout,
        )
        
        # Scan for models
        try:
            modbus_client.scan(base_addr=base_address)
        except TypeError:
            try:
                modbus_client.scan(base_address)
            except TypeError:
                try:
                    modbus_client.scan(address=base_address)
                except TypeError:
                    modbus_client.scan()
        
        # Group points by model
        points_by_model = {}
        for model_id, point_name, value in points_to_write:
            if model_id not in points_by_model:
                points_by_model[model_id] = []
            points_by_model[model_id].append((point_name, value))
        
        logger.debug(f"Writing to {len(points_by_model)} models")
        
        results = {}
        validation_errors = []
        
        # Phase 1: Validate all points (if atomic mode)
        if atomic and validate:
            logger.info("Phase 1: Validating all points")
            
            for model_id, point_values in points_by_model.items():
                # Get the model
                model = modbus_client.models.get(model_id)
                if model is None:
                    model = modbus_client.models.get(str(model_id))
                
                if model is None:
                    for point_name, value in point_values:
                        key = f"{model_id}.{point_name}"
                        error = f"Model {model_id} not found"
                        validation_errors.append((key, error))
                    continue
                
                # Handle list of models
                if isinstance(model, list):
                    if len(model) == 0:
                        continue
                    model = model[0]
                
                # Read model
                model.read()
                
                # Validate each point
                for point_name, value in point_values:
                    key = f"{model_id}.{point_name}"
                    point = getattr(model, point_name, None)
                    
                    if point is None:
                        validation_errors.append((key, f"Point not found"))
                        continue
                    
                    # Validation checks
                    if hasattr(point, "pdef"):
                        pdef = point.pdef
                        
                        # Check write access
                        if hasattr(pdef, "access"):
                            if pdef.access not in ["rw", "w"]:
                                validation_errors.append(
                                    (key, f"Read-only (access={pdef.access})")
                                )
                                continue
                        
                        # Check min/max
                        if hasattr(pdef, "min") and pdef.min is not None:
                            if value < pdef.min:
                                validation_errors.append(
                                    (key, f"Below minimum {pdef.min}")
                                )
                                continue
                        
                        if hasattr(pdef, "max") and pdef.max is not None:
                            if value > pdef.max:
                                validation_errors.append(
                                    (key, f"Above maximum {pdef.max}")
                                )
                                continue
                        
                        # Check enum values
                        if hasattr(pdef, "symbols") and pdef.symbols:
                            if value not in pdef.symbols.keys():
                                validation_errors.append(
                                    (key, f"Invalid enum value")
                                )
                                continue
            
            # If any validation errors in atomic mode, abort
            if validation_errors:
                logger.error(f"Validation failed for {len(validation_errors)} points")
                for key, error in validation_errors:
                    logger.error(f"  {key}: {error}")
                    results[key] = False
                
                modbus_client.close()
                return results, f"Validation failed: {len(validation_errors)} errors"
            
            logger.info("All points validated successfully")
        
        # Phase 2: Perform writes (unless dry run)
        if dry_run:
            logger.info("DRY RUN: Validation passed, no writes performed")
            for model_id, point_values in points_by_model.items():
                for point_name, value in point_values:
                    key = f"{model_id}.{point_name}"
                    results[key] = True
            modbus_client.close()
            return results, None
        
        logger.info("Phase 2: Writing all points")
        
        # Write each model
        for model_id, point_values in points_by_model.items():
            logger.debug(f"Writing to model {model_id}")
            
            # Get the model
            model = modbus_client.models.get(model_id)
            if model is None:
                model = modbus_client.models.get(str(model_id))
            
            if model is None:
                for point_name, value in point_values:
                    key = f"{model_id}.{point_name}"
                    results[key] = False
                continue
            
            # Handle list of models
            if isinstance(model, list):
                if len(model) == 0:
                    continue
                model = model[0]
            
            # Read current state
            model.read()
            
            # Set all point values for this model
            for point_name, value in point_values:
                key = f"{model_id}.{point_name}"
                point = getattr(model, point_name, None)
                
                if point is None:
                    logger.warning(f"Point {key} not found")
                    results[key] = False
                    continue
                
                old_value = getattr(point, "value", None)
                point.value = value
                logger.debug(f"Set {key}: {old_value} -> {value}")
            
            # Write entire model at once
            try:
                model.write()
                logger.info(f"Model {model_id} written successfully")
                
                # Mark all points as successful
                for point_name, value in point_values:
                    key = f"{model_id}.{point_name}"
                    results[key] = True
                    
            except Exception as e:
                logger.error(f"Failed to write model {model_id}: {e}")
                for point_name, value in point_values:
                    key = f"{model_id}.{point_name}"
                    results[key] = False
        
        modbus_client.close()
        logger.info(f"Batch write complete: {sum(results.values())}/{len(results)} successful")
        return results, None
        
    except Exception as e:
        error = f"Batch write failed: {str(e)}"
        logger.exception(error)
        return {}, error

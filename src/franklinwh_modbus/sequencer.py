"""
SunSpec InfoPoint Sequencer
Executes deterministic sequences of SunSpec register operations with verification.
"""

import logging
import time
from typing import Dict, List, Any, Optional, Tuple

try:
    import sunspec2.modbus.client as client
except ImportError:
    client = None

logger = logging.getLogger(__name__)

class SunSpecSequencer:
    """Orchestrates multi-step SunSpec operations."""
    
    def __init__(self, device: Any, base_address: int = 0):
        """
        Initialize with a sunspec2 device object.
        
        Args:
            device: An instance of SunSpecModbusClientDeviceTCP (or similar)
                   that has already been scanned.
            base_address: The starting Modbus address used for scanning.
        """
        self.device = device
        self.base_address = base_address
        self.verbose = False

    def get_point(self, tag: str) -> Tuple[Any, Any]:
        """Resolve 'Model.Point' tag to (model_obj, point_obj)."""
        try:
            model_id_str, point_name = tag.split('.')
            model_id = int(model_id_str)
        except ValueError:
            raise ValueError(f"Invalid tag format '{tag}'. Use 'ModelID.PointName' (e.g. 704.WSetPct)")

        model = self.device.models.get(model_id)
        if model is None:
            model = self.device.models.get(str(model_id))
        
        if model is None:
            raise ValueError(f"Model {model_id} not found on device")
        
        if isinstance(model, list):
            model = model[0]
            
        point = getattr(model, point_name, None)
        if point is None:
            raise ValueError(f"Point '{point_name}' not found in Model {model_id}")
            
        return model, point

    def get_point_val(self, model: Any, point: Any) -> Any:
        """Helper to get scaled value from a point."""
        val = point.value
        if val is None:
            return None
            
        # Robust point definition attribute access
        pdef = point.pdef
        def get_attr(obj, key):
            if isinstance(obj, dict): return obj.get(key)
            return getattr(obj, key, None)
            
        sf_name = get_attr(pdef, 'sf')
        if sf_name:
            sf_point = getattr(model, sf_name, None)
            if sf_point:
                sf_val = sf_point.value
                if sf_val is not None:
                    # Apply scale factor: value * 10^sf
                    return val * (10 ** sf_val)
        return val

    def read_value(self, tag: str) -> Any:
        model, point = self.get_point(tag)
        model.read()
        return self.get_point_val(model, point)

    def write_value(self, tag: str, human_val: Any) -> Any:
        """Write a value, applying scale factor conversion if needed."""
        model, point = self.get_point(tag)
        
        raw_val = human_val
        pdef = point.pdef
        
        def get_attr(obj, key):
            if isinstance(obj, dict): return obj.get(key)
            return getattr(obj, key, None)
            
        sf_name = get_attr(pdef, 'sf')
        if sf_name:
            sf_point = getattr(model, sf_name, None)
            if sf_point:
                model.read() # Ensure we have the latest SF
                sf_val = sf_point.value
                if sf_val is not None:
                    # Inverse scale factor: raw = human / 10^sf
                    raw_val = int(human_val / (10 ** sf_val))
                    
        point.value = raw_val
        model.write()
        return raw_val

    def run_sequence(self, sequence: List[Dict[str, Any]], dry_run: bool = False) -> bool:
        """Execute a list of step dictionaries."""
        total_steps = len(sequence)
        logger.info(f"Starting sequence with {total_steps} steps...")
        
        for i, step in enumerate(sequence):
            step_name = step.get('name', step.get('step', f"Step {i+1}"))
            logger.info(f"\n--- [{i+1}/{total_steps}] {step_name} ---")
            
            # 1. Handle Writes
            writes = step.get('writes', {})
            if writes:
                if not self.execute_writes(writes, step, dry_run):
                    if step.get('abort_on_failure', True):
                        logger.error(f"Aborting sequence due to write failure in '{step_name}'")
                        return False

            # 2. Handle Wait For (Polling Loop)
            wait_for = step.get('wait_for')
            if wait_for:
                if not self.execute_wait_for(wait_for, step_name):
                    if step.get('abort_on_failure', True):
                        logger.error(f"Aborting sequence due to wait condition failure in '{step_name}'")
                        return False

            # 3. Handle Reads
            reads = step.get('reads', [])
            if reads:
                self.execute_reads(reads)

            # 4. Handle Sleep
            sleep_ms = step.get('sleep_ms', step.get('post_sleep_ms', 0))
            if sleep_ms > 0:
                logger.info(f"Sleeping for {sleep_ms}ms...")
                time.sleep(sleep_ms / 1000.0)
            
            # Step completion summary (especially useful if logs are suppressed)
            if logger.level > logging.INFO:
                print(f"DONE: {step_name}")

        logger.info("\nSequence complete.")
        return True

    def execute_writes(self, writes: Dict[str, Any], step: Dict[str, Any], dry_run: bool) -> bool:
        verify = step.get('verify', True)
        timeout_ms = step.get('verify_timeout_ms', 2000)
        
        # Capture "Before" state
        before_vals = {}
        for tag in writes:
            try:
                before_vals[tag] = self.read_value(tag)
            except Exception as e:
                logger.warning(f"  Could not read initial value for {tag}: {e}")
                before_vals[tag] = "Unknown"

        if dry_run:
            for tag, val in writes.items():
                logger.info(f"  [DRY RUN] Would write {tag}: {before_vals[tag]} -> {val}")
            return True

        # Perform writes (grouped by model for efficiency)
        models_to_write = {}
        
        def get_attr(obj, key):
            if isinstance(obj, dict): return obj.get(key)
            return getattr(obj, key, None)

        for tag, val in writes.items():
            model, point = self.get_point(tag)
            model_id = int(tag.split('.')[0])
            if model not in models_to_write:
                models_to_write[model] = []
            
            # Resolve raw value
            raw_val = val
            pdef = point.pdef
            sf_name = get_attr(pdef, 'sf')
            if sf_name:
                sf_point = getattr(model, sf_name, None)
                if sf_point:
                    model.read()
                    sf_val = sf_point.value
                    if sf_val is not None:
                        raw_val = int(val / (10 ** sf_val))
            
            # Get address for logging
            pdef = point.pdef
            offset = getattr(point, 'offset', get_attr(pdef, 'offset'))
            
            # Derive absolute address
            addr = getattr(point, 'addr', None)
            if addr is None:
                # Calculate: Device Base + Model Offset + Point Offset
                # We use the base_address provided to the sequencer or controller
                d_base = getattr(self.device, 'base_addr', 0)
                if d_base == 0:
                    # Fallback to checking if we have it stored elsewhere
                    d_base = getattr(self, 'base_address', 0)
                
                m_off = getattr(model, 'model_addr', getattr(model, 'addr', 0))
                if offset is not None:
                    addr = d_base + m_off + offset
            
            addr_str = f"{addr}" if addr is not None else "???"
            logger.info(f"  Writing {tag} (Model {model_id}) = {val} [Raw: {raw_val}, Addr: {addr_str}]")
            models_to_write[model].append((point, raw_val))

        for model, points in models_to_write.items():
            for point, raw_val in points:
                point.value = raw_val
            model.write()

        # Verification
        if not verify:
            for tag, val in writes.items():
                logger.info(f"  Write {tag}: {before_vals.get(tag)} -> {val} [SENT]")
            return True

        start_time = time.time()
        deadline = start_time + (timeout_ms / 1000.0)
        pending = list(writes.keys())
        
        logger.info("  Verifying writes...")
        while pending and time.time() < deadline:
            for tag in list(pending):
                current = self.read_value(tag)
                target = writes[tag]
                
                if current == target:
                    elapsed = int((time.time() - start_time) * 1000)
                    logger.info(f"  ✓ {tag}: {before_vals.get(tag)} -> {current} [VERIFIED in {elapsed}ms]")
                    pending.remove(tag)
            
            if pending:
                time.sleep(0.1)

        if pending:
            for tag in pending:
                current = self.read_value(tag)
                logger.error(f"  ✗ {tag}: Update failure. Current: {current}, Expected: {writes[tag]}")
            return False
        
        return True

    def execute_wait_for(self, config: Dict[str, Any], step_name: str) -> bool:
        """Poll a point until a condition is met."""
        tag = config.get('point')
        op = config.get('operator', '==')
        target = config.get('value')
        timeout_ms = config.get('timeout_ms', 30000)
        poll_ms = config.get('poll_ms', 1000)
        
        if not tag:
            logger.error("  wait_for missing 'point'")
            return False
            
        logger.info(f"  Waiting for {tag} {op} {target} (timeout: {timeout_ms}ms)...")
        
        start_time = time.time()
        deadline = start_time + (timeout_ms / 1000.0)
        
        while time.time() < deadline:
            try:
                current = self.read_value(tag)
                
                # Evaluation
                satisfied = False
                if op == '==': satisfied = (current == target)
                elif op == '!=': satisfied = (current != target)
                elif op == '>': satisfied = (current > target)
                elif op == '<': satisfied = (current < target)
                elif op == '>=': satisfied = (current >= target)
                elif op == '<=': satisfied = (current <= target)
                elif op == 'in': satisfied = (current in target)
                elif op == 'not in': satisfied = (current not in target)
                else:
                    logger.error(f"  Unsupported operator '{op}'")
                    return False
                    
                if satisfied:
                    elapsed = int((time.time() - start_time) * 1000)
                    logger.info(f"  ✓ Condition met: {current} {op} {target} [after {elapsed}ms]")
                    return True
                
                if self.verbose:
                    logger.info(f"    Current: {current} (target: {target})")
                    
            except Exception as e:
                logger.warning(f"  Polling {tag} failed: {e}")
                
            time.sleep(poll_ms / 1000.0)
            
        logger.error(f"  ✗ Timeout waiting for {tag} {op} {target}")
        return False

    def execute_reads(self, tags: List[str]):
        for tag in tags:
            try:
                val = self.read_value(tag)
                model, point = self.get_point(tag)
                meaning = ""
                if hasattr(point, 'pdef') and hasattr(point.pdef, 'symbols'):
                    meaning = f" ({point.pdef.symbols.get(val, 'Unknown')})"
                logger.info(f"  Read {tag}: {val}{meaning}")
            except Exception as e:
                logger.error(f"  Read {tag} failed: {e}")

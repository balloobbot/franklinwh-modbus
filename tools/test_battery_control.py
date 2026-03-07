#!/usr/bin/env python3
"""
Safe Battery Control Testing Script

Tests SunSpec2 Model 702/704 write operations for power limiting control.
Implements safety checks and rollback mechanisms.

SAFETY WARNINGS:
- Model 703.ES: Controls GRID RELAY - can disconnect grid power!
- ALWAYS test with UPS protection on controlling device
- ALWAYS verify current values before writing
- ALWAYS implement rollback on unexpected behavior

Test Sequence:
1. Read-only baseline (no writes)
2. Model 702: Charge/Discharge limits
3. Model 704: Percentage-based limiting
4. (SKIP Model 703.ES - grid disconnect risk)
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from modbus_client import FranklinWHModbusClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("battery_control_test")


class BatteryControlTester:
    """Safe battery control testing with rollback"""
    
    def __init__(self, host: str = "192.168.0.110", port: int = 502):
        self.host = host
        self.port = port
        self.client = None
        self.original_values = {}
        
    async def connect(self):
        """Connect to aGate"""
        logger.info(f"Connecting to {self.host}:{self.port}")
        self.client = FranklinWHModbusClient(
            host=self.host,
            port=self.port,
            unit_id=1,
            timeout=5.0
        )
        await self.client.connect()
        logger.info("✅ Connected successfully")
        
    async def disconnect(self):
        """Disconnect from aGate"""
        if self.client:
            await self.client.disconnect()
            logger.info("Disconnected")
    
    async def read_baseline(self):
        """Read and store current values (no writes)"""
        logger.info("\n" + "="*70)
        logger.info("PHASE 1: READ BASELINE (No Writes)")
        logger.info("="*70)
        
        try:
            # Model 702: Capacity and Limits
            model_702 = await self.client.get_model(702)
            if model_702:
                logger.info("\n📊 Model 702 (DER Capacity):")
                
                # Read ratings (hardware limits)
                w_cha_rte_max_rtg = model_702.points.get('WChaRteMaxRtg', {}).get('value')
                w_dis_cha_rte_max_rtg = model_702.points.get('WDisChaRteMaxRtg', {}).get('value')
                
                logger.info(f"  WChaRteMaxRtg (Rated Charge Max):     {w_cha_rte_max_rtg} W")
                logger.info(f"  WDisChaRteMaxRtg (Rated Discharge Max): {w_dis_cha_rte_max_rtg} W")
                
                # Read current settings
                w_cha_rte_max = model_702.points.get('WChaRteMax', {}).get('value')
                w_dis_cha_rte_max = model_702.points.get('WDisChaRteMax', {}).get('value')
                
                logger.info(f"  WChaRteMax (Current Charge Limit):     {w_cha_rte_max} W")
                logger.info(f"  WDisChaRteMax (Current Discharge Limit): {w_dis_cha_rte_max} W")
                
                # Store for rollback
                self.original_values['702.WChaRteMax'] = w_cha_rte_max
                self.original_values['702.WDisChaRteMax'] = w_dis_cha_rte_max
                self.original_values['702.WChaRteMaxRtg'] = w_cha_rte_max_rtg
                self.original_values['702.WDisChaRteMaxRtg'] = w_dis_cha_rte_max_rtg
            
            # Model 704: DER AC Controls
            model_704 = await self.client.get_model(704)
            if model_704:
                logger.info("\n📊 Model 704 (DER AC Controls):")
                
                w_max_lim_pct_ena = model_704.points.get('WMaxLimPctEna', {}).get('value')
                w_max_lim_pct = model_704.points.get('WMaxLimPct', {}).get('value')
                w_set_ena = model_704.points.get('WSetEna', {}).get('value')
                w_set_mod = model_704.points.get('WSetMod', {}).get('value')
                
                logger.info(f"  WMaxLimPctEna (Limit Enable):  {w_max_lim_pct_ena}")
                logger.info(f"  WMaxLimPct (Limit %):          {w_max_lim_pct}")
                logger.info(f"  WSetEna (Setpoint Enable):     {w_set_ena}")
                logger.info(f"  WSetMod (Setpoint Mode):       {w_set_mod}")
                
                # Store for rollback
                self.original_values['704.WMaxLimPctEna'] = w_max_lim_pct_ena
                self.original_values['704.WMaxLimPct'] = w_max_lim_pct
                self.original_values['704.WSetEna'] = w_set_ena
                self.original_values['704.WSetMod'] = w_set_mod
            
            # Model 714: Current Power (for monitoring)
            model_714 = await self.client.get_model(714)
            if model_714:
                logger.info("\n📊 Model 714 (DC Measurement):")
                w = model_714.points.get('W', {}).get('value')
                logger.info(f"  W (Current Power): {w} W (+ = discharge, - = charge)")
                
            logger.info("\n✅ Baseline read complete")
            
        except Exception as e:
            logger.error(f"❌ Error reading baseline: {e}")
            raise
    
    async def test_model_702_limits(self, charge_limit_w: int = 2500, discharge_limit_w: int = 3000):
        """Test Model 702 charge/discharge limits"""
        logger.info("\n" + "="*70)
        logger.info("PHASE 2: TEST Model 702 Power Limits")
        logger.info("="*70)
        logger.info(f"Target: Charge={charge_limit_w}W, Discharge={discharge_limit_w}W")
        
        try:
            model_702 = await self.client.get_model(702)
            if not model_702:
                logger.error("❌ Model 702 not available")
                return False
            
            # Validate limits are within ratings
            max_charge = self.original_values.get('702.WChaRteMaxRtg', 5000)
            max_discharge = self.original_values.get('702.WDisChaRteMaxRtg', 5000)
            
            if charge_limit_w > max_charge or discharge_limit_w > max_discharge:
                logger.error(f"❌ Limits exceed ratings! Max charge: {max_charge}W, Max discharge: {max_discharge}W")
                return False
            
            # Confirm with user
            logger.warning(f"\n⚠️  ABOUT TO WRITE:")
            logger.warning(f"   WChaRteMax: {self.original_values['702.WChaRteMax']} → {charge_limit_w} W")
            logger.warning(f"   WDisChaRteMax: {self.original_values['702.WDisChaRteMax']} → {discharge_limit_w} W")
            
            response = input("\n   Proceed with write? (yes/no): ")
            if response.lower() != 'yes':
                logger.info("❌ User cancelled")
                return False
            
            # WRITE OPERATION
            logger.info("\n📝 Writing new limits...")
            model_702.points['WChaRteMax']['value'] = charge_limit_w
            model_702.points['WDisChaRteMax']['value'] = discharge_limit_w
            
            # Execute write
            await asyncio.get_event_loop().run_in_executor(None, model_702.write)
            logger.info("✅ Write successful")
            
            # Read back to verify
            await asyncio.sleep(1)
            model_702_verify = await self.client.get_model(702)
            new_charge = model_702_verify.points.get('WChaRteMax', {}).get('value')
            new_discharge = model_702_verify.points.get('WDisChaRteMax', {}).get('value')
            
            logger.info(f"\n✅ Verification:")
            logger.info(f"   WChaRteMax: {new_charge} W (expected: {charge_limit_w})")
            logger.info(f"   WDisChaRteMax: {new_discharge} W (expected: {discharge_limit_w})")
            
            if new_charge == charge_limit_w and new_discharge == discharge_limit_w:
                logger.info("✅ Write confirmed successful!")
                return True
            else:
                logger.warning("⚠️  Values don't match - unexpected behavior")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error writing Model 702 limits: {e}")
            return False
    
    async def test_model_704_percent_limit(self, limit_pct: int = 50):
        """Test Model 704 percentage-based limiting"""
        logger.info("\n" + "="*70)
        logger.info("PHASE 3: TEST Model 704 Percentage Limit")
        logger.info("="*70)
        logger.info(f"Target: {limit_pct}% power limit")
        
        try:
            model_704 = await self.client.get_model(704)
            if not model_704:
                logger.error("❌ Model 704 not available")
                return False
            
            # Get scale factor
            scale_factor = model_704.points.get('WMaxLimPct_SF', {}).get('value', -2)
            scaled_value = limit_pct * (10 ** (-1 * scale_factor))  # e.g., 50 * 100 = 5000
            
            logger.warning(f"\n⚠️  ABOUT TO WRITE:")
            logger.warning(f"   WMaxLimPctEna: {self.original_values['704.WMaxLimPctEna']} → 1 (ENABLED)")
            logger.warning(f"   WMaxLimPct: {self.original_values['704.WMaxLimPct']} → {scaled_value} ({limit_pct}%)")
            
            response = input("\n   Proceed with write? (yes/no): ")
            if response.lower() != 'yes':
                logger.info("❌ User cancelled")
                return False
            
            # WRITE OPERATION
            logger.info("\n📝 Writing percentage limit...")
            model_704.points['WMaxLimPctEna']['value'] = 1
            model_704.points['WMaxLimPct']['value'] = scaled_value
            
            # Execute write
            await asyncio.get_event_loop().run_in_executor(None, model_704.write)
            logger.info("✅ Write successful")
            
            # Read back to verify
            await asyncio.sleep(1)
            model_704_verify = await self.client.get_model(704)
            new_ena = model_704_verify.points.get('WMaxLimPctEna', {}).get('value')
            new_pct = model_704_verify.points.get('WMaxLimPct', {}).get('value')
            
            logger.info(f"\n✅ Verification:")
            logger.info(f"   WMaxLimPctEna: {new_ena} (expected: 1)")
            logger.info(f"   WMaxLimPct: {new_pct} (expected: {scaled_value})")
            
            if new_ena == 1 and new_pct == scaled_value:
                logger.info("✅ Write confirmed successful!")
                return True
            else:
                logger.warning("⚠️  Values don't match - unexpected behavior")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error writing Model 704 limit: {e}")
            return False
    
    async def monitor_power(self, duration_seconds: int = 30):
        """Monitor battery power for specified duration"""
        logger.info(f"\n📊 Monitoring power for {duration_seconds} seconds...")
        
        for i in range(duration_seconds):
            try:
                model_714 = await self.client.get_model(714)
                if model_714:
                    w = model_714.points.get('W', {}).get('value', 0)
                    direction = "charging" if w < 0 else "discharging" if w > 0 else "idle"
                    logger.info(f"  [{i+1:2d}s] Power: {w:6d} W ({direction})")
            except Exception as e:
                logger.warning(f"  [{i+1:2d}s] Error reading power: {e}")
            
            await asyncio.sleep(1)
    
    async def test_timeout_behavior(self, duration_minutes: int = 10):
        """Test if aGate disconnects after timeout without heartbeat"""
        logger.info("\n" + "="*70)
        logger.info("PHASE 4: TEST Timeout Behavior (No Heartbeat)")
        logger.info("="*70)
        logger.info(f"Testing if limits persist for {duration_minutes} minutes without writes")
        logger.info("This tests if FranklinWH requires heartbeat maintenance")
        
        duration_seconds = duration_minutes * 60
        
        try:
            # Check limits are still applied
            model_702 = await self.client.get_model(702)
            if model_702:
                current_charge = model_702.points.get('WChaRteMax', {}).get('value')
                current_discharge = model_702.points.get('WDisChaRteMax', {}).get('value')
                logger.info(f"\nCurrent limits at start:")
                logger.info(f"  Charge: {current_charge} W")
                logger.info(f"  Discharge: {current_discharge} W")
            
            # Monitor for extended period WITHOUT ANY WRITES
            logger.info(f"\n⏱️  Idle monitoring for {duration_minutes} minutes...")
            logger.info("   (No heartbeat writes - testing auto-disconnect)")
            
            for minute in range(duration_minutes):
                logger.info(f"\n--- Minute {minute + 1}/{duration_minutes} ---")
                
                # Read power every 15 seconds
                for quarter in range(4):
                    try:
                        model_714 = await self.client.get_model(714)
                        if model_714:
                            w = model_714.points.get('W', {}).get('value', 0)
                            direction = "charging" if w < 0 else "discharging" if w > 0 else "idle"
                            logger.info(f"  [{minute}:{quarter*15:02d}] Power: {w:6d} W ({direction})")
                    except Exception as e:
                        logger.error(f"  ❌ Connection lost at {minute}:{quarter*15:02d}! Error: {e}")
                        logger.error("  This may indicate auto-disconnect triggered")
                        return False
                    
                    await asyncio.sleep(15)
                
                # Check if limits are still applied (every minute)
                try:
                    model_702_check = await self.client.get_model(702)
                    if model_702_check:
                        check_charge = model_702_check.points.get('WChaRteMax', {}).get('value')
                        check_discharge = model_702_check.points.get('WDisChaRteMax', {}).get('value')
                        
                        if check_charge != current_charge or check_discharge != current_discharge:
                            logger.warning(f"\n⚠️  LIMITS CHANGED!")
                            logger.warning(f"   Charge: {current_charge} → {check_charge} W")
                            logger.warning(f"   Discharge: {current_discharge} → {check_discharge} W")
                            logger.warning(f"   Possible auto-revert after {minute + 1} minutes")
                            return False
                        else:
                            logger.info(f"  ✅ Limits still applied: {check_charge}W / {check_discharge}W")
                except Exception as e:
                    logger.error(f"  ❌ Cannot verify limits: {e}")
                    return False
            
            logger.info(f"\n✅ SUCCESS: Limits persisted for {duration_minutes} minutes without heartbeat")
            logger.info("   FranklinWH does NOT require heartbeat maintenance!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error during timeout test: {e}")
            return False
    
    async def rollback_to_original(self):
        """Restore original values"""
        logger.info("\n" + "="*70)
        logger.info("ROLLBACK: Restoring Original Values")
        logger.info("="*70)
        
        try:
            # Restore Model 702
            if '702.WChaRteMax' in self.original_values:
                model_702 = await self.client.get_model(702)
                if model_702:
                    model_702.points['WChaRteMax']['value'] = self.original_values['702.WChaRteMax']
                    model_702.points['WDisChaRteMax']['value'] = self.original_values['702.WDisChaRteMax']
                    await asyncio.get_event_loop().run_in_executor(None, model_702.write)
                    logger.info(f"✅ Restored Model 702 limits")
            
            # Restore Model 704
            if '704.WMaxLimPctEna' in self.original_values:
                model_704 = await self.client.get_model(704)
                if model_704:
                    model_704.points['WMaxLimPctEna']['value'] = self.original_values['704.WMaxLimPctEna']
                    model_704.points['WMaxLimPct']['value'] = self.original_values['704.WMaxLimPct']
                    await asyncio.get_event_loop().run_in_executor(None, model_704.write)
                    logger.info(f"✅ Restored Model 704 limits")
            
            logger.info("✅ Rollback complete")
            
        except Exception as e:
            logger.error(f"❌ Error during rollback: {e}")
            logger.error("⚠️  MANUAL INTERVENTION REQUIRED")
            logger.error(f"   Original Model 702.WChaRteMax: {self.original_values.get('702.WChaRteMax')}")
            logger.error(f"   Original Model 702.WDisChaRteMax: {self.original_values.get('702.WDisChaRteMax')}")


async def main():
    """Main test execution"""
    tester = BatteryControlTester()
    
    try:
        # Connect
        await tester.connect()
        
        # Phase 1: Read baseline
        await tester.read_baseline()
        
        input("\nPress Enter to continue to Phase 2 (Model 702 limits test)...")
        
        # Phase 2: Test Model 702 limits
        success_702 = await tester.test_model_702_limits(
            charge_limit_w=2500,    # 2.5 kW charge limit
            discharge_limit_w=3000  # 3.0 kW discharge limit
        )
        
        if success_702:
            # Monitor power
            await tester.monitor_power(duration_seconds=30)
        
        input("\nPress Enter to continue to Phase 3 (Model 704 % limit test)...")
        
        # Phase 3: Test Model 704 percentage limit
        success_704 = await tester.test_model_704_percent_limit(limit_pct=50)
        
        if success_704:
            # Monitor power
            await tester.monitor_power(duration_seconds=30)
        
        # Phase 4: Test timeout behavior (optional - takes 10 minutes)
        response = input("\nTest timeout behavior (10 minute idle test)? (yes/no): ")
        success_timeout = False
        if response.lower() == 'yes':
            success_timeout = await tester.test_timeout_behavior(duration_minutes=10)
        else:
            logger.info("⏭️  Skipping timeout test")
        
        input("\nPress Enter to rollback to original values...")
        
        # Rollback
        await tester.rollback_to_original()
        
        logger.info("\n" + "="*70)
        logger.info("TEST COMPLETE")
        logger.info("="*70)
        logger.info(f"Model 702 test: {'✅ SUCCESS' if success_702 else '❌ FAILED'}")
        logger.info(f"Model 704 test: {'✅ SUCCESS' if success_704 else '❌ FAILED'}")
        if response.lower() == 'yes':
            logger.info(f"Timeout test:   {'✅ SUCCESS - No heartbeat required!' if success_timeout else '⚠️  FAILED - May require heartbeat'}")
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Test interrupted by user")
        logger.info("Attempting rollback...")
        await tester.rollback_to_original()
    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}")
        logger.info("Attempting rollback...")
        await tester.rollback_to_original()
    finally:
        await tester.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

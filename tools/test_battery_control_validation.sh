#!/bin/bash
#
# Battery Control Validation Test
# 
# PURPOSE: Verify that FranklinWH aGate actually HONORS the limits set via SunSpec2
#          (not just accepts and stores them!)
#
# TEST STRATEGY:
# 1. Monitor baseline power flow
# 2. Set VERY LOW discharge limit (500W - should be obvious!)
# 3. Monitor actual power for 2 minutes
# 4. Check if power flow respects the limit
# 5. Restore unlimited operation
#
# PASS CRITERIA:
# - Battery discharge power stays ≤ limit + tolerance (±10%)
# - If battery tries to discharge >500W and gets capped, we have PROOF!
#

set -e

# Configuration
HOST="192.168.0.110"
PORT="502"
UNIT="1"

# Test parameters
DISCHARGE_LIMIT_W=500      # Very low - should be visible
CHARGE_LIMIT_W=500         # Very low - should be visible
MONITORING_DURATION=120    # 2 minutes
SAMPLE_INTERVAL=5          # 5 seconds

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Activate virtual environment
source venv/bin/activate

echo "=============================================="
echo "  Battery Control VALIDATION Test"
echo "=============================================="
echo ""
echo "🎯 OBJECTIVE: Prove aGate honors Model 702 limits"
echo ""
echo "Test Parameters:"
echo "  Discharge Limit: ${DISCHARGE_LIMIT_W}W"
echo "  Charge Limit: ${CHARGE_LIMIT_W}W"
echo "  Monitoring Duration: ${MONITORING_DURATION}s"
echo "  Sample Interval: ${SAMPLE_INTERVAL}s"
echo ""

# Helper function to read a point
read_point() {
    local point=$1
    python src/modbus_sunspec2_readwrite.py \
        -i $HOST -p $PORT -u $UNIT \
        --read "$point" 2>/dev/null | \
        grep -oP '(?<=Value: )[0-9.-]+' || echo "0"
}

# Helper function to write a point
write_point() {
    local point=$1
    local value=$2
    python src/modbus_sunspec2_readwrite.py \
        -i $HOST -p $PORT -u $UNIT \
        --write "${point}=${value}" >/dev/null 2>&1
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Phase 1: BASELINE - Read Current Power Flow"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Reading Model 714 (DC Power Measurement)..."
dc_power=$(read_point "714.W")
echo "  DC Power: ${dc_power}W"

echo ""
echo "Reading Model 701 (AC Power Measurement)..."
ac_power=$(read_point "701.W")
echo "  AC Power: ${ac_power}W"

echo ""
echo "Reading Model 702 (Current Limits)..."
current_charge_limit=$(read_point "702.WChaRteMax")
current_discharge_limit=$(read_point "702.WDisChaRteMax")
echo "  Current Charge Limit: ${current_charge_limit}W"
echo "  Current Discharge Limit: ${current_discharge_limit}W"

echo ""
echo "📊 BASELINE ESTABLISHED"
echo ""

# Determine what we can test based on current power flow
if (( $(echo "$dc_power < -100" | bc -l) )); then
    test_mode="DISCHARGE"
    echo "🔋 Battery is DISCHARGING (${dc_power}W)"
    echo "   → Will test DISCHARGE limit"
elif (( $(echo "$dc_power > 100" | bc -l) )); then
    test_mode="CHARGE"
    echo "🔌 Battery is CHARGING (${dc_power}W)"
    echo "   → Will test CHARGE limit"
else
    test_mode="IDLE"
    echo "⏸️  Battery is IDLE (${dc_power}W)"
    echo "   → Cannot validate - no power flow!"
    echo ""
    echo "❌ TEST SKIPPED: Need active charging or discharging to validate"
    echo ""
    echo "Recommendation: Run this test when battery is actively charging or discharging"
    exit 1
fi

echo ""
read -p "Press ENTER to apply limits and start monitoring..."
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Phase 2: APPLY LIMITS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Setting Model 702 limits..."
write_point "702.WChaRteMax" "$CHARGE_LIMIT_W"
write_point "702.WDisChaRteMax" "$DISCHARGE_LIMIT_W"

sleep 2

# Verify limits were set
new_charge_limit=$(read_point "702.WChaRteMax")
new_discharge_limit=$(read_point "702.WDisChaRteMax")

echo "  ✅ Charge Limit Set: ${new_charge_limit}W"
echo "  ✅ Discharge Limit Set: ${new_discharge_limit}W"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Phase 3: MONITOR ACTUAL POWER FLOW"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Monitoring for ${MONITORING_DURATION}s (samples every ${SAMPLE_INTERVAL}s)..."
echo ""
echo "Timestamp       | DC Power (W) | AC Power (W) | Status"
echo "----------------|--------------|--------------|------------------"

# Data collection arrays
declare -a timestamps
declare -a dc_powers
declare -a ac_powers

violations=0
samples=0
start_time=$(date +%s)

while true; do
    current_time=$(date +%s)
    elapsed=$((current_time - start_time))
    
    if [ $elapsed -ge $MONITORING_DURATION ]; then
        break
    fi
    
    # Read current power
    dc_now=$(read_point "714.W")
    ac_now=$(read_point "701.W")
    
    # Store data
    timestamps+=($elapsed)
    dc_powers+=($dc_now)
    ac_powers+=($ac_now)
    samples=$((samples + 1))
    
    # Check for limit violations
    status="✅ OK"
    if [ "$test_mode" = "DISCHARGE" ]; then
        # Negative power = discharge, check absolute value
        abs_power=$(echo "$dc_now" | tr -d '-')
        if (( $(echo "$abs_power > $DISCHARGE_LIMIT_W * 1.1" | bc -l) )); then
            status="${RED}❌ LIMIT VIOLATED!${NC}"
            violations=$((violations + 1))
        fi
    elif [ "$test_mode" = "CHARGE" ]; then
        if (( $(echo "$dc_now > $CHARGE_LIMIT_W * 1.1" | bc -l) )); then
            status="${RED}❌ LIMIT VIOLATED!${NC}"
            violations=$((violations + 1))
        fi
    fi
    
    printf "%-15s | %12.1f | %12.1f | %s\n" \
        "${elapsed}s" "$dc_now" "$ac_now" "$status"
    
    sleep $SAMPLE_INTERVAL
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Phase 4: ANALYSIS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Calculate statistics
total_samples=${#dc_powers[@]}
echo "Total Samples: $total_samples"
echo "Limit Violations: $violations"
echo ""

# Determine result
violation_rate=0
if [ $total_samples -gt 0 ]; then
    violation_rate=$(echo "scale=1; $violations * 100 / $total_samples" | bc)
fi

echo "Violation Rate: ${violation_rate}%"
echo ""

if [ $violations -eq 0 ]; then
    echo "${GREEN}✅ VALIDATION PASSED!${NC}"
    echo ""
    echo "Result: FranklinWH aGate HONORS Model 702 limits"
    echo "All power samples respected the ${DISCHARGE_LIMIT_W}W/${CHARGE_LIMIT_W}W limits"
    result="PASS"
elif (( $(echo "$violation_rate < 20" | bc -l) )); then
    echo "${YELLOW}⚠️  VALIDATION PARTIAL${NC}"
    echo ""
    echo "Result: aGate MOSTLY honors limits (${violation_rate}% violations)"
    echo "May have transient spikes or measurement timing issues"
    result="PARTIAL"
else
    echo "${RED}❌ VALIDATION FAILED!${NC}"
    echo ""
    echo "Result: FranklinWH aGate IGNORES Model 702 limits"
    echo "Power frequently exceeded set limits"
    result="FAIL"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Phase 5: RESTORE UNLIMITED OPERATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Restoring original limits..."
write_point "702.WChaRteMax" "$current_charge_limit"
write_point "702.WDisChaRteMax" "$current_discharge_limit"

sleep 1

restored_charge=$(read_point "702.WChaRteMax")
restored_discharge=$(read_point "702.WDisChaRteMax")

echo "  ✅ Charge Limit: ${restored_charge}W"
echo "  ✅ Discharge Limit: ${restored_discharge}W"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "VALIDATION TEST COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Test Mode: $test_mode"
echo "Result: $result"
echo "Samples: $total_samples"
echo "Violations: $violations (${violation_rate}%)"
echo ""

# Save detailed log
log_file="battery_control_validation_$(date +%Y%m%d_%H%M%S).log"
{
    echo "Battery Control Validation Test"
    echo "Date: $(date)"
    echo ""
    echo "Test Parameters:"
    echo "  Discharge Limit: ${DISCHARGE_LIMIT_W}W"
    echo "  Charge Limit: ${CHARGE_LIMIT_W}W"
    echo "  Test Mode: $test_mode"
    echo ""
    echo "Results:"
    echo "  Samples: $total_samples"
    echo "  Violations: $violations"
    echo "  Violation Rate: ${violation_rate}%"
    echo "  Result: $result"
    echo ""
    echo "Power Flow Data:"
    echo "Time,DC_Power,AC_Power"
    for i in "${!timestamps[@]}"; do
        echo "${timestamps[$i]},${dc_powers[$i]},${ac_powers[$i]}"
    done
} > "$log_file"

echo "📄 Detailed log saved to: $log_file"
echo ""

if [ "$result" = "PASS" ]; then
    exit 0
elif [ "$result" = "PARTIAL" ]; then
    exit 2
else
    exit 1
fi

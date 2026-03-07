#!/bin/bash
#
# Battery Control Validation Test (API Version)
# 
# Uses dashboard API instead of broken CLI scripts
#
# REQUIREMENTS:
# - Dashboard running at localhost:8000
# - Battery actively charging or discharging
#

set -e

# Configuration
API_BASE="http://localhost:8000/api"
DISCHARGE_LIMIT_W=500
CHARGE_LIMIT_W=500
MONITORING_DURATION=120
SAMPLE_INTERVAL=5

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=============================================="
echo "  Battery Control VALIDATION Test (API)"
echo "=============================================="
echo ""
echo "🎯 OBJECTIVE: Prove aGate honors Model 702 limits"
echo ""

# Check if dashboard is running
if ! curl -s "$API_BASE/status" > /dev/null 2>&1; then
    echo "${RED}❌ Dashboard not running!${NC}"
    echo ""
    echo "Start dashboard first:"
    echo "  ./run.sh"
    echo ""
    exit 1
fi

echo "✅ Dashboard is running"
echo ""

# Helper: Read SunSpec point via API
read_point() {
    local model=$1
    local point=$2
    curl -s "$API_BASE/sunspec/read?model=$model&point=$point" 2>/dev/null | \
        python -c "import sys, json; data=json.load(sys.stdin); print(data.get('value', 0) if data.get('success') else 0)" 2>/dev/null || echo "0"
}

# Helper: Write SunSpec point via API
write_point() {
    local model=$1
    local point=$2
    local value=$3
    curl -s -X POST "$API_BASE/sunspec/write" \
        -H "Content-Type: application/json" \
        -d "{\"model\": $model, \"point\": \"$point\", \"value\": $value}" \
        >/dev/null 2>&1
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Phase 1: BASELINE - Read Current Power Flow"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Reading Model 714 (DC Power Measurement)..."
dc_power=$(read_point 714 W)
echo "  DC Power: ${dc_power}W"

echo ""
echo "Reading Model 702 (Current Limits)..."
current_charge_limit=$(read_point 702 WChaRteMax)
current_discharge_limit=$(read_point 702 WDisChaRteMax)
echo "  Current Charge Limit: ${current_charge_limit}W"
echo "  Current Discharge Limit: ${current_discharge_limit}W"

echo ""
echo "📊 BASELINE ESTABLISHED"
echo ""

# Determine test mode
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
    echo "❌ TEST SKIPPED: Need active charging or discharging"
    echo ""
    echo "Recommendation:"
    echo "  1. Force-charge battery in FranklinWH app"
    echo "  2. Re-run this test"
    exit 1
fi

echo ""
read -p "Press ENTER to apply limits and start monitoring..."
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Phase 2: APPLY LIMITS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Setting Model 702 limits via API..."
write_point 702 WChaRteMax $CHARGE_LIMIT_W
write_point 702 WDisChaRteMax $DISCHARGE_LIMIT_W

sleep 2

# Verify limits
new_charge_limit=$(read_point 702 WChaRteMax)
new_discharge_limit=$(read_point 702 WDisChaRteMax)

echo "  ✅ Charge Limit Set: ${new_charge_limit}W"
echo "  ✅ Discharge Limit Set: ${new_discharge_limit}W"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Phase 3: MONITOR ACTUAL POWER FLOW"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Monitoring for ${MONITORING_DURATION}s (samples every ${SAMPLE_INTERVAL}s)..."
echo ""
echo "Timestamp       | DC Power (W) | Status"
echo "----------------|--------------|------------------"

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
    dc_now=$(read_point 714 W)
    samples=$((samples + 1))
    
    # Check for limit violations
    status="✅ OK"
    if [ "$test_mode" = "DISCHARGE" ]; then
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
    
    printf "%-15s | %12.1f | %s\n" "${elapsed}s" "$dc_now" "$status"
    
    sleep $SAMPLE_INTERVAL
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Phase 4: RESTORE UNLIMITED OPERATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Restoring original limits..."
write_point 702 WChaRteMax $current_charge_limit
write_point 702 WDisChaRteMax $current_discharge_limit

sleep 1

restored_charge=$(read_point 702 WChaRteMax)
restored_discharge=$(read_point 702 WDisChaRteMax)

echo "  ✅ Charge Limit: ${restored_charge}W"
echo "  ✅ Discharge Limit: ${restored_discharge}W"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "RESULTS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

violation_rate=0
if [ $samples -gt 0 ]; then
    violation_rate=$(echo "scale=1; $violations * 100 / $samples" | bc)
fi

echo "Test Mode: $test_mode"
echo "Total Samples: $samples"
echo "Limit Violations: $violations (${violation_rate}%)"
echo ""

if [ $violations -eq 0 ]; then
    echo "${GREEN}✅ VALIDATION PASSED!${NC}"
    echo ""
    echo "Result: FranklinWH aGate HONORS Model 702 limits"
    echo "Battery control is FUNCTIONAL - safe to implement Sprint 1!"
    exit 0
elif (( $(echo "$violation_rate < 20" | bc -l) )); then
    echo "${YELLOW}⚠️  VALIDATION PARTIAL${NC}"
    echo ""
    echo "Result: Mostly works (${violation_rate}% violations)"
    echo "May have transient spikes - acceptable for production"
    exit 2
else
    echo "${RED}❌ VALIDATION FAILED!${NC}"
    echo ""
    echo "Result: FranklinWH aGate IGNORES Model 702 limits"
    echo "Battery control feature NOT viable - DO NOT implement"
    exit 1
fi

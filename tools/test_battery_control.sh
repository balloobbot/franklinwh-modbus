#!/bin/bash
# Battery Control Test Script
# Safe testing of Model 702/704 power limiting controls

set -e

echo "========================================================================"
echo "Battery Control Test - FranklinWH SunSpec2"
echo "========================================================================"
echo ""

HOST="192.168.0.110"
PORT="502"
UNIT="1"

echo "Phase 1: Read Baseline (Current Values)"
echo "========================================================================"
echo ""

echo "📊 Model 702 (DER Capacity) - Current Limits:"
python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --read 702.WChaRteMaxRtg
python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --read 702.WDisChaRteMaxRtg
python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --read 702.WChaRteMax
python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --read 702.WDisChaRteMax

echo ""
echo "📊 Model 704 (DER AC Controls) - Current Limits:"
python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --read 704.WMaxLimPctEna
python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --read 704.WMaxLimPct

echo ""
echo "📊 Model 714 (DC Measurement) - Current Power:"
python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --read 714.W

echo ""
read -p "Press Enter to continue to Phase 2 (Model 702 limit test)..."

echo ""
echo "Phase 2: Test Model 702 Charge/Discharge Limits"
echo "========================================================================"
echo ""
echo "⚠️  ABOUT TO WRITE:"
echo "   WChaRteMax: 2500 W (2.5 kW charge limit)"
echo "   WDisChaRteMax: 3000 W (3.0 kW discharge limit)"
echo ""
read -p "Type 'yes' to proceed: " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ User cancelled"
    exit 1
fi

echo ""
echo "📝 Writing limits..."
python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --write 702.WChaRteMax=2500
python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --write 702.WDisChaRteMax=3000

echo ""
echo "✅ Verifying write..."
python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --read 702.WChaRteMax
python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --read 702.WDisChaRteMax

echo ""
echo "📊 Monitoring power for 30 seconds..."
for i in {1..30}; do
    power=$(python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --read 714.W 2>/dev/null | grep "Value:" | awk '{print $2}')
    echo "  [$i/30] Power: $power W"
    sleep 1
done

echo ""
read -p "Press Enter to continue to Phase 3 (Model 704 % limit test)..."

echo ""
echo "Phase 3: Test Model 704 Percentage Limit"
echo "========================================================================"
echo ""
echo "⚠️  ABOUT TO WRITE:"
echo "   WMaxLimPctEna: 1 (ENABLE percentage limiting)"
echo "   WMaxLimPct: 5000 (50% with scale factor -2)"
echo ""
read -p "Type 'yes' to proceed: " confirm2

if [ "$confirm2" != "yes" ]; then
    echo "❌ User cancelled - rolling back..."
    python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --write 702.WChaRteMax=5000
    python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --write 702.WDisChaRteMax=5000
    exit 1
fi

echo ""
echo "📝 Writing percentage limit..."
python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --write 704.WMaxLimPctEna=1
python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --write 704.WMaxLimPct=5000

echo ""
echo "✅ Verifying write..."
python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --read 704.WMaxLimPctEna
python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --read 704.WMaxLimPct

echo ""
echo "📊 Monitoring power for 30 seconds..."
for i in {1..30}; do
    power=$(python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --read 714.W 2>/dev/null | grep "Value:" | awk '{print $2}')
    echo "  [$i/30] Power: $power W"
    sleep 1
done

echo ""
read -p "Test timeout behavior (10 minute idle test)? (yes/no): " confirm3

if [ "$confirm3" = "yes" ]; then
    echo ""
    echo "Phase 4: Timeout Behavior Test (10 Minutes)"
    echo "========================================================================"
    echo ""
    echo "⏱️  Testing if limits persist without heartbeat writes..."
    echo "   This will monitor for 10 minutes with NO writes."
    echo ""
    
    # Get current limits
    charge_limit=$(python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --read 702.WChaRteMax 2>/dev/null | grep "Value:" | awk '{print $2}')
    discharge_limit=$(python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --read 702.WDisChaRteMax 2>/dev/null | grep "Value:" | awk '{print $2}')
    
    echo "Starting limits: Charge=$charge_limit W, Discharge=$discharge_limit W"
    echo ""
    
    for minute in {1..10}; do
        echo "--- Minute $minute/10 ---"
        
        # Check power every 15 seconds
        for quarter in {0..3}; do
            seconds=$((quarter * 15))
            power=$(python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --read 714.W 2>/dev/null | grep "Value:" | awk '{print $2}')
            echo "  [$minute:$(printf '%02d' $seconds)] Power: $power W"
            
            if [ $quarter -lt 3 ]; then
                sleep 15
            fi
        done
        
        # Check if limits still applied
        new_charge=$(python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --read 702.WChaRteMax 2>/dev/null | grep "Value:" | awk '{print $2}')
        new_discharge=$(python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --read 702.WDisChaRteMax 2>/dev/null | grep "Value:" | awk '{print $2}')
        
        if [ "$new_charge" != "$charge_limit" ] || [ "$new_discharge" != "$discharge_limit" ]; then
            echo ""
            echo "⚠️  LIMITS CHANGED!"
            echo "   Charge: $charge_limit → $new_charge W"
            echo "   Discharge: $discharge_limit → $new_discharge W"
            echo "   Auto-revert detected after $minute minutes"
            echo ""
            break
        else
            echo "  ✅ Limits still applied: $new_charge W / $new_discharge W"
        fi
        echo ""
    done
    
    echo "✅ Timeout test complete"
else
    echo "⏭️  Skipping timeout test"
fi

echo ""
read -p "Press Enter to rollback to original values..."

echo ""
echo "Rollback: Restoring Original Values"
echo "========================================================================"
echo ""

# Restore to rated maximums
python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --write 702.WChaRteMax=5000
python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --write 702.WDisChaRteMax=5000
python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --write 704.WMaxLimPctEna=0
python src/modbus_sunspec2_readwrite.py -i $HOST -p $PORT -u $UNIT --write 704.WMaxLimPct=0

echo ""
echo "✅ Rollback complete"

echo ""
echo "========================================================================"
echo "TEST COMPLETE"
echo "========================================================================"

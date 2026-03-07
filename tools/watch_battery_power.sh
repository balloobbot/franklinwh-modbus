#!/bin/bash
# Real-time battery power monitoring
# Shows Model 714 DC power and Model 702 limits

source venv/bin/activate

echo "=========================================="
echo " Real-Time Battery Power Monitor"
echo "=========================================="
echo ""
echo "Monitoring battery DC power (Model 714.W)"
echo "And current limits (Model 702)"
echo ""
echo "Press Ctrl+C to stop"
echo ""

watch -n 2 '
echo "=== $(date +"%H:%M:%S") ==="
echo ""
echo "Battery DC Power (Model 714.W):"
python src/modbus_sunspec2_readwrite.py -i 192.168.0.110 --read 714.W 2>/dev/null | grep -oP "(?<=Value: )[0-9.-]+" || echo "  Failed to read"
echo ""
echo "Current Limits (Model 702):"
echo -n "  Charge Max: "
python src/modbus_sunspec2_readwrite.py -i 192.168.0.110 --read 702.WChaRteMax 2>/dev/null | grep -oP "(?<=Value: )[0-9.-]+" || echo "0"
echo -n "W  Discharge Max: "
python src/modbus_sunspec2_readwrite.py -i 192.168.0.110 --read 702.WDisChaRteMax 2>/dev/null | grep -oP "(?<=Value: )[0-9.-]+" || echo "0"
echo "W"
'

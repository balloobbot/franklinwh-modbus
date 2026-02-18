#!/bin/bash
# Quick script to restore unlimited battery operation
# Run this if limits are stuck at 0W or blocking operation

source venv/bin/activate

echo "Restoring unlimited battery operation..."
echo ""

# Set to 10kW (10000W) which should be unlimited for FranklinWH
python src/modbus_sunspec2_readwrite.py -i 192.168.0.110 \
    --write 702.WChaRteMax=10000

python src/modbus_sunspec2_readwrite.py -i 192.168.0.110 \
    --write 702.WDisChaRteMax=10000

echo ""
echo "✅ Limits restored to 10000W (unlimited)"
echo ""
echo "Verifying..."
python src/modbus_sunspec2_readwrite.py -i 192.168.0.110 --read 702.WChaRteMax
python src/modbus_sunspec2_readwrite.py -i 192.168.0.110 --read 702.WDisChaRteMax

#!/bin/bash
# Pre-Test Health Check - Verify Clean Baseline State
# Date: 2026-02-15 02:40

IP="192.168.0.110"
UNIT=2

echo "=== MODEL 704 HEALTH CHECK - Baseline Verification ==="
echo "Date: $(date)"
echo ""

echo "Step 1: Check if currently in VPP Mode"
echo "  → Open FranklinWH app and check 'Run Status'"
read -p "Is VPP Mode currently active? (y/n): " vpp_active

if [ "$vpp_active" = "y" ]; then
    echo "  ⚠️  VPP MODE IS ACTIVE - not clean baseline!"
    echo "  Recommendation: Wait for timer to expire or send --idle"
    exit 1
else
    echo "  ✅ VPP Mode not active - good"
fi

echo ""
echo "Step 2: Reading ALL Model 704 RW registers..."
python3 << 'EOF'
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient('192.168.0.110', port=502, timeout=10)
client.connect()

print("\n=== Model 704 RW Registers - Expected Defaults ===\n")

# Read Model 704 control registers
r = client.read_holding_registers(299, count=60, device_id=2)

if not r.isError():
    # Define expected defaults per SunSpec spec
    checks = []
    
    # WSetEna (PDU 321, offset 22 from 299)
    wsetena = r.registers[22]
    checks.append({
        'register': 'WSetEna (321)',
        'value': wsetena,
        'expected': 0,
        'ok': wsetena == 0,
        'meaning': 'DISABLED' if wsetena == 0 else 'ENABLED'
    })
    
    # WSetMod (PDU 322)
    wsetmod = r.registers[23]
    checks.append({
        'register': 'WSetMod (322)',
        'value': wsetmod,
        'expected': 0,
        'ok': wsetmod == 0,
        'meaning': 'Absolute W'
    })
    
    # WSet (PDU 323-324)
    wset_high = r.registers[24]
    wset_low = r.registers[25]
    wset = (wset_high << 16) | wset_low
    if wset >= 0x80000000:
        wset -= 0x100000000
    checks.append({
        'register': 'WSet (323-324)',
        'value': wset,
        'expected': 0,
        'ok': wset == 0,
        'meaning': f'{wset}W'
    })
    
    # WSetRvrtTms (PDU 330-331, offset 31-32 from 299)
    rvrt_high = r.registers[31]
    rvrt_low = r.registers[32]
    rvrt_tms = (rvrt_high << 16) | rvrt_low
    checks.append({
        'register': 'WSetRvrtTms (330-331)',
        'value': rvrt_tms,
        'expected': '0 or 1800',
        'ok': rvrt_tms == 0 or rvrt_tms == 1800,
        'meaning': f'{rvrt_tms}s' if rvrt_tms != 0 else 'No reversion'
    })
    
    # WSetRvrtRem (PDU 332-333)
    rem_high = r.registers[33]
    rem_low = r.registers[34]
    rvrt_rem = (rem_high << 16) | rem_low
    checks.append({
        'register': 'WSetRvrtRem (332-333)',
        'value': rvrt_rem,
        'expected': 0,
        'ok': rvrt_rem == 0,
        'meaning': f'{rvrt_rem}s remaining' if rvrt_rem > 0 else 'Not running'
    })
    
    # VarSetEna (PDU 335, offset 36 from 299)
    varsetena = r.registers[36]
    checks.append({
        'register': 'VarSetEna (335)',
        'value': varsetena,
        'expected': 0,
        'ok': varsetena == 0,
        'meaning': 'DISABLED' if varsetena == 0 else 'ENABLED'
    })
    
    # Display results
    print("Register              | Value     | Expected  | Status | Meaning")
    print("-" * 75)
    
    all_ok = True
    for check in checks:
        status = "✅ OK" if check['ok'] else "❌ FAIL"
        if not check['ok']:
            all_ok = False
        print(f"{check['register']:20} | {check['value']:9} | {str(check['expected']):9} | {status:6} | {check['meaning']}")
    
    print("\n=== OVERALL HEALTH CHECK ===")
    if all_ok:
        print("✅ ALL REGISTERS AT EXPECTED DEFAULTS")
        print("✅ CLEAN BASELINE - Ready for test")
    else:
        print("❌ SOME REGISTERS NOT AT DEFAULTS")
        print("⚠️  Recommendation: Reset registers before test")
        print("\nTo reset, run:")
        print("  python3 fhp_battery_ctrl.py -i $IP --franklinwh --unit-id $UNIT --idle")
else:
    print(f"❌ Error reading registers: {r}")

client.close()
EOF

echo ""
echo "Step 3: Summary"
echo ""
echo "If all checks passed:"
echo "  ✅ System is in clean baseline state"
echo "  ✅ Safe to proceed with MAX_CHARGE unlock test"
echo ""
echo "If any checks failed:"
echo "  ⚠️  Send --idle command to reset registers"
echo "  ⚠️  Verify VPP mode deactivates"
echo "  ⚠️  Re-run this health check"

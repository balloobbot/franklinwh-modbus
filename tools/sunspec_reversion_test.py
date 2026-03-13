#!/usr/bin/env python3
"""
REVERSION EFFICACY TEST v2
Uses library for VPP, then raw sockets for reversion + polling.
"""
import socket, struct, time, sys
sys.path.insert(0, '/Users/davidhona/dev/modbus/src')

IP = '192.168.0.110'; PORT = 502; UID = 2; TO = 30

def conn():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(TO); s.connect((IP, PORT)); return s

def rd(s, addr, n=1):
    req = struct.pack('>HHHBBHH', 0, 0, 6, UID, 3, addr, n)
    s.settimeout(TO); s.sendall(req); r = s.recv(256)
    if len(r) < 9 or (r[7] & 0x80): return 'ERR'
    if n == 1: return struct.unpack('>H', r[9:11])[0]
    return [struct.unpack('>H', r[9+i*2:11+i*2])[0] for i in range(n)]

def rd_s16(s, addr):
    req = struct.pack('>HHHBBHH', 0, 0, 6, UID, 3, addr, 1)
    s.settimeout(TO); s.sendall(req); r = s.recv(256)
    if len(r) < 9 or (r[7] & 0x80): return 'ERR'
    return struct.unpack('>h', r[9:11])[0]

def wr(s, addr, val):
    req = struct.pack('>HHHBBHH', 0, 0, 6, UID, 6, addr, val & 0xFFFF)
    s.settimeout(TO); s.sendall(req); r = s.recv(256)
    return 'OK' if not (len(r) < 8 or (r[7] & 0x80)) else 'ERR'

def wr32(s, addr, val):
    hi = (val >> 16) & 0xFFFF; lo = val & 0xFFFF
    header = struct.pack('>HHHBBHHB', 0, 0, 11, UID, 16, addr, 2, 4)
    s.settimeout(TO); s.sendall(header + struct.pack('>HH', hi, lo)); r = s.recv(256)
    return 'OK' if not (len(r) < 8 or (r[7] & 0x80)) else 'ERR'

print("REVERSION EFFICACY TEST v2", flush=True)
print("="*60, flush=True)

# Step 1: Activate VPP via library (this does proper sequencing)
print("\n[1] Activate VPP via library...", flush=True)
from franklinwh_modbus import FranklinWHController
from franklinwh_modbus.types import BatteryCommand, ControlMode
ctrl = FranklinWHController(IP); ctrl.connect()
ok, msg = ctrl.send_command(BatteryCommand(power_watts=500, mode=ControlMode.LIMIT_ABS))
print(f"  {msg}", flush=True)
ctrl.disconnect()
print("  Waiting 8s for VPP...", flush=True)
time.sleep(8)

# Step 2: Configure reversion via raw socket (VPP now active)
print("\n[2] Configure reversion (VPP active)...", flush=True)
s = conn()
time.sleep(0.3); wse = rd(s, 318)
print(f"  WSetEna={wse}", flush=True)

# Set reversion target to 0W
time.sleep(0.3); r1 = wr32(s, 322, 0)
print(f"  WSetRvrt=0: {r1}", flush=True)

# Enable reversion
time.sleep(0.3); r2 = wr(s, 326, 1)
print(f"  WSetEnaRvrt=1: {r2}", flush=True)

# Set 30s countdown
time.sleep(0.3); r3 = wr32(s, 327, 30)
print(f"  WSetRvrtTms=30: {r3}", flush=True)
time.sleep(0.5)

# Confirm
time.sleep(0.3); c_rvrt = rd(s, 322, 2)
time.sleep(0.3); c_rena = rd(s, 326)
time.sleep(0.3); c_rtms = rd(s, 327, 2)
time.sleep(0.3); c_rrem = rd(s, 329, 2)
time.sleep(0.3); c_wse = rd(s, 318)
time.sleep(0.3); c_wpct = rd_s16(s, 324)
s.close()

print(f"  WSetEna={c_wse} WSetPct={c_wpct}", flush=True)
print(f"  WSetRvrt={c_rvrt} WSetEnaRvrt={c_rena}", flush=True)
print(f"  WSetRvrtTms={c_rtms} WSetRvrtRem={c_rrem}", flush=True)

if not isinstance(c_rrem, list) or c_rrem == [0, 0]:
    print("\n  ⚠️ Countdown not active! Timer may not have accepted.", flush=True)
else:
    print(f"\n  ✅ Countdown active: {c_rrem[1]}s remaining", flush=True)

# Step 3: Poll every 5s for 45s (fresh connection each poll)
print(f"\n{'━'*60}", flush=True)
print("  POLLING — fresh connection per poll", flush=True)
print(f"{'━'*60}", flush=True)
print(f"  {'T':>4s}  {'WSetEna':>8s}  {'WSetPct':>8s}  {'RvrtRem':>8s}  {'Notes'}", flush=True)
print(f"  {'─'*4}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*20}", flush=True)

t0 = time.time()
for i in range(10):  # 0, 5, 10, ..., 45
    target = t0 + i * 5
    now = time.time()
    if now < target: time.sleep(target - now)

    try:
        sp = conn()
        time.sleep(0.2); we = rd(sp, 318)
        time.sleep(0.2); wp = rd_s16(sp, 324)
        time.sleep(0.2); rr = rd(sp, 329, 2)
        sp.close()
    except Exception as e:
        we = wp = rr = f'ERR:{e}'

    rr_val = rr[1] if isinstance(rr, list) else rr
    elapsed = time.time() - t0
    note = ""
    if elapsed < 28: note = "counting down"
    elif 28 <= elapsed < 33: note = "EXPIRY ZONE"
    else:
        note = "AFTER EXPIRY"
        if isinstance(we, int) and we == 0: note += " WSetEna=0 ✅"
        elif isinstance(we, int) and we == 1: note += " WSetEna=1 ⚠️"

    print(f"  {elapsed:4.0f}s  {we!s:>8s}  {wp!s:>8s}  {rr_val!s:>8s}  {note}", flush=True)

# Step 4: Final state
print(f"\n{'━'*60}", flush=True)
print("  FINAL STATE", flush=True)
print(f"{'━'*60}", flush=True)
sf = conn()
time.sleep(0.3); f_wse = rd(sf, 318)
time.sleep(0.3); f_wpct = rd_s16(sf, 324)
time.sleep(0.3); f_wset = rd(sf, 320, 2)
time.sleep(0.3); f_rvrt = rd(sf, 322, 2)
time.sleep(0.3); f_rena = rd(sf, 326)
time.sleep(0.3); f_rtms = rd(sf, 327, 2)
time.sleep(0.3); f_rrem = rd(sf, 329, 2)
sf.close()
print(f"  WSetEna={f_wse}  WSetPct={f_wpct}  WSet={f_wset}", flush=True)
print(f"  WSetRvrt={f_rvrt}  WSetEnaRvrt={f_rena}", flush=True)
print(f"  WSetRvrtTms={f_rtms}  WSetRvrtRem={f_rrem}", flush=True)

# Verdict
print(f"\n{'═'*60}", flush=True)
if isinstance(f_wse, int) and f_wse == 0:
    print("  ✅ WSetEna auto-cleared to 0 → VPP DEACTIVATED", flush=True)
elif isinstance(f_wse, int) and f_wse == 1:
    print("  ⚠️ WSetEna still 1 → VPP DID NOT AUTO-DEACTIVATE", flush=True)
if isinstance(f_wpct, int) and f_wpct == 0:
    print("  ✅ WSetPct reverted to 0", flush=True)
else:
    print(f"  ⚠️ WSetPct={f_wpct} (was -100, expected 0 if reverted)", flush=True)
print(f"{'═'*60}", flush=True)

# Cleanup
print("\n[CLEANUP]...", flush=True)
ctrl2 = FranklinWHController(IP); ctrl2.connect()
ctrl2.reset_control_state()
bat = ctrl2.read_battery_status()
mode = ctrl2.read_native_mode()
print(f"  SoC={bat.get('soc')}% Mode={mode.get('mode_name')}", flush=True)
ctrl2.disconnect()
print("DONE", flush=True)

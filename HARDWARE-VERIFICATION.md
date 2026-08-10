# What I'd want to check against a real aGate

This migration was written without hardware. The register map is a
*reconstruction* — built from the SunSpec model definitions, sized with the
counts reported in
[modbus-connection#156](https://github.com/home-assistant-libs/modbus-connection/issues/156),
and validated by reproducing all 29 absolute addresses documented in
`SUNSPEC_MODEL_REFERENCE.md` (see MIGRATION-NOTES.md §0).

That validation is strong about **addresses and layout** and says nothing about
**behaviour**. Everything below is the difference between those two.

There's a script for the read-only half:

```bash
python3 scripts/hardware_check.py 192.168.1.100 --json report.json
```

It walks the chain, compares every model's address and length against the
reconstruction, reports the curve counts, and flags each assumption that turns
out to be wrong. It issues no writes, changes no mode and moves no power, so it
is safe on a live system at any state of charge. Exit code is non-zero if
anything differs. Against the reconstruction it reports zero differences —
which is what makes a difference on real hardware meaningful.

The write checks are not in the script, because they move a battery.

---

## Tier 1 — would change the code if wrong

### 1. Does the device really acknowledge writes it discards?

**Why it matters most:** it is the reason every write in this library is
verified by a read-back (`writing.py`), the reason `WriteRejected` exists, and
the reason `--test-extension-write` works by writing each register the value it
already holds. If the device raises a proper Modbus exception instead, all of
that is unnecessary machinery.

The claim comes from the old code's own comment — *"FC06 response is just an
echo. We MUST perform a separate read to verify the write actually STUCK"* — and
from a second owner's report cited in ha-sunspec's notes. Neither is an
observation I made.

**How:** with SPAN Modbus *locked*, write 15507 and watch the response.

```python
from modbus_connection import ModbusTcpParams
from modbus_connection.tmodbus import ModbusConnection

unit = (await connect()).for_unit(2)
before = (await unit.read_holding_registers(15507, 1))[0]
await unit.write_register(15507, 3 if before != 3 else 2)   # exception here?
after = (await unit.read_holding_registers(15507, 1))[0]
print(before, after)                                        # or silence + no change?
```

**Expect:** no exception, and `after == before`. If instead it raises
`IllegalDataAddressError` or similar, say so — read-back verification could
become opt-in rather than the default.

### 2. Does writing 15507 really reset 15508 and 15509?

**Why:** this is the one place where batching is a *correctness* requirement
rather than a saving. `async_set_native_mode()` writes all three registers in
one FC16, rewriting the reserves to the values they already hold, purely
because of this. If it's not true, that method gets simpler.

**How:** needs SPAN Modbus unlocked.

```
1. set the reserves to distinctive values (e.g. 23% and 37%)
2. write 15507 ALONE with a single-register FC06
3. read 15508 and 15509
```

**Expect:** they come back as something other than 23/37. Also worth trying the
FC16 form and confirming it *doesn't* reset them — that's the assumption the
fix rests on.

### 3. Does the aGate accept FC16 at all?

**Why:** the old code used FC06 almost exclusively. Every batching claim in this
migration — the 17→4 curve write, the three-register mode write — assumes FC16
works. If the device only honours single-register writes, the whole write path
collapses back to FC06 and item 2 has no fix.

**How:** `scripts/hardware_check.py` confirms FC03 block widths but cannot test
writes. Manually: `await unit.write_registers(15508, [20, 30])` with the values
already there, then read back.

**Expect:** accepted. Check it separately in the curve block (see item 9) — some
firmware accepts FC16 in one region and not another.

### 4. Is `WSetRvrtTms` really decorative?

**Why:** the entire software-timeout design rests on it. If the hardware timer
does revert, `duration_s` becomes a convenience instead of the only safety
mechanism, and the docs overstate the danger.

**How:** set `WSetRvrtTms` to 60 s, issue a setpoint, wait 90 s, read `WSetEna`
and `WSetPct`. **Expect:** both unchanged, and `WSetRvrtRem` at 0.

### 5. Do the settle delays and the three-phase order actually matter?

**Why:** `CONTROL_SETTLE_S = 0.3` and `ENABLE_SETTLE_S = 0.5` are inherited
numbers with no measurement behind them, and every control write pays them.
The stop→configure→enable ordering is likewise inherited.

**How:**
- Set both to `0.0` and issue ten setpoints. Does each land?
- Write `WSetPct` while `WSetEna` is still 1. Is it ignored, as the old code's
  comment claims?
- Binary-search the smallest delay that still works.

**Expect:** unknown — this is the item most likely to produce a surprise in
either direction. Measuring it would let the library stop guessing.

---

## Tier 2 — the reconstruction's blind spots

These are all covered by `scripts/hardware_check.py`. Listed so the output means
something.

### 6. The chain, and where M502 actually sits

The reconstruction places M1@2, M701@70 … M715@1087 — and infers M502 *after*
715, because every documented address is exactly 30 lower than a chain
containing it between M1 and M701. That inference is the one part of the layout
not pinned by evidence. **Nothing in the library depends on it**, but I'd like
to know.

Also worth confirming: no model ID appears twice, and no model appears that the
reconstruction doesn't know about.

### 7. Do all 17 model headers verify?

The single highest-value read-only check, and it happens automatically:
`SunSpecComponent._verify_read()` compares each model's read-back ID and length
against the scan on every poll. If `async_connect()` succeeds, all 17 matched.

For M705–M712 that also **confirms their counts**, because a curve model's
length is a function of `NPt` / `NCrv` / `NCrvSet`. A device reporting different
counts fails loudly on the first read rather than decoding garbage — which is
the safety property that makes shipping generated static layouts defensible.

### 8. Are all the scale factors in range?

ha-sunspec's notes state that all 55 `sunssf` registers on this hardware hold
valid in-range exponents, and a fair amount rests on it: modbus-connection
decodes a point whose factor is out of range to `None`, where pysunspec2 hands
back the raw value. If even one is unimplemented on a real unit, that
disagreement stops being theoretical.

The script reads every distinct scale register the components reference and
reports any outside −10..10.

### 9. What do the curve models actually contain?

The seven curve models read on the reconstruction, but every point in it is
synthetic. On a real unit:

- Is any curve **configured** (`ActPt` > 0)? If they're all zero, the whole
  curve half of the profile is present but unused, and `read_curve()`'s
  truncation has never done anything real.
- Is any curve's **`ReadOnly`** flag set? If every curve reports writable, then
  issue 156's item 4 (per-instance writability) is untested on this device and
  I'd downgrade how hard I pushed it.
- For 707–710, do the three trip regions hold *distinct* values? That's the
  strongest available check that `MayTrip` and `MomCess` are placed at the right
  runtime offsets — if my arithmetic were wrong, they'd overlap or read zeros.

### 10. Does the extension block behave?

- Does 15500–15513 answer as one block?
- Does **16000** — the undocumented high-resolution load mirror — answer at all,
  and is it genuinely finer than 15506? `home_load_w()` prefers it whenever it's
  non-zero.
- Are 15504/15505 (remote PV) meaningful, or always 0 on a unit without apBoxes?

### 11. How wide a read will it answer?

The planner caps blocks at 125 registers, the Modbus ceiling. Some gateways cap
lower, and then `Component.max_span` has to come down. The script tries 125
first.

Also worth knowing: is `message_spacing=0.05` enough? The old code slept **0.6 s
between model reads** — if that was necessary rather than cargo-culted, the
default here is far too aggressive and a poll will start failing.

---

## Tier 3 — never exercised at all

### 12. The curve write path

`write_curve()` is the payload of the whole 1547 exercise and has only ever run
against a mock. On hardware:

- Does one FC16 over the 8 contiguous point registers land?
- Does `ActPt` take, written separately and last?
- Is the measured round-trip count actually 4, and is the wall-clock saving real
  on a device that wants settling time?
- Does the device *validate* a curve — reject a non-monotonic one, say — or
  accept anything?

Start with model 705 curve index 2 (a stored curve, not the active one) if the
firmware distinguishes them.

### 13. The runtime-counted prototype

The acceptance test for issue 156. Run the same device against the
[`sunspec-1547-curve-models`](https://github.com/home-assistant-libs/modbus-connection/tree/sunspec-1547-curve-models)
branch with the runtime-counted layout (the `TripLV` / `VoltVar` classes in that
branch's tests) and confirm it reads **the same values** as the static build
here. Two specific things:

- Does a nested count register get read at the model-relative address, once,
  rather than shifted per instance?
- Do `MayTrip` and `MomCess` land at `offset=lambda m: 1 + 3*m.n_pt` and twice
  that?

If both hold on real hardware, the proposal is validated end to end.

### 14. Multi-battery (`NPrt` > 1)

The fixture has one DC port. The summing, peak-temperature and mean-voltage
logic in `battery_status()` — and the derived-current workaround, which divides
total power by the mean of the *live* voltages — has never seen more than one
port. Anyone with two or three stacks would be exercising genuinely untested
code.

### 15. The mode calculators' sign convention

The known defect, carried over deliberately (see the note at the top of
`modes.py`): `_calc_self_consumption` returns `-max_charge_w` for "charge flat
out", while peak-shave and the TOU discharge branch return a *positive* number
to discharge. `BatteryCommand` documents positive as charge.

Someone with hardware can settle it in one observation: **run
`--vmode self_consumption` below target and watch which way the battery goes.**
Whichever it is, half these functions are wrong and I had no way to tell which
half.

### 16. The TUI and the CLI end to end

`monitor.py` has never been rendered — it was ported by rewiring its data
access, and the layout code was not touched. The CLI's argument handling is
unchanged but every path through it now goes via `SyncAGate`. Both need someone
to actually look at them.

### 17. Off-grid behaviour

`_inverter_safety()` only engages when `connection_state != "Connected"`, so
none of it has ever run. Worth checking during a real outage, or by opening the
main breaker if that's safe on the installation.

### 18. Connection loss and recovery

`reconnect()` is now "connect again" rather than the old bespoke retry path,
because the connection layer handles the rest. Unplug the network mid-poll and
mid-control-loop and see whether the loop recovers and, critically, whether it
still releases control on the way out.

---

## What a report back would ideally contain

```bash
python3 scripts/hardware_check.py <ip> --json agate-report.json
```

plus, for anything in Tier 1 or 3 that gets tried, just: what was done, what
happened, and what was expected. A raw dump would also settle §0 for good —
`agate.async_read_raw()` returns every polled register keyed by address.

**If the script reports zero differences**, the reconstruction is exact and
everything in MIGRATION-NOTES.md that rests on layout is solid. The behavioural
claims in Tier 1 would still be open.

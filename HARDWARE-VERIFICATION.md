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

## What has been answered

@david2069 ran the script and two write experiments against an **aGate X on
firmware `V10R01B04D00`**, single DC port, **no SPAN on the system**, and
reported back in
[david2069/franklinwh-modbus#12](https://github.com/david2069/franklinwh-modbus/issues/12).
Each item below carries the result. In short:

- **The reconstruction is exact.** 50 checks, 0 differing. All of Tier 2 is
  settled, including M502 at 1096 — the one placement no evidence pinned.
- **The sign convention is settled, and the code was wrong** (§15). Fixed.
- **§5 was settled by the specification, not by the device.** The three-phase
  order was half right: enable last is required, the stop phase is advised
  against. Fixed.
- Tier 1's write items and Tier 3 are still open. Items 1 and 2 need a SPAN
  lock state this reporter cannot set either way.

The two sources cited below are the SunSpec Alliance *Information Model
Specification* (doc 12041, v1.9) and the *Modbus IEEE 1547-2018 Profile
Specification* (v1.1, 2024-02-15).

---

## Tier 1 — would change the code if wrong

### 1. Does the device really acknowledge writes it discards?

> **Answered by the specification; still open on this device.** Information
> Model Specification, *Read-Only and Write-Only Registers*, p. 19: "WRITE to
> R: The written value is ignored. No exception is generated." A device that
> accepts the write and raises nothing is conforming, so read-back
> verification rests on the spec rather than on folklore. It stays mandatory
> and does **not** become opt-in. What is still unobserved is this device
> under a SPAN lock.

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

> **Still open.** Needs SPAN Modbus unlocked; the reporting system has no SPAN.

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

> **Partly answered.** The 704 control writes went out and read back correctly
> throughout §15's runs. The curve block is still untested.

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

> **Still open.**

**Why:** the entire software-timeout design rests on it. If the hardware timer
does revert, `duration_s` becomes a convenience instead of the only safety
mechanism, and the docs overstate the danger.

**How:** set `WSetRvrtTms` to 60 s, issue a setpoint, wait 90 s, read `WSetEna`
and `WSetPct`. **Expect:** both unchanged, and `WSetRvrtRem` at 0.

### 5. Do the settle delays and the three-phase order actually matter?

> **Answered, by the specification.** Information Model Specification,
> *Procedures for Multi-Write Operations*, p. 21: "Changed settings are
> written. Changes do NOT take effect, even if the activation field is already
> enabled, until the activation field is enabled." So enable-last is required,
> and the old code's comment was describing specified behaviour rather than a
> FranklinWH quirk. The same section: "It is not recommended to disable the
> control to update the settings" — which the stop phase did. The stop phase is
> gone and the enable write is last; see `async_send_command`.
>
> Two runs at +30%, one written into an already-enabled control and one through
> configure-then-enable, both moved 0 W — but that comparison is confounded by
> the sign (§15), so it measures nothing about ordering. The settle delays are
> still unmeasured.
>
> **Still open:** whether writing `WSetEna = 1` when it already reads 1 counts
> as enabling the activation field on this firmware, or whether an edge is
> needed. The library writes it unconditionally.

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

> **Settled.** All 17 models present, each once, every address and length
> matching. **M502 sits at 1096, L=28** — the inferred placement is correct.

The reconstruction places M1@2, M701@70 … M715@1087 — and infers M502 *after*
715, because every documented address is exactly 30 lower than a chain
containing it between M1 and M701. That inference is the one part of the layout
not pinned by evidence. **Nothing in the library depends on it**, but I'd like
to know.

Also worth confirming: no model ID appears twice, and no model appears that the
reconstruction doesn't know about.

### 7. Do all 17 model headers verify?

> **Settled.** All 17 verify, so the counts this build generates against are
> confirmed by construction.

The single highest-value read-only check, and it happens automatically:
`SunSpecComponent._verify_read()` compares each model's read-back ID and length
against the scan on every poll. If `async_connect()` succeeds, all 17 matched.

For M705–M712 that also **confirms their counts**, because a curve model's
length is a function of `NPt` / `NCrv` / `NCrvSet`. A device reporting different
counts fails loudly on the first read rather than decoding garbage — which is
the safety property that makes shipping generated static layouts defensible.

### 8. Are all the scale factors in range?

> **Settled.** 33 distinct referenced `sunssf` registers, all within -10..10,
> none unimplemented.

ha-sunspec's notes state that all 55 `sunssf` registers on this hardware hold
valid in-range exponents, and a fair amount rests on it: modbus-connection
decodes a point whose factor is out of range to `None`, where pysunspec2 hands
back the raw value. If even one is unimplemented on a real unit, that
disagreement stops being theoretical.

The script reads every distinct scale register the components reference and
reports any outside −10..10.

### 9. What do the curve models actually contain?

> **Settled, with one blank.** Curves are configured, not dormant: M705 3/3,
> M706 2/2, M712 2/2 have active points, so `read_curve()`'s truncation does
> real work. `ReadOnly` is per instance and it is set — `crv[0]` reports
> read-only on all seven curve models, every later instance writable. So
> `curves.py::is_writable` is load-bearing, not defensive.
>
> Trip regions: all four of 707-710 return both sets with all three region
> keys. `must_trip` holds values everywhere; `mom_cess` holds values on 707 and
> 708 and reads all-`None` on 709/710; **`may_trip` reads all-`None` on all
> four**. An unimplemented region and a misplaced read are indistinguishable
> from there, so `may_trip` does **not** confirm the `1 + 3*NPt` offset, and
> §13 cannot lean on it as the acceptance test. `mom_cess` corroborates the
> offset on the two models that populate it.

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

> **Settled on reads.** It reads as one block, mode and both reserves decode.
> **16000 answers and is genuinely finer than 15506** — 261 W against 300 W at
> the same instant — so `home_load_w`'s preference for the mirror is right.
> Writes still need SPAN.

- Does 15500–15513 answer as one block?
- Does **16000** — the undocumented high-resolution load mirror — answer at all,
  and is it genuinely finer than 15506? `home_load_w()` prefers it whenever it's
  non-zero.
- Are 15504/15505 (remote PV) meaningful, or always 0 on a unit without apBoxes?

### 11. How wide a read will it answer?

> **Settled.** FC03 of 125 registers is answered, so `max_span` needs no
> lowering. A whole-device poll took 3679 ms at `message_spacing=0.05`; the old
> code's 0.6 s between model reads was unnecessary on this firmware.

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

> **Settled, and the library was wrong.** Measured on model 704, ~1.5 kW for
> 8 s per run, every write verified by read-back:
>
> | `704.WSetPct` | `714.DCW` | `701.W` (grid) | Result |
> |---|---|---|---|
> | **-30%** | **-1500 W** | +1756 W import | **charges at 1500 W** |
> | +30% | 0 W | 285 W | no dispatch |
> | +100% | 0 W | 288 W | no dispatch |
>
> A negative `WSetPct` charges. A positive one moves nothing at all — it is not
> a discharge command, it is a command the device ignores. `async_send_command`
> inverts correctly; the mode calculators were the inverted half, and both
> peak-shave and the TOU discharge branch would have commanded a *charge*.
> Fixed, with `tests/test_modes.py` covering every calculator.
>
> **Still open:** peak-shave and TOU were not run directly. That both would
> have misbehaved is inference from the two positive-setpoint observations.
> Also open: whether discharge is reachable through some other point. The 1547
> profile does not require `WSetPct` at all — its active-power control is
> `WMaxLimPct`, a limit rather than a signed setpoint — and neither source
> defines `WSetPct`'s sign convention anywhere.

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

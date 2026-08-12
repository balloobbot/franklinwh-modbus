# Migrating franklinwh-modbus to modbus-connection

This library used to talk to a FranklinWH aGate through **pysunspec2**'s
synchronous Modbus client, with a hand-assembled raw socket alongside it for
everything pysunspec2 could not reach. It now talks **modbus-connection 4.6.0**
on the **tmodbus** backend, and pysunspec2 is gone from the dependency list
entirely — its model definitions were consumed once, at generation time.

Two results up front:

- **All 17 models the aGate exposes read**, including the seven curve models
  ([issue #156](https://github.com/home-assistant-libs/modbus-connection/issues/156)
  lists them as inexpressible), in **15 pooled block reads** covering 1143
  registers. Every view — battery, grid, solar, control, alarms — is computed
  from that one poll rather than issuing its own reads.
- **Writing a four-point volt-var curve went from 17 round trips to 4.** The 17
  is measured, and matches issue 156's estimate exactly.

**Caveat, stated once and meant throughout: there is no aGate here.** Everything
below is verified against a reconstruction of the device's register map, not
against hardware. What makes the reconstruction trustworthy is described in the
next section; what it cannot tell us is whether the device behaves as its
documentation says. [HARDWARE-VERIFICATION.md](HARDWARE-VERIFICATION.md) lists
exactly what would settle each open question, and
`scripts/hardware_check.py` runs the read-only half of it.

---

## 0. The register map, and why it can be trusted

There is no register dump in this repository — the prose refers to one, but what
is committed is documentation, not capture. So the map was **reconstructed**:
the SunSpec model definitions for models 1, 502 and 701–715, laid out in chain
order and sized with the counts issue 156 reports.

That reconstruction reproduces **29 of the 29** absolute addresses documented in
`SUNSPEC_MODEL_REFERENCE.md`, exactly:

```
M1 @2 (L=66)   M701 @70 (L=153)  M702 @225  M703 @277  M704 @296
M705 @363 (L=67)  M706 @432  M707 @465 (L=105)  M708 @572
M709 @679 (L=135) M710 @816  M711 @953  M712 @987
M713 @1033  M714 @1042  M715 @1087   end @1126
```

This is a stronger check than it looks, and it cuts both ways:

- **It confirms the counts.** M705–M712's lengths are decided *entirely* by
  `NPt` / `NCrv` / `NCrvSet`. M713 sits behind all of them. If any count were
  wrong, every documented address from 1035 onward would miss. They all land, so
  `NCrv=3, NPt=4` (705), `NCrv=2, NPt=2` (706), `NCrvSet=2, NPt=5` (707–710),
  `NCtl=2` (711), `NCrv=2, NPt=6` (712), `NPrt=1` (714) are right.
- **It corrects one thing.** Model 502 is **not** between M1 and M701. Every
  documented address is exactly 30 (= 2 + 28) lower than a chain containing it
  there, and that offset holds all the way through M715 — so 502 sits after 715
  or elsewhere. The fixture places it after 715; nothing in the library depends
  on where.

`scripts/build_agate_fixture.py` builds the map,
`tests/fixtures/agate_registers.py` is the result, and
`tests/test_register_map.py` is the check — 48 assertions over the documented
addresses, the chain layout, the decoded identity strings and the count points.

---

## 1. What weird things does this library do?

**It hand-assembles Modbus TCP frames onto a raw socket.** The FranklinWH
extension registers at 15500+ are outside the SunSpec chain, and pysunspec2 has
no way to reach an address it did not discover. So the old code did this, in
six places across `controller.py` and `sequencer.py`:

```python
req = struct.pack('>HHHBBHH', 0, 0, 6, self.unit_id, 6, self.EXT_ONGRID_MODE, mode)
sock.sendall(req)
resp = sock.recv(256)
```

Transaction ID hard-coded to `0`, no framing loop on the response, no length
check before indexing `resp[7]`, and a second hand-rolled frame for the
read-back. The 32-bit variant packs its own FC16 header byte by byte. All of it
is now one 13-field `Component` (`models/extensions.py`) with declared
addresses, and the block joins the same pooled read as the SunSpec models.

**Every write is verified by reading it back — because the device lies.** The
aGate answers a write it intends to discard with a success echo carrying the
*stored* value, not an exception. Writes to the extension block fail this way
whenever the installer has not enabled the "SPAN Modbus" option, and the old
code knew it:

> *"FC06 response is just an echo. We MUST perform a separate read to verify the
> write actually STUCK in hardware. This catches cases where the device is
> read-only but echoes success."*

This is not a quirk to route around; it is load-bearing. `writing.py` verifies
every write and raises `WriteRejected` naming what did not take.

**Writing one register resets its neighbours.** Writing 15507 (operating mode)
resets 15508 and 15509 (the two SOC reserves) to a default. So
`async_set_native_mode()` writes all three in one FC16, rewriting the reserves
to the values they already hold. Batching here is a *correctness* requirement,
not a saving — three sequential single-register writes are not equivalent to one
three-register write.

**The hardware's safety timer is decorative.** Model 704's `WSetRvrtTms` counts
down and then does nothing: the countdown reaches zero and `WSetEna` and
`WSetPct` are unchanged, observed for 186 s past expiry. So the only thing that
ever puts the device back is a software timer on this side, and the control loop
releases control in a `finally`. Any unattended use *must* pass `duration_s`.

**Control is a three-phase sequence with settling between phases.** Stop
(`WSetEna=0`), configure (`WSetMod`, `WSetPct`), enable (`WSetEna=1`), with
300–500 ms between. A setpoint written while the enable register is still set is
ignored. `WSetPct`'s sign is also inverted relative to the library's own
convention — positive watts means charge here, and negative `WSetPct` on the
device.

**Model 713's `Sta` is always 0, and model 714's `DCA` is always 0.** So battery
state is derived from the sign of DC power with a ±50 W deadband, and DC current
is derived as total power over the mean of the live port voltages. Both
workarounds survive the migration unchanged.

**The mode calculators' sign convention is inconsistent — and is preserved.**
`BatteryCommand` documents positive as charge, most of the arithmetic follows
it, but `_calc_self_consumption` returns `-max_charge_w` for "charge flat out"
and both peak-shave and the time-of-use discharge branch return a *positive*
number to discharge. This is reproduced exactly rather than corrected: it is the
shipped behaviour and there was no hardware to re-tune against. Flagged at the
top of `modes.py`.

**Conflict detection has to infer who is driving.** The vendor cloud API and the
aGate's own modes both move the battery without ever setting `WSetEna`, so the
only evidence is DC power moving while remote control is off — and most such
movement is *correct* (charging from excess solar in Self-Consumption is the
mode working). `safety.py` reads it against solar, load and grid, and prefixes
the merely-informational cases with `INFO:`.

**The sequencer's tag grammar is a user-facing contract.** `704.WSetPct`,
`714.DCW_1`, and a bare `15507`. The shipped JSON sequences in
`examples/sequencer/` depend on it, so it is unchanged — but a bare address now
resolves to a field on a component instead of triggering the raw-socket path.

---

## 2. What internals of modbus-connection did I have to touch?

**No monkeypatching, no subclassing of a private class, no reaching around the
connection.** On 4.3 this section listed four private attributes in
`writing.py`, because planning a batched write meant re-deriving from private
state what the read path resolves internally:

```python
component._register_fields   # to look up a field by name
component._address(field)    # to resolve its absolute address
component._scale_address(f)  # to resolve its scale register
component._unit              # to issue the write
```

**4.4 makes all four public.** `Component.resolved_fields` is a mapping of
field name to a `ResolvedField` carrying the field, its absolute address, its
register count, its scale register's absolute address and its space — the read
path's own resolution, exposed as data — and `Component.modbus_unit` gives the
unit. `writing.py` now reads placements straight off it and touches nothing
private. `scripts/hardware_check.py` did the same for the one thing it needed,
a referenced `sunssf`'s resolved address.

What is still missing is the *planner*, not the placement: everything the read
path groups and batches through `ReadPlan` has no write-side counterpart, and
`Component.write()` writes one field. That part of §3.1 stands.

Two private uses remain:

- `component._groups` in `sequencer.py`, to resolve a `714.DCW_1` instance
  suffix. `RepeatingGroupField.__get__` gives the instances by attribute name,
  but there is no way to ask "what repeating groups does this component have",
  which is what an index-by-position tag needs.
- `SunSpecComponent._verify_read()` is called directly in a test. It runs
  automatically on every refresh; calling it explicitly is just asserting on it.

**One thing that could not be done through the public API at all:** the seven
curve models. See §4.

---

## 3. What could modbus-connection do better?

Ordered by how much each cost. Everything here is grounded in this device; where
it is not, it says so.

### 3.1 There is no write planner — and the run that matters spans components

Issue 156 proposes `Component.write_many({field: value, …})`. That is the right
shape but it is **not sufficient**, and the measurement is the argument.

Model 705's real layout, writing one four-point curve:

| | write requests | scale-factor reads | round trips |
| --- | --- | --- | --- |
| `Component.write()` per field | 9 (all FC06) | 8 | **17** |
| `write_many()` per component | 5 (FC06 + FC16) | 8 | **13** |
| `write_across()` over the set | 2 (FC16 + FC06) | 2 | **4** |

The 17 reproduces issue 156's estimate exactly. But per-component batching only
reaches 13, because **a curve's points are one sub-component each**: the eight
contiguous registers of a four-point curve span four `DERVoltVarCrvPt`
instances. A planner scoped to one component cannot see across them, and each
one re-reads the same two scale factors from the model's fixed block.

So the ask is not `Component.write_many` but a planner over a **set of
(component, field, value) entries** — or equivalently, one that descends a
component's sub-instances. `writing.py::write_across` is the prototype.

Two constraints it found that a naive port of `ReadPlan` would get wrong:

- **A write plan must not merge across gaps.** `ReadPlan` merges spans within
  `max_gap` because over-reading is free. Over-*writing* is not: touching a
  register the caller did not name is a bug. `_plan()` groups strictly
  contiguous runs only.
- **Grouping has to express intent, not just adjacency.** This device wants its
  704 control writes *ordered* with the enable register last. An optimiser free
  to reorder or coalesce would break that. The three phases stay three calls.

**Half of this shipped in 4.5.0**, from the other end: the SunSpec *generator*
now emits a `write_<block>` method for every repeated block whose points are all
writable, so `_generated.py` carries `crv[0].write_pt(points)` on the 705, 706,
707–710 and 712 curve blocks and on 704's power-factor blocks. It plans exactly
the run `write_across` finds — measured on model 705, the same FC16 of 8
registers at 388 after the same two scale reads.

`write_curve` stays on `write_across` regardless, because the block writer is
the plan without the guarantees this device needs: it does not verify (3.2), has
no `settle`, and does not know about `ActPt` (3.4). Adopting it would trade two
of the three reasons this layer exists for zero saved round trips.

### 3.2 Nothing verifies a write

`write()` returns once the request is acknowledged. On a device that
acknowledges writes it discards, that means nothing. Every consumer of such
hardware writes the same read-back loop; a `verify=True` option on the write
path (with a `settle` delay, since the device applies asynchronously) would
serve all of them. `WriteRejected` naming the fields that did not take is the
useful failure.

### 3.3 `writable` cannot depend on a sibling register

Every curve carries a `ReadOnly` point saying whether *that curve instance* may
be written. `RegisterField.writable` is a property of the field, shared by every
instance of the sub-component, and `WriteValidator = Callable[[Any], Any]`
receives only the value — so it cannot consult a sibling.

Confirmed against the real layout, and it matters here precisely because the
device accepts writes it should reject: marking the points writable means a
write to a read-only curve silently appears to succeed. `curves.py::is_writable`
checks it by hand before writing. **Passing the owning component to the
validator would be enough.**

### 3.4 `ActPt` versus `NPt` has no expression

A curve's storage is `NPt` points and its addresses are fixed by `NPt`, but only
the first `ActPt` mean anything — the rest are allocated slots holding whatever
was there last. Every consumer re-derives this. `read_curve()` truncates and
`write_curve()` sets `ActPt` last, so a curve never claims more active points
than it holds. Minor next to the rest, but it appears on all seven curve models
and the framework has no word for it.

### 3.5 One member's readable ranges poisoned a `ComponentGroup` — fixed in 4.4

The extension block's map is known exactly: 15500–15513 and 16000, with 486
dead registers between. Declaring that is the *more* correct thing to do — and
on 4.3 it made the component unpoolable:

```
ValueError: every holding-space component in a ComponentGroup must declare
register_ranges if any does, but some left it unset
```

The SunSpec components have no reason to declare ranges (`scan()` tells them
what is there). So the choice was: state the map and lose pooling, or drop the
map and keep it. This library dropped it, with a comment saying why.

**[#160](https://github.com/home-assistant-libs/modbus-connection/pull/160)
resolved it**, and along the lines argued here: an undeclared member now stands
for the addresses it reads by itself rather than conflicting with a member that
declared something. `Extensions.register_ranges` states the two runs again.

The change is not free, and it is worth being precise about the cost. A group
no longer bridges gaps with `max_gap`; it plans against the union of what its
members declare or claim. That is stricter in the right way — a pooled read can
no longer wander into addresses nobody claims — but it costs this device one
extra request. Model 1's last point is a `Pad` the generated component does not
read, so register 69 sits between M1's claim and M701's and belongs to neither,
and M1 can no longer join the run behind it. **15 block reads rather than 14.**
Everything from 70 to 963 is still one merged span. A fair trade for a rule
that was blocking a correct declaration.

### 3.6 The nested-count and dynamic-placement gaps

This is issue 156's items 1 and 2. Fully worked, with a prototype — see §4.

### Things that went right

- **The tmodbus swap is one import line and one extra in `pyproject.toml`.** The
  whole suite passes on either backend. That is the backend-neutrality claim
  actually holding up.
- **`SunSpecComponent`'s header verification pays for itself twice here.** It
  catches a firmware that moved a model — *and*, because a curve model's length
  is decided by its counts, it catches a device whose counts differ from the
  ones the components were generated for. That is the exact failure mode the
  static-count approach in §4 is exposed to, and the library detects it for free.
- **Pooling.** 17 models plus the extension block, one poll, 15 block reads.
  Every read view is then free, which changed the shape of the code: the old
  controller re-read a model per accessor.
- **`resolved_fields` closed the last private-attribute hole** (§2). It arrived
  as a read-path diagnostic, but what it exposes is exactly what a write needs
  to know about a field, so the batched-write module went from four private
  attributes to none.
- **The per-type unimplemented sentinels, `scale_register` resolving inside the
  pooled block, and shared factors staying put across a repeating block** all
  did the right thing with no adjustment.
- **`message_spacing`** replaced hand-rolled `time.sleep()` between reads.

---

## 4. Issue 156: what got working, what did not

*Draft comment for
[home-assistant-libs/modbus-connection#156](https://github.com/home-assistant-libs/modbus-connection/issues/156).*

---

I migrated **[franklinwh-modbus](https://github.com/balloobbot/franklinwh-modbus/tree/migrate-modbus-connection)**
onto 4.4.0 — the aGate this issue was written from, as a *concrete hardware*
consumer rather than a generic one. Knowing exactly which models and counts the
device has turns out to change the answer, so this is a report on what the seven
blocked models actually need.

Branch with a working prototype: **`sunspec-1547-curve-models`** (not a PR).

### First: the counts in this issue are independently confirmed

There is no register dump committed in that repo — only documentation. So I
rebuilt the map from the SunSpec model definitions, laid out in chain order and
sized with the counts reported here. It reproduces **29 of 29** documented
absolute addresses exactly.

That is a real check on the counts rather than a restatement of them: M705–M712's
lengths are decided *entirely* by `NPt` / `NCrv` / `NCrvSet`, and M713–M715 sit
behind all of them. If any count were wrong, every address from 1035 on would
miss. They all land.

It also corrects one detail: **M502 is not between M1 and M701.** Every
documented address is exactly 30 (= 2 + 28) lower than a chain containing it
there, and that holds through M715 — so 502 is after 715 or elsewhere.

### Status: all 7 read; 4 of the 5 asks are confirmed, 1 is understated

| | | Status |
| --- | --- | --- |
| 1 | Nested count shifts with the parent instance | **Confirmed.** Fixed in the prototype. Note it is *tested* behaviour today, so changing it is a decision, not a bugfix — see below. |
| 2 | `stride` must be a static `int` | **Confirmed, and understated.** A dynamic stride alone does not express 707–710. |
| 3 | No batched write | **Confirmed, and understated.** `Component.write_many` is not enough; the contiguous run spans components. |
| 4 | Writability is static, profile makes it per-instance | **Confirmed.** Worked around by hand. |
| 5 | `ActPt` vs `NPt` | **Confirmed.** Worked around by hand. |

### Item 1 — the nested count

Reproduced. `repeating_group` takes a `count_in_block` keyword saying whose
coordinates the count register's address is stated in; passing `False` states it
in the owning layout's coordinates, which is what every SunSpec map means.

**The default stays as it is** — the count keeps moving with the enclosing
instance, so nothing changes for anyone who does not pass the flag. My first
version flipped the default, arguing symmetry with `scale_register` (which does
default to not moving). That was wrong: the case where the two differ fails
*silently*, which is why the bug is nasty and equally why flipping the default
could quietly change what an existing consumer reads.

It is a per-group keyword rather than a class attribute like `scale_in_block`,
because a component can own two groups counted differently, and because a new
keyword with a compatible default cannot break anyone.

The compatibility claim in the only form worth making: the test diff is
**purely additive**, 134 insertions and no deletions.
`test_nested_dynamic_in_static` and `test_nested_dynamic_in_dynamic`, which both
assert that instance 1 reads its count from `count + stride`, are byte-identical
to `main` and still pass.

### Item 2 — placement, not just stride

A callable `stride` fixes 705, 706 and 712. It does **not** fix 707–710, and
this is the part I would most want to correct in the issue.

Each `Crv` in 707–710 contains three same-shaped regions — `MustTrip`,
`MayTrip`, `MomCess` — at offsets `0`, `S` and `2S` where `S = 1 + NPt*3`. The
problem is not only the enclosing stride; it is that **`MayTrip`'s own field
addresses depend on `NPt`**. A stride places repeats of one block. It cannot
place a *sibling* after a runtime-sized one.

You can dodge it by collapsing the three regions into one `repeating_group(3, …)`
with a dynamic stride, since they are structurally identical — but that throws
away the names the spec gives them, and `crv.region[1].pt[0]` is a worse API than
`crv.may_trip[0].pt[0]`.

So the prototype adds **`offset`** alongside `stride`, both accepting
`int | Callable[[Component], int]`:

```python
class TripCrv(Component):
    read_only  = enum16(9)
    must_trip  = repeating_group(1, TripRegion, stride=1)
    may_trip   = repeating_group(1, TripRegion, stride=1, offset=_region)
    mom_cess   = repeating_group(1, TripRegion, stride=1,
                                 offset=lambda m: 2 * _region(m))

class TripLV(SunSpecComponent):
    n_pt = uint16(5)
    crv  = repeating_group(uint16(6), TripCrv,
                           stride=lambda m: 1 + 3 * _region(m))
```

The callable receives the component whose block the addresses are relative to —
the outermost layout, not the immediate parent — because that is where SunSpec
puts count points.

**The machinery for this already exists.** Register-counted groups are built in
`_refresh_repeating_groups`, i.e. *after* the fixed block has been read. So a
dynamic stride needs no new pass; the only rule to add is that a group with a
dynamic stride or offset is resolved in that second pass even when its count is
a fixed `int` (it stops folding into the parent's block read). That is a small
change to `_build_instances` and the static/repeating split.

With items 1 and 2, **all seven models read correctly**, at full nesting depth,
with the three named trip regions preserved.

I would rather have this than an `async_resolve(unit)` step: it keeps the layout
declarative and keeps the per-poll re-read, where a resolve step freezes the
counts at setup.

### The cheaper fix that unblocks all seven — already shipped

Worth separating, because it is much smaller than the above, and it is what this
library actually ships.

If you are generating for **one** firmware, the counts are not a runtime unknown.
Give the generator the values the device reports and the whole layout is static:

```
python -m modbus_connection.model.sunspec.generate \
  --count 705:NPt=4 --count 705:NCrv=3 \
  --count 707:NPt=5 --count 707:NCrvSet=2  ...
```

Without it the generator leaves 705/706/712's curve group commented out and
**refuses 707–710 outright** (`group 'MustTrip' has a device-dependent size but
is not the last block`). With it, all seven emit as ordinary fixed-count
`repeating_group`s and read correctly — no library changes at all.

Nested *static* groups already work three levels deep; nothing was broken there.
The blockers are only ever about counts unknown at author time.

Two honest limits: it bakes one device's counts into the generated classes, and
it loses the per-poll re-read. The first is less dangerous than it sounds —
`SunSpecComponent`'s header check catches it, because a curve model's length is
a function of its counts, so a device with different counts fails loudly on the
first read rather than reading garbage. That is a nice property and it came free.

**This landed upstream as
[#158](https://github.com/home-assistant-libs/modbus-connection/pull/158) while
this migration was being written**, converging on the same design including the
model scoping. `src/franklinwh_modbus/models/_generated.py` is byte-identical to
what released `main` now produces, so the file is reproducible with a released
tool rather than a local patch. My own proposal
([#162](https://github.com/home-assistant-libs/modbus-connection/issues/162)) was
closed as a duplicate — I had been generating against a checkout a day stale.

It also does one thing my version did not: rejects a `--count` naming a point
that sizes nothing, so a typo cannot silently do nothing.

### Item 3 — batched writes: the run spans components

Measured against model 705's real shape (`NCrv`=3, `NPt`=4), writing one
four-point curve:

| | write requests | scale-factor reads | round trips |
| --- | --- | --- | --- |
| `Component.write()` per field | 9 (all FC06) | 8 | **17** |
| `write_many()` per component | 5 | 8 | **13** |
| planned over the whole set | 2 | 2 | **4** |

The 17 matches this issue exactly. But `Component.write_many` only reaches 13 —
because **a curve's points are one sub-component each**, so the eight contiguous
registers span four components. A per-component planner cannot see across them,
and each re-reads the same two scale factors from the model's fixed block.

So I would restate the ask: not `Component.write_many({field: value})`, but a
planner over **(component, field, value) entries** — or one that descends
sub-instances. Prototyped as `write_across()` in the migrated library.

Two constraints found while writing it, both arguing against reusing `ReadPlan`:

- **A write plan must not merge across gaps.** `ReadPlan` merges within
  `max_gap` because over-reading is free; over-writing is not.
- **Grouping must express intent.** This device needs its 704 control writes
  *ordered*, enable last. An optimiser free to coalesce or reorder breaks it.

Related, and I would fold it in: **nothing verifies a write.** This device
acknowledges writes it discards, so `write()` returning successfully means
nothing. Every consumer of such hardware writes the same read-back loop.

### Items 4 and 5 — confirmed, worked around

`ReadOnly` per curve instance: confirmed. Passing the owning component to the
validator would be enough. It matters more than it looks here — because the
device accepts writes it should reject, marking curve points writable means a
write to a read-only curve *silently appears to succeed*.

`ActPt` vs `NPt`: confirmed, on all seven models. Both are handled by hand in
`curves.py`.

### One more, not in the issue — since fixed

**A `ComponentGroup` refused to pool a member that declares `register_ranges`
with members that do not.** The aGate's manufacturer block at 15500 has a known,
holey map (15500–15513 and 16000); the SunSpec models have no reason to declare
anything. Stating the map correctly was what made the component unpoolable.

[#160](https://github.com/home-assistant-libs/modbus-connection/pull/160) landed
in 4.4 and an undeclared member now stands for what it reads by itself, so the
map is declared again. Costs this device one extra request — see §3.5.

### Caveat

**No aGate was available.** All of this is verified against the reconstructed
map described above, which is exact on addresses and layout, and says nothing
about behaviour. The device-lies-about-writes and the reset-the-neighbours
behaviours are taken from that repo's own code comments and from the second
owner's report in the ha-sunspec notes, not observed here.

---

## Appendix: what the migration ships

```
src/franklinwh_modbus/
  models/_generated.py   1772 lines, all 17 models, generator output
  models/extensions.py   the 15500 block, replacing the raw-socket path
  device.py              AGate: scan, one pooled poll, control
  writing.py             batched + verified writes (write_across)
  curves.py              the 1547 curve models: ActPt, ReadOnly, whole-curve writes
  sequencer.py           the JSON sequence engine, tag grammar unchanged
  safety.py              check_state, SOC validation, conflict detection
  modes.py               the virtual-mode control loop
  sync.py                blocking facade for the TUI and CLI
```

`controller.py` (2210 lines) is deleted. 123 tests run the whole stack against
the reconstructed map, including a mock device that acknowledges writes and
discards them.

**Not carried across:** nothing was dropped for convenience, but two behaviours
changed shape. The extension writability probe no longer runs at connect time —
it was a side effect of connecting, and now every write verifies itself, so
`--test-extension-write` asks each register to accept the value it already
holds. And `reconnect()` is now "connect again" rather than a bespoke retry
path, because the connection layer handles the rest.

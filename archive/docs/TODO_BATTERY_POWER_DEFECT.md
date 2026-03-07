# TODO: Fix Battery Power Display Inconsistency

## Defect

**Status:** ✅ **RESOLVED** - Fixed 2026-02-08, tested and verified

**Reported:** 2026-02-08

**Screenshot Evidence:**
```
Battery Power Card:        Power Flow Summary:
  -1 W ↓                     Battery ↑ 400 W
  Charging                   (Discharging implied by ↑)
```

**Problem:**
Two dashboard widgets showing **contradicting** battery power data:

1. **"Battery Power" card** (left):
   - Value: `-1 W`
   - Arrow: `↓` (down)
   - Label: "Charging"

2. **"Power Flow Summary" card** (right):
   - Value: `400 W`
   - Arrow: `↑` (up)
   - Direction: Discharging (implied by up arrow)

**Inconsistencies:**
- ❌ Different values: `-1 W` vs `400 W`
- ❌ Opposite arrows: `↓` (charging) vs `↑` (discharging)
- ❌ Opposite states: "Charging" vs discharging

---

## Root Cause Investigation Needed

### Possible Causes:

1. **Sign Convention Mismatch:**
   - Battery Power uses: `-` = charging, `+` = discharging
   - Power Flow uses: `+` = charging, `-` = discharging
   - OR one widget inverts the sign incorrectly

2. **Different Data Sources:**
   - Battery Power: Reading from `liveData.battery_power`
   - Power Flow: Reading from different register or calculated value
   - Backend may be returning different values to different endpoints

3. **Arrow Direction Logic Error:**
   - One widget has inverted arrow logic
   - `↑` should mean discharging (power out)
   - `↓` should mean charging (power in)

4. **Stale Data:**
   - One widget not updating properly
   - Different refresh rates causing desync

---

## Expected Behavior

**Both widgets should agree:**

**If Battery is Charging (400W):**
- Battery Power: `+400 W ↓ Charging`
- Power Flow: `Battery ↓ 400 W`

**If Battery is Discharging (400W):**
- Battery Power: `-400 W ↑ Discharging`
- Power Flow: `Battery ↑ 400 W`

**Sign Convention (industry standard):**
- **Positive** = Discharging (power OUT of battery)
- **Negative** = Charging (power INTO battery)

---

## Files to Investigate

### Frontend Templates:
1. **`templates/dashboard.html`**
   - Battery Power widget rendering
   - Power Flow Summary widget rendering
   - Check which `liveData` fields each uses

### Frontend JavaScript:
2. **`static/js/app.js`**
   - `liveData.battery_power` assignment
   - Arrow direction logic
   - "Charging" / "Discharging" label logic

### Backend:
3. **`src/modbus_client_franklinwh.py`** or **`src/modbus_client.py`**
   - Battery power register reading
   - Sign handling for charge/discharge
   - Check if sign is inverted anywhere

4. **`src/web_server.py`**
   - `/api/live-data` endpoint
   - Battery power field mapping
   - Verify data transformation

---

## Investigation Steps

1. **Check data source:**
   ```bash
   curl http://localhost:8080/api/live-data | jq '.battery_power'
   ```
   Verify what the backend is actually returning.

2. **Review sign convention:**
   - Check SunSpec Model 713 battery power register
   - Verify if register uses `+` for discharge or `+` for charge
   - Ensure backend reads it correctly

3. **Check widget logic:**
   - Find Battery Power widget template in `dashboard.html`
   - Find Power Flow Summary template
   - Compare their `liveData` field usage

4. **Test with known state:**
   - Force battery to discharge at known rate (e.g., 2000W)
   - Verify both widgets show: `↑ 2000 W Discharging`

---

## Priority

**Priority:** 🔴 **HIGH**

**Impact:**
- Users cannot trust battery power data
- Incorrect display may lead to wrong manual decisions
- Undermines confidence in entire dashboard

**User Impact:**
> "Battery Power card on main dashboard page disagrees (is wrong) with Power Flow card Battery values and arrow icon direction"

---

## Related

- May be related to conversation 3de456e9 `WEB_UI_DEFECTS.md` (Zero-as-None logic issue)
- Check if this is a sign convention problem similar to other power fields

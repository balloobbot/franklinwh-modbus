# TODO: MQTT Settings Corruption Bug

## Status

**Status:** ✅ **RESOLVED** - 2026-02-08 ✅ **User Confirmed Working**

**Severity:** 🔴 **CRITICAL** - Data loss bug (now fixed)

---

## Problem

Settings modal was **overwriting MQTT credentials** with empty defaults when user saved any settings (e.g., toggling a widget).

**User Impact:**
- User had working MQTT connection with credentials
- Opened Settings modal, changed a widget setting, clicked "Save"
- MQTT credentials were **wiped out** → connection broken
- Required manual re-entry of credentials and restart

---

## Root Cause

**File:** `static/js/app.js`

### Issue 1: Hardcoded Empty Defaults
Lines 243-249 had hardcoded default MQTT config with **empty credentials**:

```javascript
mqtt: {
    host: '192.168.0.109',
    port: 1883,
    username: '',      // ❌ EMPTY!
    password: '',      // ❌ EMPTY!
    enabled: false     // ❌ DISABLED!
}
```

### Issue 2: Settings Modal Sent MQTT Even Though No UI
Lines 642-665 in `saveSettings()` sent **entire MQTT config** to API:

```javascript
mqtt: {
    host: this.config.mqtt.host,        // ← Empty from defaults!
    port: this.config.mqtt.port,
    username: this.config.mqtt.username, // ← Empty!
    password: this.config.mqtt.password, // ← Empty!
    // ... 20+ more fields
}
```

**The Bug:**
1. Page loads → Alpine initializes `this.config.mqtt` with hardcoded **empty** defaults
2. Settings modal has **NO MQTT section** in UI (MQTT managed via `/mqtt-admin` page)
3. User saves Settings → sends `this.config.mqtt` with empty credentials
4. Backend receives empty credentials → **OVERWRITES** `data/config.json`
5. User's real MQTT credentials **LOST**

---

## The Fix

**Removed MQTT from Settings payload** (lines 641-666):

```javascript
// ❌ REMOVED MQTT - Settings modal has no MQTT section, 
// sending it was overwriting saved credentials with empty defaults!
// MQTT settings are managed via /mqtt-admin page only
```

**Now settings payload only includes:**
- ✅ Modbus connection (has UI in Settings modal)
- ✅ Dashboard widgets (has UI in Settings modal)
- ✅ Theme (has UI in Settings modal)
- ✅ Auto-refresh settings (has UI in Settings modal)
- ❌ MQTT (NO UI in Settings modal → not sent)

---

## Why This Happened

**Last Night's Settings Modal Fix** (conversation 9ee92100) was actually about **Status Badges**, not settings. The settings save logic has been this way for a while, but user didn't notice until now because:

1. MQTT was already configured
2. User rarely used Settings modal
3. Bug only triggers when Settings modal is saved

---

## Verification

After fix, Settings modal now:
- ✅ Saves Modbus settings correctly
- ✅ Saves widget toggles correctly
- ✅ Saves theme correctly
- ✅ Does NOT touch MQTT config at all
- ✅ MQTT credentials remain intact in `data/config.json`

---

## Prevention

**Design Rule:** Settings modal payload should **ONLY** include fields that have UI controls in the modal.

**If adding new settings:**
1. Add UI controls to Settings modal template
2. Add fields to `saveSettings()` payload
3. OR manage via dedicated admin page (like MQTT Admin)

---

## Related Files

- `/mqtt-admin` - Dedicated page for MQTT configuration
- `data/config.json` - Where all settings persist
- `src/web_server.py` - `/api/settings` endpoint (handles partial updates)

---

## User Recovery Steps

Since MQTT credentials were wiped:

1. ✅ Go to `/mqtt-admin` page
2. ✅ Re-enter broker credentials
3. ✅ Click "Save Configuration" 
4. ✅ Restart app or wait for auto-reconnect
5. ✅ Verify "Auto-start" checkbox is enabled
6. ✅ With this fix, Settings modal won't overwrite it again

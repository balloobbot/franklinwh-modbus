---
description: Verify implementation is working (mandatory before declaring complete)
---

# Verify Implementation

**MANDATORY**: Run this workflow before declaring any implementation complete.
**Reference**: SAFETY_CONTROLS.md Rule #5

All three checks must pass.

---

## Check 1: Application Logs

// turbo
```bash
tail -100 data/logs/franklinwh.log | grep -iE "error|exception|traceback"
```

Expected: Empty output (or only pre-existing documented errors).

// turbo
```bash
grep -c "ERROR" data/logs/franklinwh.log
```

Compare with baseline count in `AGENT_ERROR_TRACKING.md`.

**Result**: ☐ Pass / ☐ Fail

---

## Check 2: Browser Console

1. Navigate to `http://localhost:8080`
2. Open DevTools (F12) → Console tab
3. Hard refresh: Ctrl+Shift+R
4. Must show **zero** red errors
5. Check Network tab — no failed requests

**Result**: ☐ Pass / ☐ Fail

---

## Check 3: Functional Testing

**ACTUALLY USE IT.** Click buttons, navigate, fill forms.

- ☐ UI renders correctly
- ☐ Buttons/links trigger expected behavior
- ☐ Data displays correctly
- ☐ API calls succeed (Network tab)
- ☐ Changes persist after page reload

**Result**: ☐ Pass / ☐ Fail

---

## Verification Report Template

```markdown
## Verification Results — [Feature Name]

### ✅ Check 1: Application Logs
- Error count: [N] (baseline: [N])
- Log excerpt: `[paste relevant lines]`

### ✅ Check 2: Browser Console
- JS errors: 0
- Failed requests: 0

### ✅ Check 3: Functional Testing
- Tested: [specific actions]
- Edge cases: [what was tested]

**Overall**: ✅ VERIFIED WORKING
```

---

## ❌ If Any Check Fails

1. **Diagnose** root cause
2. **Fix** the issue
3. **Restart** if backend changed (port 8080 only!)
4. **Re-verify** all 3 checks

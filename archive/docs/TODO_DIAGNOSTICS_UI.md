# TODO: Diagnostics Page UI Redesign

## Problem

**Status:** 🟡 **MEDIUM** - UX consistency issue

**Issue:** Diagnostics page (`/diagnostics`) does not match the UI theme and style of other pages in the application.

**Current State:**
- Uses basic Bootstrap table styling
- Plain header with simple buttons
- No alignment with modern design system
- Feels disconnected from main dashboard aesthetic

**Comparison:**
- **Main Dashboard:** Modern glassmorphism, dark mode, cohesive design
- **MQTT Admin:** Uses base.html template, sidebar navigation, consistent styling
- **Diagnostics:** ❌ Bootstrap-only, no template inheritance, inconsistent

---

## Expected Outcome

Diagnostics page should:
- Extend `base.html` template (consistent sidebar/header)
- Use application's design system (colors, spacing, typography)
- Match the visual style of MQTT Admin and main dashboard
- Implement dark mode support
- Modern card-based layout instead of plain tables

---

## Files to Update

1. **`templates/diagnostics.html`**
   - Change from standalone HTML to `{% extends "base.html" %}`
   - Replace Bootstrap-only styling with app design system
   - Modernize data table presentation
   - Add proper dark mode classes

2. **Review for inspiration:**
   - `templates/base.html` - Template structure
   - `templates/mqtt_admin.html` - Admin page styling
   - `templates/dashboard.html` - Main dashboard cards

---

## Priority

**Priority:** 🟡 **MEDIUM**

**Why not higher:**
- Doesn't block functionality
- Page works correctly, just aesthetically inconsistent
- Users can still access all diagnostics data

**When to tackle:**
- After Quick Win #2 (Battery power display)
- After Quick Win #3 (Chart X-axis defect)
- Good candidate for Week 2 polish work

---

## Estimated Effort

⏱️ 2-3 hours

**Breakdown:**
- Template restructuring (1 hr)
- Style updates and dark mode (1 hr)
- Testing and polish (30 min - 1 hr)

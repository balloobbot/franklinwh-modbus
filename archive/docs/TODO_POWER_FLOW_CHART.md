# TODO: Power Flow Chart Enhancements

## Current Status

✅ **Phase 1: COMPLETE**
- Grid power stream added (4th data line)
- User-selectable time scale (15m, 30m, 1h, 3h, 6h)
- Y-axis scale labels with dynamic W/kW formatting
- Zero line indicator for positive/negative values
- Time labels in HH:MM format
- Visual feedback on time scale changes
- Clean legend

## Remaining Work

### Phase 2: Enhanced Visualization

#### Critical Issue: X-Axis Time Span Visualization
**Status:** ✅ **RESOLVED** - Fixed 2026-02-08 (Quick Win #3)

**Problem:** Chart currently auto-zooms to fit available data. If you have 7 minutes of data with a 6-hour time scale selected, the 7 minutes fills the entire chart width instead of appearing as a small segment on the left side of a 6-hour span.

**Solution Implemented:**
- Changed X-axis positioning from index-based to time-based
- Data points positioned by timestamp within selected window
- Added "Now" marker at right edge  
- Fixed time labels show absolute positions (not data timestamps)
- Old data filtered out when older than selected window

**See:** [`walkthrough.md`](file:///home/david/.gemini/antigravity/brain/cc001a88-c7d9-45b6-8330-9c7b074d621d/walkthrough.md) for full implementation details

**Problem:** Chart currently auto-zooms to fit available data. If you have 7 minutes of data with a 6-hour time scale selected, the 7 minutes fills the entire chart width instead of appearing as a small segment on the left side of a 6-hour span.

**Expected Behavior:**
- Data points should appear at correct relative positions within selected time window
- Empty portions of time window should show grid but no data
- Current time marker should show position within window
- Example: 7 minutes of data in a 6-hour window should fill ~2% of chart width

**Implementation:**
- [ ] Calculate absolute time positions within window
- [ ] Render full time scale range (even with partial data)
- [ ] Add current time indicator
- [ ] Show data density/coverage indicator

**Priority:** High - Affects user's ability to understand data context

---

#### Dual Y-Axis Support
- [ ] **Left Y-axis**: Power (W or kW) - primary scale
- [ ] **Right Y-axis**: SOC% overlay (optional)
- [ ] Add toggle for SOC% overlay
- [ ] Implement dual-scale calculation and rendering
- [ ] Add scale labels and gridlines for both axes

**Use Case:** See discharge rate AND battery level on same chart

---

#### Chart Type Selection
- [ ] **Line Chart** (current implementation)
- [ ] **Bar Chart** mode
- [ ] **Stacked Bar Chart** mode
- [ ] Add dropdown selector for chart type
- [ ] Maintain data streams across chart types

**User Request:** "user-selectable option to switch chart type/style [only bar and bar-stack]"

---

#### Time-Span Selector with Dynamic Data Loading

**Status:** ⚠️ **NOT TRIVIAL** - Requires backend work

**Current Implementation:**
- Time scale selector exists (15m, 30m, 1h, 3h, 6h)
- Uses in-memory `chartData` array (limited to current session data)
- No DB retrieval, no historical data

**Requested Feature:**
User wants dropdown time-span selector that:
1. **Fetches data from database** for selected time span
2. **Re-scales Y-axis** (left kW scale) to fit data range dynamically
3. **Re-generates timeline** to align with dataset returned
4. **Proper time labels** matching the selected span granularity

**Agent Assessment:** "Not a trivial amount of work to implement"

**Why It's Complex:**
- Requires backend database storage (Phase 3)
- Need `/api/chart/data?start={ts}&end={ts}&resolution={30s|1m|5m}` endpoint
- Dynamic Y-axis scale calculation based on data range
- Time label generation logic for different granularities
- Data decimation for longer time spans
- Performance optimization for large datasets

**Implementation Requirements:**
- [ ] Backend: Historical data storage (SQLite)
- [ ] Backend: Chart data API with time range parameters
- [ ] Backend: Data aggregation (30s → 1m → 5m → 15m)
- [ ] Frontend: Detect time-span change
- [ ] Frontend: Fetch data from API for selected span
- [ ] Frontend: Calculate Y-axis min/max from dataset
- [ ] Frontend: Generate appropriate time labels (HH:MM or HH:00 or DD/MM)
- [ ] Frontend: Re-render chart with new scales

**Estimated Effort:** 1-2 weeks (backend + frontend)

**User Request:** "TODO / future work" (conversation not captured)

---

### Phase 3: Viewing Modes

#### Mode A: Real-Time (Current)
- [x] Currently implemented ✅
- [ ] Add explicit "Real-Time" badge/indicator
- [ ] Show live refresh countdown
- [ ] Auto-scroll to show latest data

#### Mode B: Historical (Past Time/Date Range)
- [ ] Add date/time range picker
- [ ] Fetch historical data from backend API
- [ ] Disable auto-refresh in historical mode
- [ ] Add zoom/pan controls for exploring data
- [ ] Export historical data (CSV/JSON)

**User Request:** "different mode - (a) real-time [current] (b) historical - past time/date-range"

---

## Backend Requirements

### Data Collection
- [ ] Implement configurable retention periods for different time scales
- [ ] Create historical data API endpoint (`/api/chart/historical`)
- [ ] Add database storage for long-term historical data
- [ ] Data aggregation (30s → 1m → 5m → 15m → 1h)

### API Endpoints
```python
# New endpoints needed:
GET /api/chart/data?start={timestamp}&end={timestamp}&resolution={30s|1m|5m|15m}
GET /api/chart/config  # Get available time scales, chart types
POST /api/chart/config  # Save user preferences
```

### Database Schema
```sql
CREATE TABLE chart_data_historical (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    solar_w REAL,
    home_loads_w REAL,
    battery_w REAL,
    grid_w REAL,
    soc_pct REAL,
    resolution TEXT DEFAULT '30s',  -- 30s, 1m, 5m, 15m, 1h
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chart_timestamp ON chart_data_historical(timestamp);
CREATE INDEX idx_chart_resolution ON chart_data_historical(resolution);
```

---

## UI/UX Design

### Chart Controls Panel
```
┌───────────────────────────────────────────────────────────┐
│ [📊 Real-Time ▼] [⏱️ 30 min ▼] [📈 Line ▼] [⚙️ Settings] │
├───────────────────────────────────────────────────────────┤
│                    Chart Area (SVG)                       │
│                                                           │
│  [Legend: Solar | Home | Battery | Grid | SOC%]          │
└───────────────────────────────────────────────────────────┘
```

### Settings Panel (Modal/Drawer)
- [ ] Toggle data streams (Solar, Home, Grid, Battery, SOC%)
- [ ] Y-axis units (W / kW / auto)
- [ ] Grid line density
- [ ] Color customization
- [ ] Smoothing/interpolation options
- [ ] Export options (CSV, JSON, PNG)

---

## Implementation Phases

### Phase 2A: Fix Critical Defect (Week 1)
**Priority:** 🔴 **CRITICAL**
1. [ ] Fix X-axis time span visualization
2. [ ] Add current time indicator
3. [ ] Test with various data densities

**Effort:** 1-2 days  
**Files:** `templates/dashboard.html`, `static/js/app.js`

---

### Phase 2B: Chart Types (Week 2)
1. [ ] Implement bar chart mode
2. [ ] Implement stacked bar chart mode
3. [ ] Add chart type selector dropdown
4. [ ] Test data rendering in all modes

**Effort:** 2-3 days

---

### Phase 2C: Dual Y-Axis (Week 2-3)
1. [ ] Calculate dual scale ranges
2. [ ] Render right Y-axis (SOC%)
3. [ ] Add SOC% data line
4. [ ] Add toggle switch
5. [ ] Test scale synchronization

**Effort:** 2-3 days

---

### Phase 3: Historical Mode (Week 4-5)
1. [ ] Backend: Historical data storage
2. [ ] Backend: `/api/chart/historical` endpoint
3. [ ] Frontend: Date/time range picker
4. [ ] Frontend: Mode switcher (Real-time/Historical)
5. [ ] Frontend: Export functionality
6. [ ] Data aggregation for longer periods
7. [ ] Zoom/pan controls

**Effort:** 1-2 weeks

---

## Technical Considerations

### Performance
- Use data decimation for longer time scales
  - 6h view: 1-minute averages (~360 points)
  - 24h view: 5-minute averages (~288 points)
- Implement virtual scrolling for very large historical datasets
- Consider Web Workers for data processing if needed

### Data Storage
- Keep last 24 hours in memory (current implementation)
- Store 30-day history in SQLite (30s resolution)
- Store 1-year history aggregated (5m resolution)
- Implement automatic cleanup of old data

### State Management
- Store user preferences in localStorage:
  - Selected time scale
  - Chart type (line/bar/stacked)
  - Enabled data streams
  - SOC overlay preference
- Sync preferences to backend for multi-device support
- Maintain separate state for real-time vs historical mode

---

## Related User Requests

From conversation (date unknown):
> "I think some fine tuning is needed for a future TODO: add Grid power, user-selectable time-scale, user-selectable option to switch chart type/style [only bar and bar-stack - NEEDS: Left (power kW or W) or Right scale (if selected SOC% overlay) - different mode - (a) real-time [current] (b) historical - past time/date-range"

> "I am discharging the battery to grid currently - on n off - due to dynamic tariff pricing going up n down in TOU mode :)"

**User Use Case:** Dynamic tariff pricing with frequent on/off discharge cycles
- Historical mode would help review discharge patterns
- Grid power stream would show export timing
- Dual Y-axis would correlate discharge rate with SOC levels

---

## Testing Checklist

### Phase 2A: X-Axis Fix
- [ ] Test with 5 minutes of data in 6-hour window
- [ ] Test with full 6 hours of data in 6-hour window
- [ ] Test with 30 minutes of data in 1-hour window
- [ ] Verify current time indicator position
- [ ] Test time scale switching with partial data

### Phase 2B: Chart Types
- [ ] Line chart renders correctly
- [ ] Bar chart renders correctly
- [ ] Stacked bar chart renders correctly
- [ ] Data stream toggling works in all modes
- [ ] Chart type selector updates chart immediately

### Phase 2C: Dual Y-Axis
- [ ] SOC% scale on right Y-axis
- [ ] Power scale on left Y-axis stays unchanged
- [ ] Toggle SOC overlay on/off
- [ ] Both scales visible and labeled
- [ ] Data lines render on correct scales

### Phase 3: Historical Mode
- [ ] Date range picker functional
- [ ] Historical data loads correctly
- [ ] Auto-refresh disabled in historical mode
- [ ] Export to CSV works
- [ ] Zoom/pan controls functional
- [ ] Switch between real-time and historical modes

---

## Known Issues / Defects

### Issue #1: X-Axis Time Span Visualization ❌ **CRITICAL**
**Severity:** High  
**Impact:** User cannot understand data density or time context  
**Discovered:** Conversation with user (date unknown)  
**Status:** Documented, not fixed

**Workaround:** None

---

## Priority

**Overall:** High - Chart is core feature, several user-requested enhancements

**Phase 2A Priority:** 🔴 CRITICAL - Fixes defect affecting data interpretation  
**Phase 2B Priority:** Medium - Nice to have, user requested  
**Phase 2C Priority:** Medium-High - Valuable for SOC monitoring  
**Phase 3 Priority:** Medium - Advanced feature, less urgent

---

## Dependencies
- None (standalone enhancements)
- Phase 3 benefits from `TODO_PRICING_APIS.md` (correlate prices with discharge)

---

## Notes
- Maintain lightweight SVG approach (no Chart.js)
- Leverage Alpine.js reactivity for smooth updates
- Ensure mobile responsiveness for all new features
- Consider adding chart to MQTT publishing (for Home Assistant graphs)

---

## Original Documentation
This TODO was extracted from `power_flow_chart_enhancements.md` in conversation 9ee92100-366e-45d3-838d-42270447559d, which was NOT migrated to the modbus project TODO list.

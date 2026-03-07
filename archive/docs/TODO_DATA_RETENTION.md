# TODO: Data Retention & Decimation Strategy

## Status

**Priority:** 🟡 **MEDIUM** - Future planning for Phase 3

**Blocked By:** Historical data storage (Phase 3 in TODO_POWER_FLOW_CHART.md)

---

## Current State (In-Memory Only)

**Implementation:** Chart data stored in Alpine.js state arrays
- **Storage:** RAM only, cleared on page refresh
- **Max points:** Auto-calculated based on time scale
  - 15m window: 30 points (30s intervals)
  - 30m window: 60 points
  - 1h window: 120 points
  - 3h window: 360 points
  - 6h window: 720 points
- **Memory usage:** ~30KB max (trivial)
- **Auto-trimming:** Yes, old data dropped when exceeding max

**Assessment:** ✅ Current approach is fine for in-memory charts

---

## Future Requirements (Phase 3: Database Storage)

### Problem
Once we implement historical data storage for chart time-span selector:
- Database size will grow indefinitely without retention policy
- Query performance degrades with millions of rows
- Storage costs increase linearly

### Home Assistant's Approach (Industry Standard)

**Recorder Component Strategy:**
| Age | Resolution | Example |
|---|---|---|
| 0-10 days | Full (every state change) | 30s intervals |
| 10-60 days | Hourly averages | 1-hour buckets |
| 60+ days | Daily averages | 1-day buckets |

**Default retention:** 10 days full, then decimated or purged

---

## Recommended Strategy for FranklinWH

### Retention Tiers

```
Tier 1: Live Data (< 1 hour)
  - Resolution: 30s interval (current)
  - Storage: In-memory + DB
  - Retention: Keep all

Tier 2: Recent Data (1-24 hours)
  - Resolution: 1-minute averages
  - Storage: DB only
  - Retention: 7 days

Tier 3: Historical (1-7 days)
  - Resolution: 5-minute averages
  - Storage: DB only
  - Retention: 30 days

Tier 4: Archive (7-30 days)
  - Resolution: 15-minute averages
  - Storage: DB only
  - Retention: 90 days

Tier 5: Long-term (30+ days)
  - Resolution: 1-hour averages
  - Storage: DB only
  - Retention: 365 days (optional)
```

### Database Size Estimates

**Without decimation:**
- 30s intervals = 2,880 records/day
- 30 days = 86,400 records
- 4 metrics × 86,400 = 345,600 values

**With decimation:**
- ~576 avg records/day (after decimation)
- 30 days = ~17,280 records
- **80% space savings**

---

## Implementation Plan (For Phase 3)

### Phase 3.1: Basic DB Storage
- [ ] Create SQLite table for chart data
- [ ] Store raw 30s interval data
- [ ] Implement simple retention (7 days)
- [ ] Query API endpoint for time ranges

### Phase 3.2: Decimation & Aggregation
- [ ] Create aggregation jobs (cron/scheduler)
- [ ] Implement tier-based averaging
- [ ] Auto-cleanup of old raw data
- [ ] Smart query logic (pick appropriate tier)

### Phase 3.3: Performance Optimization
- [ ] Add DB indexes on timestamp columns
- [ ] Implement data pagination
- [ ] Cache frequent queries
- [ ] Monitor DB size growth

---

## Configuration (Future)

**User-configurable settings:**
```python
RETENTION_POLICY = {
    'raw_data_days': 7,        # Keep full resolution for 7 days
    'aggregated_days': 30,     # Keep aggregates for 30 days
    'archive_days': 365,       # Keep archives for 1 year
    'enable_decimation': True  # Auto-aggregate old data
}
```

---

## Similar Systems Reference

### Home Assistant
- `recorder` component
- `purge_keep_days` setting (default: 10)
- Automatic state compression

### InfluxDB
- Retention policies per measurement
- Downsampling with continuous queries
- Shard duration optimization

### Prometheus
- TSDB with built-in retention
- Remote storage adapters
- Compaction strategies

---

## When to Implement

**Trigger:** When starting Phase 3 (Historical Mode + DB Storage)

**Estimated Effort:** 2-3 days
- Day 1: Basic DB schema + storage
- Day 2: Retention + cleanup jobs
- Day 3: Decimation + aggregation

---

## Related Files

- `TODO_POWER_FLOW_CHART.md` - Phase 3 work
- `src/models.py` - Will need ChartData model
- Future: `src/data_retention.py` - Retention manager

---

## Notes

✅ **No action needed until Phase 3**  
✅ **Current in-memory approach is optimal for live data**  
⏳ **Revisit when implementing historical data storage**

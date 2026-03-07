# TODO: Dynamic Pricing API Integrations

## Objective
Integrate real-time and forecast electricity pricing APIs to enable automated battery charge/discharge optimization based on actual tariff rates.

## Supported Providers

### 1. Amber Electric (Australia)
**Website**: https://www.amber.com.au/  
**API Docs**: https://app.amber.com.au/developers/

#### Features
- Real-time 5-minute pricing updates
- 24-hour price forecasts
- Automatic API key via customer portal
- Includes GST, network charges, and spot price

#### API Endpoints
```
GET https://api.amber.com.au/v1/sites/{siteId}/prices/current
GET https://api.amber.com.au/v1/sites/{siteId}/prices
```

#### Authentication
```http
Authorization: Bearer {API_TOKEN}
```

#### Response Example
```json
{
  "type": "CurrentInterval",
  "duration": 5,
  "startTime": "2026-02-07T06:00:00Z",
  "endTime": "2026-02-07T06:05:00Z",
  "perKwh": 0.15,
  "renewables": 45,
  "spotPerKwh": 0.08,
  "channelType": "general",
  "estimate": false
}
```

#### Implementation Notes
- Query every 5 minutes
- Cache forecast data
- Handle controlled load vs general usage pricing
- Support feed-in tariff rates

---

### 2. Local Volts (Australia)
**Website**: https://localvolts.com/  
**API**: Contact Local Volts for API access

#### Features
- Community-focused pricing
- Local renewable energy preference
- Time-of-use + spot pricing hybrid

#### API Access
- Requires Local Volts customer account
- Contact support for API credentials
- May require business/developer tier

#### Expected Data
- Current spot price
- Time-of-use period identification
- Renewable percentage
- Historical pricing data

#### Implementation Notes
- API documentation may be limited
- Might require web scraping if no official API
- Alternative: Parse customer portal data
- Check for webhooks or real-time feeds

---

### 3. ComEd Hourly Pricing (USA - Illinois)
**Website**: https://hourlypricing.comed.com/  
**API Docs**: https://hourlypricing.comed.com/api/

#### Features
- Hourly electricity prices for Northern Illinois
- Day-ahead and real-time pricing
- Historical data access
- No authentication required (public API)

#### API Endpoints
```
GET https://hourlypricing.comed.com/api?type=currenthouraverage
GET https://hourlypricing.comed.com/api?type=5minutefeed
GET https://hourlypricing.comed.com/api?type=day
```

#### Response Example (Current Hour)
```json
[
  {
    "millisUTC": "1707280800000",
    "price": "2.5"
  }
]
```

#### Implementation Notes
- Price in cents per kWh
- Convert UTC to local time
- Use 5-minute feed for real-time optimization
- Day-ahead pricing for scheduling

---

## Integration Architecture

### Module Structure
```
src/
├── pricing/
│   ├── __init__.py
│   ├── base.py              # Abstract pricing provider
│   ├── amber_electric.py    # Amber implementation
│   ├── local_volts.py       # Local Volts implementation
│   ├── comed.py             # ComEd implementation
│   └── pricing_manager.py   # Unified pricing interface
```

### Base Provider Interface
```python
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

class PricingProvider(ABC):
    @abstractmethod
    async def get_current_price(self) -> float:
        """Get current electricity price in $/kWh"""
        pass
    
    @abstractmethod
    async def get_forecast(self, hours: int = 24) -> List[dict]:
        """Get price forecast for next N hours"""
        pass
    
    @abstractmethod
    async def get_historical(self, start: datetime, end: datetime) -> List[dict]:
        """Get historical pricing data"""
        pass
```

### Pricing Manager
```python
class PricingManager:
    def __init__(self, provider: str, config: dict):
        self.provider = self._create_provider(provider, config)
        
    async def should_charge(self, threshold: float) -> bool:
        """Determine if current price is below charging threshold"""
        current = await self.provider.get_current_price()
        return current < threshold
        
    async def should_discharge(self, threshold: float) -> bool:
        """Determine if current price is above discharge threshold"""
        current = await self.provider.get_current_price()
        return current > threshold
        
    async def get_optimal_schedule(self) -> dict:
        """Generate optimal charge/discharge schedule for next 24h"""
        forecast = await self.provider.get_forecast(24)
        # Calculate optimal periods based on price
        return self._optimize_schedule(forecast)
```

## Configuration

### Config File (`config/pricing.yaml`)
```yaml
pricing:
  provider: "amber_electric"  # amber_electric, local_volts, comed
  
  amber_electric:
    api_token: "${AMBER_API_TOKEN}"
    site_id: "your-site-id"
    update_interval: 300  # seconds
    
  local_volts:
    api_token: "${LOCAL_VOLTS_TOKEN}"
    account_id: "your-account-id"
    update_interval: 300
    
  comed:
    update_interval: 300
    timezone: "America/Chicago"
    
  # Optimization thresholds
  thresholds:
    charge_below: 0.10  # $/kWh
    discharge_above: 0.30  # $/kWh
    hold_min: 0.10
    hold_max: 0.30
```

## API Endpoints (Backend)

```python
# New endpoints in web_server.py
GET  /api/pricing/current
GET  /api/pricing/forecast?hours=24
GET  /api/pricing/historical?start={ts}&end={ts}
GET  /api/pricing/provider
POST /api/pricing/provider  # Change provider
GET  /api/pricing/thresholds
PUT  /api/pricing/thresholds
POST /api/pricing/test-connection
```

## Frontend UI Components

### Pricing Dashboard Widget
- [ ] Current price display (large, prominent)
- [ ] Price trend indicator (↑↓→)
- [ ] 24-hour price forecast chart
- [ ] Next action recommendation
- [ ] Savings calculator

### Price Forecast Chart
- [ ] Line chart showing forecast prices
- [ ] Highlight charge periods (green)
- [ ] Highlight discharge periods (red)
- [ ] Current price marker
- [ ] Renewable energy percentage overlay

### Configuration Panel
- [ ] Provider selection dropdown
- [ ] API credentials input
- [ ] Threshold configuration sliders
- [ ] Connection test button
- [ ] Auto-optimization toggle

## Scheduler Integration

### Price-Aware Scheduling
```python
async def smart_schedule():
    pricing = PricingManager('amber_electric', config)
    
    # Get forecast
    forecast = await pricing.get_forecast(24)
    
    # Find cheapest periods for charging
    charge_periods = find_cheapest_periods(forecast, hours=4)
    
    # Find most expensive periods for discharge
    discharge_periods = find_most_expensive_periods(forecast, hours=3)
    
    # Schedule battery actions
    for period in charge_periods:
        schedule_charge(period['start'], period['end'])
        
    for period in discharge_periods:
        schedule_discharge(period['start'], period['end'])
```

## Implementation Phases

### Phase 1: Core Integration
- [ ] Create base provider interface
- [ ] Implement Amber Electric provider
- [ ] Add pricing data storage (database)
- [ ] Create pricing API endpoints
- [ ] Basic UI widget for current price

### Phase 2: Additional Providers
- [ ] Implement Local Volts provider
- [ ] Implement ComEd provider
- [ ] Provider auto-detection
- [ ] Multi-provider fallback

### Phase 3: Smart Scheduling
- [ ] Integrate with schedule library
- [ ] Automatic threshold-based actions
- [ ] Forecast-based optimization
- [ ] Historical analysis and learning

### Phase 4: Advanced Features
- [ ] Savings tracking and reporting
- [ ] Export opportunities (sell-back optimization)
- [ ] Alert notifications (price spikes)
- [ ] Integration with solar forecasting

## Data Storage

### Database Schema
```sql
CREATE TABLE pricing_data (
    id INTEGER PRIMARY KEY,
    provider TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    price_per_kwh REAL NOT NULL,
    is_forecast BOOLEAN DEFAULT FALSE,
    renewable_percentage REAL,
    metadata JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_pricing_timestamp ON pricing_data(timestamp);
CREATE INDEX idx_pricing_provider ON pricing_data(provider);
```

## Safety & Error Handling

- [ ] Fallback to manual mode on API failures
- [ ] Rate limiting to avoid API quota issues
- [ ] Cache pricing data to survive outages
- [ ] Validate price data (sanity checks)
- [ ] Alert on unusual price spikes
- [ ] Manual override always available

## Dependencies

```txt
# Core
httpx>=0.25.0          # Async HTTP client
aiohttp>=3.9.0         # Alternative async HTTP
pydantic>=2.5.0        # Data validation

# Optional
pandas>=2.1.0          # Historical data analysis
plotly>=5.18.0         # Interactive charts
```

## Testing

- [ ] Mock API responses for unit tests
- [ ] Integration tests with real APIs (dev accounts)
- [ ] Pricing calculation validation
- [ ] Threshold logic testing
- [ ] Schedule optimization verification

## Documentation

- [ ] API provider setup guides
- [ ] Configuration examples
- [ ] Optimization strategies guide
- [ ] FAQ for common issues

## Priority
High - Core feature for automated optimization in dynamic pricing markets

## Related TODOs
- See `TODO_SCHEDULE_LIBRARY.md` for scheduler integration
- See `power_flow_chart_enhancements.md` for price visualization

## Notes
- Start with Amber Electric (most common in AU)
- Consider OpenNEM as free alternative for Australian pricing
- May want to support custom/manual pricing input
- Privacy: API tokens should be encrypted in database

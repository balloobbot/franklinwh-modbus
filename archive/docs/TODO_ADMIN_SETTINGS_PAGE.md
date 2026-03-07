# TODO: Dedicated Admin Settings Page

## Objective
Create a dedicated administration settings page to organize advanced configuration options, moving them out of the crowded settings modal and into a proper full-page interface.

## Motivation

### Current State
- All settings are crammed into a modal dialog
- Settings modal is becoming cluttered with 6+ sections:
  - Modbus Connection
  - Dashboard Widgets
  - Appearance
  - Data Refresh
  - System Settings (Logging)
  - (Future: more settings will be added)
- Modal format limits space for explanations and advanced options
- Difficult to organize hierarchically

### Desired State
- Dedicated `/admin` or `/settings` page
- Tab-based navigation for different setting categories
- More space for documentation and help text
- Better organization for complex settings
- Room for future expansion (pricing APIs, scheduling, multi-aGate, etc.)

## Proposed Structure

### Route
```
/admin-settings
```

### Page Layout
```
┌─────────────────────────────────────────────────────┐
│ [≡] Admin Settings                    [Save] [Reset]│
├─────────────────────────────────────────────────────┤
│ ┌────────────┐                                      │
│ │ General    │  ┌────────────────────────────────┐ │
│ │ Connection │  │                                │ │
│ │ MQTT       │  │  Modbus Connection Settings    │ │
│ │ Appearance │  │                                │ │
│ │ Widgets    │  │  Host: [192.168.0.110      ]  │ │
│ │ Logging    │  │  Port: [502]  Unit ID: [2  ]  │ │
│ │ Advanced   │  │  ...                           │ │
│ └────────────┘  └────────────────────────────────┘ │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Tabs/Sections

#### 1. General Settings
- Application name/branding
- Time zone
- Date/time format preferences
- Units (metric/imperial)

#### 2. Connection Settings
- **Modbus Configuration**
  - Host, Port, Unit ID
  - Base address
  - Timeout settings
  - Connection retry logic
  - Polling intervals

- **Network Health** (from TODO_WIFI_WARNING.md)
  - Enable/disable WiFi monitoring
  - Ping interval
  - Alert thresholds
  - Warning banner settings

#### 3. MQTT Settings
- Broker configuration
- Authentication
- Site configuration
- Discovery settings
- Entity selection
- Publishing intervals
- Advanced options

#### 4. Appearance
- Theme (Light/Dark/Auto)
- Primary color picker (expanded palette)
- Custom CSS support
- Dashboard layout options
- Font size preferences

#### 5. Widget Management
- Enable/disable widgets
- Reorder widgets (drag-and-drop)
- Widget-specific settings
- Custom widget configuration

#### 6. Logging & Diagnostics
- Log level
- Log retention days
- Log export options
- Debug mode toggle
- Performance monitoring
- Crash reporting preferences

#### 7. Advanced Settings
- **Scheduling** (future from TODO_SCHEDULE_LIBRARY.md)
  - Enable built-in scheduler
  - Tariff configuration
  - Schedule templates

- **Pricing Integration** (future from TODO_PRICING_APIS.md)
  - Provider selection
  - API credentials
  - Pricing thresholds
  - Auto-optimization settings

- **Multi-aGate** (future from TODO_MULTI_AGATE.md)
  - Orchestration mode
  - Three-phase configuration
  - Load balancing settings

- **Developer Options**
  - Mock mode toggle
  - API rate limiting
  - Experimental features
  - Database maintenance

## Implementation Plan

### Phase 1: Infrastructure
- [ ] Create new route `/admin-settings`
- [ ] Create base template `templates/admin_settings.html`
- [ ] Implement tab navigation component
- [ ] Add navigation link in sidebar

### Phase 2: Migrate Existing Settings
- [ ] Move Modbus connection settings
- [ ] Move MQTT configuration
- [ ] Move appearance settings
- [ ] Move widget management
- [ ] Move logging settings
- [ ] Keep simplified "Quick Settings" modal for common items

### Phase 3: Enhanced UI
- [ ] Add inline help text and tooltips
- [ ] Implement form validation with clear error messages
- [ ] Add "Test Connection" buttons for Modbus/MQTT
- [ ] Create settings import/export functionality
- [ ] Add settings search/filter

### Phase 4: Advanced Features
- [ ] Settings version control (track changes)
- [ ] Settings profiles (save/load configurations)
- [ ] Comparison view (current vs. default)
- [ ] Audit log for settings changes
- [ ] Keyboard shortcuts

## UI Components

### Tab Navigation
```html
<div class="admin-tabs">
  <button class="tab active">General</button>
  <button class="tab">Connection</button>
  <button class="tab">MQTT</button>
  <button class="tab">Appearance</button>
  <button class="tab">Widgets</button>
  <button class="tab">Logging</button>
  <button class="tab">Advanced</button>
</div>
```

### Settings Form
```html
<form class="settings-form">
  <section class="settings-section">
    <h3>Modbus Connection</h3>
    <p class="help-text">Configure connection to your FranklinWH aGate</p>
    
    <div class="setting-item">
      <label>Host Address</label>
      <input type="text" placeholder="192.168.0.110">
      <span class="help">IP address or hostname of your aGate</span>
    </div>
    
    <div class="setting-row">
      <div class="setting-item">
        <label>Port</label>
        <input type="number" value="502">
      </div>
      <div class="setting-item">
        <label>Unit ID</label>
        <input type="number" value="2">
      </div>
    </div>
    
    <button type="button" class="test-btn">🔌 Test Connection</button>
  </section>
</form>
```

### Sticky Save Bar
```html
<div class="save-bar" x-show="settingsChanged">
  <span>You have unsaved changes</span>
  <div class="actions">
    <button @click="resetChanges()">Discard</button>
    <button @click="saveSettings()" class="primary">Save Changes</button>
  </div>
</div>
```

## Backend Changes

### New API Endpoints
```python
# Settings management
GET  /api/admin/settings/schema    # Get settings structure
GET  /api/admin/settings/export    # Export settings as JSON
POST /api/admin/settings/import    # Import settings
POST /api/admin/settings/reset     # Reset to defaults

# Settings profiles
GET  /api/admin/profiles
POST /api/admin/profiles
GET  /api/admin/profiles/{id}
DELETE /api/admin/profiles/{id}

# Audit log
GET  /api/admin/settings/history
```

### Settings Validation
```python
# Enhanced validation with detailed error messages
class SettingsValidator:
    def validate_modbus(self, config):
        """Validate Modbus settings"""
        errors = []
        if not config.host:
            errors.append("Host is required")
        if config.port < 1 or config.port > 65535:
            errors.append("Port must be between 1-65535")
        return errors
```

## User Experience Improvements

### Quick Access
- Keep lightweight "Quick Settings" modal for:
  - Theme toggle
  - Auto-refresh toggle
  - Refresh interval
  - Link to full Admin Settings page

### Help System
- Contextual help tooltips
- "Learn More" links to documentation
- Video tutorials for complex settings
- Settings wizard for first-time setup

### Visual Feedback
- Unsaved changes indicator
- Real-time validation
- Success/error notifications
- "Test" buttons show live results
- Preview changes before saving

## Migration Strategy

### Backward Compatibility
1. Keep existing `/api/settings` endpoint working
2. Maintain localStorage for backward compatibility
3. Provide migration notice in UI
4. Auto-migrate old settings to new format

### Feature Flag
```python
# Enable new admin page gradually
ENABLE_ADMIN_SETTINGS_PAGE = True

if ENABLE_ADMIN_SETTINGS_PAGE:
    # Show link to new page
else:
    # Use old modal
```

## Testing

- [ ] Test all settings save correctly
- [ ] Test tab navigation
- [ ] Test form validation
- [ ] Test connection tests (Modbus/MQTT)
- [ ] Test settings export/import
- [ ] Test mobile responsiveness
- [ ] Test keyboard navigation

## Documentation

- [ ] Update user guide with screenshots
- [ ] Document each setting's purpose
- [ ] Create video walkthrough
- [ ] Add inline help text
- [ ] Document API changes

## Priority
Medium - Would significantly improve UX, but current modal works for now. Should be done before adding more settings categories.

## Dependencies
- Alpine.js for reactivity
- Existing settings infrastructure
- No new external dependencies required

## Related TODOs
- `TODO_WIFI_WARNING.md` - Network health settings would go in Connection tab
- `TODO_SCHEDULE_LIBRARY.md` - Scheduling settings would go in Advanced tab
- `TODO_PRICING_APIS.md` - Pricing settings would go in Advanced tab
- `TODO_MULTI_AGATE.md` - Multi-aGate settings would go in Advanced tab

## Notes
- Consider using a settings framework/library for complex validation
- Look at Home Assistant's settings UI for inspiration
- Think about mobile experience (tabs vs. accordion)
- Settings should be searchable as they grow
- Consider role-based access control for sensitive settings

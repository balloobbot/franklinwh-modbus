# Archived Web App — FranklinWH Battery Manager

**Archived:** 2026-03-07  
**Reason:** Project refocused on core Modbus library for PyPi publication.  
This web app will be rebuilt/refactored as a separate project consuming the library.

---

## Design System (Preserve for Reuse)

### Color Palette (CSS Custom Properties)

```css
:root {
    --color-primary: #3b82f6;     /* Blue — main accent */
    --color-secondary: #10b981;   /* Green — success/battery */
    --color-accent: #f59e0b;      /* Amber — warnings/highlights */
    --color-surface: #ffffff;     /* Card backgrounds */
    --color-background: #f3f4f6; /* Page background */
}

.dark {
    --color-surface: #1f2937;     /* Dark card backgrounds */
    --color-background: #111827;  /* Dark page background */
}
```

### Typography
- Font: **Inter** (Google Fonts)
- Fallback: system sans-serif

### Design Tokens
- Border radius: `12px`
- Shadow intensity: `medium`
- Scrollbar: custom styled with primary color
- Animation: `pulse-soft` (2s ease-in-out)

### Key Components
- **Dashboard cards** with glassmorphism effect
- **Dark/light theme** toggle (auto-detect)
- **Settings modal** with widget configuration
- **MQTT admin** panel
- **Topology view** (system diagram)
- **Diagnostics** page

### Templates
| File | Purpose |
|------|---------|
| `base.html` | Layout skeleton, theme, nav |
| `dashboard.html` | Main dashboard with 6 widget cards |
| `topology.html` | System topology diagram |
| `diagnostics.html` | Debug/diagnostics view |
| `mqtt_admin.html` | MQTT broker management |
| `settings_modal.html` | Widget/theme settings |
| `reset_modal.html` | Reset confirmation |

---

## How to Run (If Needed)

```bash
# From the archive directory:
cd archive/webapp

# Restore files to original locations:
cp -r src/*.py ../../src/
cp -r templates/ ../../templates/
cp -r static/ ../../static/
cp config.json ../../data/config.json

# Install web dependencies:
pip install fastapi uvicorn jinja2 python-multipart aiofiles

# Run in mock mode:
cd ../..
MOCK_MODE=true PYTHONPATH=. python3 src/main.py

# Access: http://localhost:8080
```

## Architecture

- **Framework:** FastAPI + Uvicorn
- **API:** 77 REST endpoints
- **WebSocket:** Real-time dashboard updates
- **MQTT:** Home Assistant integration via Mosquitto
- **Templates:** Jinja2
- **Frontend:** Alpine.js + custom CSS

## File Inventory

| Directory | Files | Total Size |
|-----------|-------|-----------|
| `src/` | 16 Python files | 476K |
| `templates/` | 7 HTML templates | 264K |
| `static/` | CSS + JS + HTML variants | 240K |
| `config.json` | App configuration | 4K |

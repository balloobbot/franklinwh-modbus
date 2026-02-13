# TODO: Ubuntu systemd Service Setup

## Objective

Create a systemd service to auto-start the FranklinWH web server on Ubuntu desktop boot, with easy enable/disable for development work.

---

## Service File

**Location:** `/etc/systemd/system/franklinwh-dashboard.service`

```ini
[Unit]
Description=FranklinWH Energy Dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=david
Group=david
WorkingDirectory=/home/david/dev/modbus
Environment="PATH=/home/david/dev/modbus/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/home/david/dev/modbus/venv/bin/python -m gunicorn -c gunicorn.conf.py src.web_server:app

# Restart behavior
Restart=on-failure
RestartSec=10s
StartLimitBurst=5
StartLimitIntervalSec=120

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=franklinwh-dashboard

[Install]
WantedBy=multi-user.target
```

---

## Installation Steps

### 1. Create the Service File

```bash
sudo nano /etc/systemd/system/franklinwh-dashboard.service
# Paste the service configuration above
```

### 2. Reload systemd

```bash
sudo systemctl daemon-reload
```

### 3. Enable Auto-Start (Optional - Skip During Development)

```bash
# Enable auto-start on boot
sudo systemctl enable franklinwh-dashboard.service

# Start immediately
sudo systemctl start franklinwh-dashboard.service
```

---

## Developer Workflow

### During Development (Manual Control)

**Keep service DISABLED** to avoid conflicts:

```bash
# Disable auto-start
sudo systemctl disable franklinwh-dashboard.service

# Stop the service
sudo systemctl stop franklinwh-dashboard.service

# Run manually with run.sh
cd /home/david/dev/modbus
./run.sh
```

### For Production-Like Testing

**Enable service temporarily:**

```bash
# Start the service
sudo systemctl start franklinwh-dashboard.service

# Check status
sudo systemctl status franklinwh-dashboard.service

# View logs
journalctl -u franklinwh-dashboard.service -f
```

### After Development (Enable Permanently)

```bash
# Enable auto-start on boot
sudo systemctl enable franklinwh-dashboard.service

# Start now
sudo systemctl start franklinwh-dashboard.service
```

---

## Restart Behavior

**Current Configuration:**
- `Restart=on-failure` → Only restarts if process crashes (exit code ≠ 0)
- `RestartSec=10s` → Wait 10 seconds before restarting
- `StartLimitBurst=5` → Max 5 restart attempts
- `StartLimitIntervalSec=120` → Within 120 seconds

**During Development:**
- **DISABLE the service** → No automatic restarts
- Manual crashes won't interfere with debugging

**In Production:**
- **ENABLE the service** → Auto-restart on crashes
- Prevents downtime from unexpected crashes

---

## Useful Commands

```bash
# Status
sudo systemctl status franklinwh-dashboard.service

# Start
sudo systemctl start franklinwh-dashboard.service

# Stop
sudo systemctl stop franklinwh-dashboard.service

# Restart
sudo systemctl restart franklinwh-dashboard.service

# Enable auto-start
sudo systemctl enable franklinwh-dashboard.service

# Disable auto-start
sudo systemctl disable franklinwh-dashboard.service

# View logs (last 50 lines)
journalctl -u franklinwh-dashboard.service -n 50

# Follow logs (live tail)
journalctl -u franklinwh-dashboard.service -f

# Check if enabled
systemctl is-enabled franklinwh-dashboard.service

# Check if running
systemctl is-active franklinwh-dashboard.service
```

---

## Conflict Prevention

**Development Mode (Recommended):**
1. **Disable service:** `sudo systemctl disable franklinwh-dashboard.service`
2. **Stop service:** `sudo systemctl stop franklinwh-dashboard.service`
3. **Run manually:** `./run.sh`

**Why?**
- Avoids port 8080 conflicts
- No auto-restarts during debugging
- Full control over process lifecycle

**Check for Conflicts:**
```bash
# See if port 8080 is in use
sudo lsof -i :8080

# If service is running, you'll see:
# COMMAND    PID  USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
# gunicorn  1234  david    5u  IPv4  12345      0t0  TCP *:8080 (LISTEN)
```

---

## Logging

**View Logs:**
```bash
# All logs
journalctl -u franklinwh-dashboard.service

# Last 100 lines
journalctl -u franklinwh-dashboard.service -n 100

# Since boot
journalctl -u franklinwh-dashboard.service -b

# Follow live
journalctl -u franklinwh-dashboard.service -f
```

**Log Retention:**
- Logs stored in systemd journal
- Typically retained for a few weeks
- To export logs: `journalctl -u franklinwh-dashboard.service > service.log`

---

## Testing the Service

```bash
# 1. Stop manual instance
# Press Ctrl+C in terminal running ./run.sh

# 2. Start service
sudo systemctl start franklinwh-dashboard.service

# 3. Check status
sudo systemctl status franklinwh-dashboard.service

# 4. Test web interface
curl http://localhost:8080/

# 5. View logs
journalctl -u franklinwh-dashboard.service -f

# 6. Test restart on crash (kill process)
sudo pkill -9 gunicorn
# Wait 10 seconds, check if restarted
sudo systemctl status franklinwh-dashboard.service
```

---

## Alternative: User Service (No sudo required)

**For development-focused setup:**

**Location:** `~/.config/systemd/user/franklinwh-dashboard.service`

```ini
[Unit]
Description=FranklinWH Energy Dashboard (User)
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/david/dev/modbus
Environment="PATH=/home/david/dev/modbus/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/david/dev/modbus/venv/bin/python -m gunicorn -c gunicorn.conf.py src.web_server:app
Restart=on-failure
RestartSec=10s

[Install]
WantedBy=default.target
```

**Commands (no sudo):**
```bash
# Enable/disable
systemctl --user enable franklinwh-dashboard.service
systemctl --user disable franklinwh-dashboard.service

# Start/stop
systemctl --user start franklinwh-dashboard.service
systemctl --user stop franklinwh-dashboard.service

# Status
systemctl --user status franklinwh-dashboard.service

# Logs
journalctl --user -u franklinwh-dashboard.service -f
```

---

## Priority

**Priority:** 🟡 **MEDIUM**

**When to Implement:**
- After Week 1 quick wins are complete
- When app is stable enough for production use
- Before deploying to always-on server/device

**Estimated Effort:** ⏱️ 30 minutes

---

## Notes

- Service runs as your user (`david`) for proper file permissions
- Uses existing `gunicorn.conf.py` for production WSGI server
- `Restart=on-failure` prevents restart loops during development
- Disable service during active development to avoid port conflicts

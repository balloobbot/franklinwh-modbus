function franklinWHApp() {
    return {
        // State
        theme: 'auto',
        sidebarOpen: true,
        sidebarCollapsed: false,  // Desktop sidebar collapse state
        settingsOpen: false,
        currentTab: 'dashboard',
        connected: false,
        mockMode: null,  // Will be set from API (null = not checked yet)
        refreshing: false,
        saving: false,
        settingMode: false,
        settingReserve: false,
        settingReserve2: false,
        readingRaw: false,
        lastUpdate: null,
        nextRefresh: 0,
        backendConnected: null,  // null = unknown, true = connected, false = disconnected

        // Control Modal State
        controlModal: {
            show: false,
            title: '',
            currentValue: '',
            newValue: '',
            action: null,  // Function to execute
            status: 'idle',  // idle, writing, verifying, success, error
            errorMsg: '',
            warning: null,  // Warning message for special modes
            countdown: 0    // Forced countdown before confirm
        },

        // Control Status (Local/Remote mode, write permissions)
        controlStatus: {
            warning: false,
            control_mode: 'Unknown',
            can_write: false,
            message: '',
            checking: false,
            inferred: false
        },

        // Device Status Bar Info
        deviceStatus: {
            serial: '',  // Last 8 chars of serial
            controlMode: '',  // LOCAL or REMOTE
            gridStatus: '',   // Connected, Disconnected, etc.
            chargingStatus: '',  // Charging, Discharging, Standby
            lastUpdate: null
        },

        // Data
        data: {
            battery: {
                soc: 0,
                soh: 0,
                rated_energy_wh: 0,
                available_energy_wh: 0,
                temperature: 0,
                status: 0,
                statusText: '--',
                cycles: 0,
                dc_energy_injected_wh: 0,
                dc_energy_absorbed_wh: 0
            },
            inverter: {
                power: 0,
                voltage: 0,
                current: 0,
                frequency: 0,
                powerFactor: 0
            },
            capacity: {
                max_charge_w: 0,
                max_discharge_w: 0
            },
            extensions: {
                operatingMode: 0,
                modeText: '--',
                reserveSocSelfConsumption: 0,
                reserveSocTou: 0
            },
            solar_pv: {
                output_power_w: 0,
                output_energy_wh: 0
            },
            home_loads: {
                home_loads_w: 0,
                pv_output_w: 0,
                pv_proximal_w: 0
            },
            battery_lifetime: {
                dc_energy_injected_wh: 0,
                dc_energy_absorbed_wh: 0
            }
        },

        // Widget visibility toggles
        widgetVisibility: {
            battery_metrics: true,
            inverter_status: true,
            inverter_details: true,
            capacity: true,
            solar_pv: true,
            home_loads: true,
            battery_lifetime: true,
            reserve_settings: true,
            system_health: true,
            power_flow_chart: true
        },

        // Real-time chart data (since page opened)
        chartData: {
            timestamps: [],
            home_loads: [],
            solar: [],
            battery: [],
            grid: []
        },
        chartTimeScale: 30,  // Default 30 minutes
        chartUpdating: false,  // Show updating indicator
        charts: {},
        pendingReserveSoc: 20,
        pendingReserveSoc2: 20,
        pendingMaxCharge: 5.0,
        pendingMaxDischarge: 5.0,

        // Power Capacity Controls
        powerLimitMode: 'unlimited',  // 'unlimited', 'kW', 'percent'
        powerLimitChargeKw: 5.0,
        powerLimitDischargeKw: 5.0,
        powerLimitChargePct: 100,
        powerLimitDischargePct: 100,
        powerLimitSaving: false,

        // MQTT Publishing Status
        mqttPublishing: {
            enabled: true,
            lastPublish: null,
            publishCount: 0,
            errors: []
        },
        showMQTTLiveLog: false,
        mqttLogFilter: 'all',  // 'all', 'success', 'error'

        // MQTT Stats (from backend)
        mqttStats: {
            messages_published: 0,
            last_publish_seconds_ago: null
        },

        // UI State
        toasts: [],
        modal: {
            open: false,
            title: '',
            message: '',
            type: 'confirm',
            icon: 'fa-exclamation-triangle',
            onConfirm: () => { }
        },
        alerts: [],
        logs: [],
        rawRegisters: [],
        rawStartAddr: '15000',
        rawCount: 41,

        // Modbus Terminal
        terminalLoading: false,
        terminalMessage: '',
        terminalError: false,
        terminalHistory: [],
        readMode: 'absolute',
        writeAddress: null,
        writeValue: '',
        writeDataType: 'uint16',
        terminalAuthenticated: false,
        terminalAuthPassword: '',
        terminalAuthInput: '',
        showTerminalWarning: false,

        // SunSpec2 Explorer
        sunspecModel: '701',
        sunspecDetail: 'values',
        sunspecOutput: '',
        sunspecLoading: false,
        sunspecError: '',
        showSunSpecAdvanced: false,
        sunspecOpts: {
            compact: false,
            map: false,
            vals: false,
            nz: false,
            match: false,
            json: false,
            verbose: false,
            point: '',
            raw: ''
        },

        // Battery Force Control (VPP Mode)
        batteryControl: {
            powerWatts: 0,           // Current slider value (-5000 to +5000)
            currentPower: 0,         // Current setpoint from server
            vppActive: false,        // Is VPP mode active?
            applying: false          // Is a write in progress?
        },

        // SunSpec Safe Control
        sunspecWriteModel: '715',
        sunspecWritePoint: '',
        sunspecWriteValue: '',
        sunspecWriteLoading: false,
        sunspecWriteResult: null,
        sunspecWriteAcknowledge: false,
        showSunSpecWriteWarning: false,

        // Quick Controls
        quickControls: {
            heartbeat: null,
            alarmReset: 0,
            opCtl: 0
        },
        quickControlsLoading: false,
        quickControlResult: null,
        enterServiceWarning: {
            show: false,
            actionName: '',
            value: 0,
            modelId: 0,
            countdown: 15,
            acknowledged: false
        },

        // Reserve SOC Modal
        showReserveModal: false,
        newReserveSoc: 20,
        reserveModalStatus: 'idle',  // idle, saving, success, error
        reserveModalError: '',

        // Config
        config: {
            modbus: {
                host: '192.168.0.110',
                port: 502,
                unit_id: 2,
                base_address: 40000,
                timeout: 5
            },
            mqtt: {
                host: '192.168.0.109',
                port: 1883,
                username: '',
                password: '',
                enabled: false
            },
            auto_refresh: true,
            refresh_interval: 30,
            theme: {
                primary_color: '#3b82f6',
                secondary_color: '#10b981',
                accent_color: '#f59e0b'
            },
            widgets: {
                battery_metrics: {
                    enabled: true,
                    position: 0,
                    color: '#10b981',
                    expanded: true,
                    icon: 'fa-battery-full',
                    title: 'Battery Metrics'
                },
                inverter_status: {
                    enabled: true,
                    position: 1,
                    color: '#3b82f6',
                    expanded: true,
                    icon: 'fa-bolt',
                    title: 'Inverter Status'
                },
                inverter_details: {
                    enabled: false,  // Optional - disabled by default
                    position: 1.5,
                    color: '#6366f1',
                    expanded: true,
                    icon: 'fa-microchip',
                    title: 'Inverter Details'
                },
                solar_pv: {
                    enabled: true,
                    position: 2,
                    color: '#f59e0b',
                    expanded: true,
                    icon: 'fa-sun',
                    title: 'Solar PV'
                },
                home_loads: {
                    enabled: true,
                    position: 3,
                    color: '#06b6d4',
                    expanded: true,
                    icon: 'fa-home',
                    title: 'Home Loads'
                },
                capacity: {
                    enabled: true,
                    position: 4,
                    color: '#f59e0b',
                    expanded: true,
                    icon: 'fa-tachometer-alt',
                    title: 'Power Capacity'
                },
                battery_lifetime: {
                    enabled: false,  // Disabled by default (optional display)
                    position: 5,
                    color: '#8b5cf6',
                    expanded: true,
                    icon: 'fa-history',
                    title: 'Battery Lifetime'
                },
                reserve_settings: {
                    enabled: true,
                    position: 6,
                    color: '#8b5cf6',
                    expanded: true,
                    icon: 'fa-lock',
                    title: 'Reserve Settings'
                },
                system_health: {
                    enabled: true,
                    position: 7,
                    color: '#ef4444',
                    expanded: true,
                    icon: 'fa-heartbeat',
                    title: 'System Health'
                },
                power_flow_chart: {
                    enabled: true,
                    position: 8,
                    color: '#6366f1',
                    expanded: true,
                    icon: 'fa-chart-line',
                    title: 'Power Flow Chart'
                }
            }
        },

        // Navigation
        navItems: [
            { id: 'dashboard', icon: 'fa-tachometer-alt', label: 'Dashboard', href: '/' },
            { id: 'control', icon: 'fa-sliders-h', label: 'Control' }
        ],

        // Administration Menu (expandable)
        adminExpanded: false,
        adminMenu: {
            label: 'Administration',
            icon: 'fa-tools',
            sections: [
                {
                    label: 'Configuration',
                    items: [
                        { id: 'topology', icon: 'fa-network-wired', label: 'Topology', href: '/topology' },
                        { id: 'mqtt-admin', icon: 'fa-broadcast-tower', label: 'MQTT Admin', href: '/mqtt-admin' }
                    ]
                },
                {
                    label: 'Diagnostics',
                    items: [
                        { id: 'data-sources', icon: 'fa-microscope', label: 'Data Sources', href: '/diagnostics' },
                        { id: 'logs', icon: 'fa-file-alt', label: 'Logs' },
                        { id: 'sunspec', icon: 'fa-microchip', label: 'SunSpec2' },
                        { id: 'terminal', icon: 'fa-terminal', label: 'Terminal' }
                    ]
                }
            ]
        },

        // Computed property for admin menu active state
        get isAdminActive() {
            const adminIds = ['logs', 'sunspec', 'terminal'];
            const adminPaths = ['/topology', '/mqtt-admin', '/diagnostics'];
            return adminIds.includes(this.currentTab) || adminPaths.includes(window.location.pathname);
        },

        checkAdminActive() {
            // Auto-expand admin menu if currently on an admin page
            const adminIds = ['logs', 'sunspec', 'terminal'];
            const adminPaths = ['/topology', '/mqtt-admin', '/diagnostics'];
            if (adminIds.includes(this.currentTab) || adminPaths.includes(window.location.pathname)) {
                this.adminExpanded = true;
            }
        },

        refreshTimer: null,
        countdownTimer: null,

        // Computed
        get enabledWidgets() {
            return Object.entries(this.config.widgets)
                .filter(([key, w]) => w.enabled && this.widgetVisibility[key] !== false)
                .sort((a, b) => a[1].position - b[1].position)
                .map(([key, widget]) => ({ key, ...widget }));
        },

        // Initialization
        init() {
            this.loadSettings();

            // Load saved chart time scale preference
            const savedTimeScale = localStorage.getItem('chart_time_scale');
            if (savedTimeScale) {
                this.chartTimeScale = parseInt(savedTimeScale);
            }

            this.applyTheme();
            this.checkMode();  // Check if running in mock or live mode
            this.startAutoRefresh();
            this.startBackendConnectionCheck();  // Monitor backend connection
            this.checkControlStatus();  // Check Local/Remote mode
            this.updateDeviceStatus();  // Update device status bar
            this.addLog('Application initialized', 'info');

            // Check system preference for dark mode
            if (this.theme === 'auto') {
                const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                document.documentElement.classList.toggle('dark', prefersDark);
            }

            // Initialize charts after DOM is ready
            this.$nextTick(() => {
                this.initCharts();
                this.refreshData();
            });

            // Start MQTT stats polling
            this.fetchMQTTStats();
            setInterval(() => this.fetchMQTTStats(), 10000); // Every 10s
        },

        // Fetch MQTT stats from backend
        async fetchMQTTStats() {
            try {
                const response = await fetch('/api/mqtt/status');
                if (response.ok) {
                    const data = await response.json();
                    if (data.stats) {
                        this.mqttStats.messages_published = data.stats.messages_published || 0;
                        this.mqttStats.last_publish_seconds_ago = data.stats.last_publish_seconds_ago;
                    }
                }
            } catch (e) {
                // Silently fail - stats are optional
            }
        },

        // Control status monitoring (Local/Remote mode)
        async checkControlStatus() {
            this.controlStatus.checking = true;
            try {
                const response = await fetch('/api/control_status');
                if (response.ok) {
                    const data = await response.json();

                    // Check if warning was already shown this session
                    const warningShown = sessionStorage.getItem('controlWarningShown');
                    let showWarning = data.warning;

                    if (data.warning && !warningShown) {
                        // First time seeing warning this session - show banner
                        sessionStorage.setItem('controlWarningShown', 'true');
                    } else if (warningShown) {
                        // Already shown this session - don't show banner again
                        showWarning = false;
                    }

                    this.controlStatus = {
                        warning: showWarning,
                        control_mode: data.control_mode,
                        can_write: data.can_write,
                        message: data.message || 'Control status unknown',
                        inferred: data.control_mode?.includes('inferred') || false,
                        checking: false
                    };
                }
            } catch (e) {
                console.error('Failed to check control status:', e);
            }
            this.controlStatus.checking = false;
        },

        // Update device status bar info
        async updateDeviceStatus() {
            try {
                // Get device info from topology
                const response = await fetch('/api/topology');
                if (response.ok) {
                    const data = await response.json();
                    if (data.devices && data.devices.length > 0) {
                        const device = data.devices[0];  // Use first active device

                        // Extract serial (last 8 chars)
                        const serial = device.serial_number ?
                            device.serial_number.slice(-8) :
                            (device.id || 'Unknown');

                        this.deviceStatus.serial = serial;
                    }
                }

                // Get control mode from control status
                const controlResponse = await fetch('/api/control_status');
                if (controlResponse.ok) {
                    const controlData = await controlResponse.json();
                    // Extract just LOCAL/REMOTE from control_mode
                    let mode = controlData.control_mode || 'Unknown';
                    if (mode.includes('Local')) mode = 'LOCAL';
                    else if (mode.includes('Remote')) mode = 'REMOTE';
                    else mode = 'Unknown';
                    this.deviceStatus.controlMode = mode;
                }

                // Get grid and charging status from data
                if (this.data?.inverter) {
                    // Grid status - check if we have voltage
                    const hasVoltage = this.data.inverter.voltage > 0;
                    this.deviceStatus.gridStatus = hasVoltage ? 'Connected' : 'Disconnected';

                    // Charging status from power
                    const power = this.data.inverter.power || 0;
                    if (power < -50) {
                        this.deviceStatus.chargingStatus = 'Charging';
                    } else if (power > 50) {
                        this.deviceStatus.chargingStatus = 'Discharging';
                    } else {
                        this.deviceStatus.chargingStatus = 'Standby';
                    }
                }

                this.deviceStatus.lastUpdate = new Date();
            } catch (e) {
                console.error('Failed to update device status:', e);
            }
        },

        // Backend connection monitoring
        startBackendConnectionCheck() {
            // Check immediately
            this.checkBackendConnection();
            // Then check every 5 seconds
            setInterval(() => this.checkBackendConnection(), 5000);
        },

        async checkBackendConnection() {
            try {
                const response = await fetch('/api/health', {
                    method: 'GET',
                    // Short timeout to quickly detect disconnections
                    signal: AbortSignal.timeout(3000)
                });
                if (response.ok) {
                    const wasDisconnected = this.backendConnected === false;
                    this.backendConnected = true;
                    // Log reconnection
                    if (wasDisconnected) {
                        this.addLog('Reconnected to backend server', 'success');
                    }
                } else {
                    this.backendConnected = false;
                }
            } catch (error) {
                const wasConnected = this.backendConnected === true;
                this.backendConnected = false;
                // Log disconnection once
                if (wasConnected) {
                    this.addLog('Lost connection to backend server', 'error');
                }
            }
        },

        async checkMode() {
            try {
                const response = await fetch('/api/health');
                if (response.ok) {
                    const data = await response.json();
                    this.mockMode = data.mock_mode === true;
                    this.connected = data.modbus_connected === true;
                    this.backendConnected = true;  // Mark backend as connected
                    if (this.mockMode) {
                        this.addLog('Running in MOCK MODE', 'warning');
                    } else {
                        this.addLog('Running in LIVE MODE', 'info');
                    }
                }
            } catch (e) {
                console.error('Failed to check mode:', e);
                this.connected = false;
            }
        },

        // Theme handling
        applyTheme() {
            const root = document.documentElement;
            if (this.theme === 'dark') {
                root.classList.add('dark');
            } else if (this.theme === 'light') {
                root.classList.remove('dark');
            } else {
                // Auto
                const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                root.classList.toggle('dark', prefersDark);
            }
            this.setPrimaryColor(this.config.theme.primary_color);
        },

        setPrimaryColor(color) {
            this.config.theme.primary_color = color;
            document.documentElement.style.setProperty('--color-primary', color);
        },

        // Settings persistence
        loadSettings() {
            try {
                const saved = localStorage.getItem('franklinwh_settings');
                if (saved) {
                    const parsed = JSON.parse(saved);
                    this.config = { ...this.config, ...parsed.config };
                    this.theme = parsed.theme || 'auto';
                }
            } catch (e) {
                console.error('Failed to load settings:', e);
            }
        },

        async saveSettings() {
            this.saving = true;
            try {
                // Build settings payload - only include defined values and filter to backend-expected fields
                const settings = {
                    // Modbus - only include expected fields
                    modbus: {
                        host: this.config.modbus.host,
                        port: this.config.modbus.port,
                        unit_id: this.config.modbus.unit_id,
                        base_address: this.config.modbus.base_address,
                        timeout: this.config.modbus.timeout
                    },
                    // ❌ REMOVED MQTT - Settings modal has no MQTT section, 
                    // sending it was overwriting saved credentials with empty defaults!
                    // MQTT settings are managed via /mqtt-admin page only

                    // Theme must be an object, not a string
                    theme: {
                        mode: this.theme,  // The actual theme string (light/dark/auto)
                        primary_color: this.config.theme.primary_color,
                        secondary_color: this.config.theme.secondary_color,
                        accent_color: this.config.theme.accent_color
                    },
                    auto_refresh: this.config.auto_refresh,
                    refresh_interval: this.config.refresh_interval,
                    // Filter widgets to only include backend-expected fields
                    widgets: Object.fromEntries(
                        Object.entries(this.config.widgets).map(([key, widget]) => [
                            key,
                            {
                                enabled: widget.enabled,
                                position: Math.round(widget.position),  // Convert to integer
                                color: widget.color,
                                expanded: widget.expanded
                            }
                        ])
                    )
                };

                // Only include log settings if they're defined
                if (this.config.log_level) settings.log_level = this.config.log_level;
                if (this.config.log_retention_days) settings.log_retention_days = this.config.log_retention_days;

                // Save to API
                const response = await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settings)
                });

                if (!response.ok) {
                    // Get the error details from the response
                    const errorData = await response.json();
                    console.error('API Error Response:', errorData);
                    throw new Error(`API Error (${response.status}): ${JSON.stringify(errorData)}`);
                }

                // Update local storage as backup/cache
                localStorage.setItem('franklinwh_settings', JSON.stringify({
                    config: this.config,
                    theme: this.theme
                }));

                this.addToast('Settings saved to disk', 'success');
                this.settingsOpen = false;

                // Refresh data to reflect any connection changes
                setTimeout(() => this.refreshData(), 500);
            } catch (e) {
                console.error('Save error:', e);
                this.addToast('Failed to save settings: ' + e.message, 'error');
            }
            this.saving = false;
        },

        resetSettings() {
            this.modal = {
                open: true,
                title: 'Reset Settings?',
                message: 'This will restore default settings.',
                type: 'confirm',
                icon: 'fa-exclamation-triangle',
                onConfirm: () => {
                    localStorage.removeItem('franklinwh_settings');
                    location.reload();
                }
            };
        },

        // Data refresh
        startAutoRefresh() {
            this.refreshData();
            this.updateDeviceStatus();  // Initial device status update
            this.refreshTimer = setInterval(() => {
                if (this.config.auto_refresh) {
                    this.refreshData();
                    this.updateDeviceStatus();  // Update device status on each refresh
                }
            }, this.config.refresh_interval * 1000);

            this.countdownTimer = setInterval(() => {
                if (this.config.auto_refresh && this.nextRefresh > 0) {
                    this.nextRefresh--;
                } else if (this.config.auto_refresh) {
                    this.nextRefresh = this.config.refresh_interval;
                }
            }, 1000);
        },

        async refreshData() {
            this.refreshing = true;
            try {
                const response = await fetch('/api/data');
                if (!response.ok) throw new Error('API Error: ' + response.status);
                const rawData = await response.json();

                // Normalize Data
                let apiData;
                try {
                    apiData = this.normalizeData(rawData);
                } catch (e) {
                    console.error('Normalization error:', e);
                    this.addToast('Data error: ' + e.message, 'error');
                    apiData = rawData; // Fallback
                }

                // Update data from API
                if (apiData.battery) this.data.battery = apiData.battery;
                if (apiData.inverter) this.data.inverter = apiData.inverter;
                if (apiData.capacity) this.data.capacity = apiData.capacity;

                // Handle null solar_pv
                if (apiData.solar_pv) {
                    this.data.solar_pv = apiData.solar_pv;
                } else if (this.data.solar_pv && this.data.solar_pv.output_power_w === undefined) {
                    this.data.solar_pv = { output_power_w: 0, output_energy_wh: 0 };
                }

                // Handle home_loads
                if (apiData.home_loads) this.data.home_loads = apiData.home_loads;

                if (apiData.battery_lifetime) this.data.battery_lifetime = apiData.battery_lifetime;

                if (apiData.extensions) {
                    this.data.extensions = { ...this.data.extensions, ...apiData.extensions };
                    // Correct snake_case extensions
                    if (apiData.extensions.reserve_soc_self_consumption !== undefined) {
                        this.data.extensions.reserveSocSelfConsumption = apiData.extensions.reserve_soc_self_consumption;
                    }
                    if (apiData.extensions.reserve_soc_tou !== undefined) {
                        this.data.extensions.reserveSocTou = apiData.extensions.reserve_soc_tou;
                    }

                    // Update pending reserve values
                    if (apiData.extensions.reserveSoc !== null && apiData.extensions.reserveSoc !== undefined) {
                        this.pendingReserveSoc = apiData.extensions.reserveSoc;
                    }
                    if (apiData.extensions.reserveSoc2 !== null && apiData.extensions.reserveSoc2 !== undefined) {
                        this.pendingReserveSoc2 = apiData.extensions.reserveSoc2;
                    }
                }

                // Update chart data
                try {
                    this.updateChartData();
                } catch (e) {
                    console.error('Chart update error:', e);
                    // Don't fail the whole refresh for a chart error
                }

                // Publish dashboard-calculated values to MQTT (async, don't wait)
                this.publishDashboardToMQTT();

                this.connected = true;
                this.lastUpdate = new Date();
                this.nextRefresh = this.config.refresh_interval;

                // Clear any persistent error toast if successful
                // this.toasts = this.toasts.filter(t => t.type !== 'error');

            } catch (e) {
                console.error('Fetch error:', e);
                this.connected = false;
                this.addLog('Refresh failed: ' + e.message, 'error');
                // Only toast if it's not a standard network error (too annoying)
                if (e.message !== 'Failed to fetch') {
                    this.addToast('Connection Error: ' + e.message, 'error');
                }
            }
            this.refreshing = false;
        },

        normalizeData(data) {
            // Helper to deeply convert keys if needed, but for now just fix specific known issues
            const out = { ...data };

            if (out.battery) {
                out.battery.statusText = out.battery.status_text || out.battery.statusText || '--';
            }
            if (out.inverter) {
                out.inverter.powerFactor = out.inverter.power_factor !== undefined ? out.inverter.power_factor : out.inverter.powerFactor;
            }
            return out;
        },
        updateChartData() {
            // Add new data point to chart and trim to selected time scale (30-720 points)
            // Store timestamps as milliseconds for time-based calculations
            const now = Date.now();

            this.chartData.timestamps.push(now);
            this.chartData.home_loads.push(this.data.home_loads?.home_loads_w || 0);
            this.chartData.solar.push(this.data.solar_pv?.output_power_w || 0);
            this.chartData.battery.push(this.data.inverter?.power || 0);
            // Calculate grid = home - solar - battery (positive = importing, negative = exporting)
            const grid = (this.data.home_loads?.home_loads_w || 0) -
                (this.data.solar_pv?.output_power_w || 0) -
                (this.data.inverter?.power || 0);
            this.chartData.grid.push(grid);

            // Keep only the data points for the selected time scale
            const maxPoints = this.getMaxChartDataPoints();
            if (this.chartData.timestamps.length > maxPoints) {
                this.chartData.timestamps.shift();
                this.chartData.home_loads.shift();
                this.chartData.solar.shift();
                this.chartData.battery.shift();
                this.chartData.grid.shift();
            }

            // Update chart if it exists
            if (this.charts.powerFlow) {
                this.charts.powerFlow.update('none');
            }
        },

        getMaxChartDataPoints() {
            // Calculate max data points based on time scale
            // Refresh interval is 30 seconds
            return Math.floor((this.chartTimeScale * 60) / 30);
        },

        adjustChartTimeScale() {
            // Save preference
            localStorage.setItem('chart_time_scale', this.chartTimeScale);

            // Show updating indicator
            this.chartUpdating = true;
            setTimeout(() => this.chartUpdating = false, 800);

            // Trim excess data points if needed
            const maxPoints = this.getMaxChartDataPoints();
            if (this.chartData.timestamps.length > maxPoints) {
                const excess = this.chartData.timestamps.length - maxPoints;
                this.chartData.timestamps.splice(0, excess);
                this.chartData.home_loads.splice(0, excess);
                this.chartData.solar.splice(0, excess);
                this.chartData.battery.splice(0, excess);
                this.chartData.grid.splice(0, excess);
            }
        },

        getChartMaxValue() {
            // Get maximum value across all data series for Y-axis scaling
            if (this.chartData.timestamps.length === 0) return 1000;

            const allValues = [
                ...this.chartData.solar,
                ...this.chartData.home_loads,
                ...this.chartData.battery.map(v => Math.abs(v)),
                ...this.chartData.grid.map(v => Math.abs(v))
            ];
            const max = Math.max(...allValues, 1);

            // Round up to nice number
            const magnitude = Math.pow(10, Math.floor(Math.log10(max)));
            return Math.ceil(max / magnitude) * magnitude;
        },

        getChartLinePoints(dataArray, allowNegative) {
            // Generate SVG polyline points for chart data with time-based positioning
            if (this.chartData.timestamps.length < 2) return '';

            // Calculate time window boundaries
            const now = Date.now();
            const windowMs = this.chartTimeScale * 60 * 1000;  // Convert minutes to milliseconds
            const windowStart = now - windowMs;

            const maxValue = this.getChartMaxValue();
            const chartWidth = 800;  // SVG chart width in pixels

            return dataArray.map((val, i) => {
                const timestamp = this.chartData.timestamps[i];

                // Skip data points older than the current window
                const ageMs = now - timestamp;
                if (ageMs > windowMs) return null;

                // Calculate Y position (same as before)
                let y;
                if (allowNegative) {
                    // Handle negative values (battery/grid)
                    const min = Math.min(...dataArray, 0);
                    const max = Math.max(...dataArray, maxValue);
                    const range = max - min;
                    y = 200 - ((val - min) / Math.max(range, 1) * 180);
                } else {
                    // Positive only (solar/home)
                    y = 200 - (val / maxValue * 180);
                }

                // Calculate X position based on timestamp within window
                // positionInWindow: 0 = window start (left), 1 = now (right)
                const positionInWindow = (windowMs - ageMs) / windowMs;
                const x = 50 + (positionInWindow * chartWidth);  // Offset 50 for Y-axis space

                return `${x},${y}`;
            }).filter(point => point !== null).join(' ');  // Filter out old data points
        },

        getZeroLineY() {
            // Calculate Y position for zero line
            const min = Math.min(...this.chartData.battery, ...this.chartData.grid, 0);
            const max = Math.max(...this.chartData.battery, ...this.chartData.grid, this.getChartMaxValue());
            const range = max - min;
            return 200 - ((0 - min) / Math.max(range, 1) * 180);
        },

        getTimeLabel(position) {
            // Calculate time label for fixed position in window (0 = oldest, 1 = now)
            // This shows absolute time positions, not data point timestamps
            const now = Date.now();
            const windowMs = this.chartTimeScale * 60 * 1000;

            // Position 0 = window start (oldest), Position 1 = now (newest)
            const timestamp = now - (windowMs * (1 - position));

            const d = new Date(timestamp);
            return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
        },

        initCharts() {
            // Initialize Power Flow Chart
            const ctx = document.getElementById('chart-power_flow_chart');
            if (!ctx) return;

            this.charts.powerFlow = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: this.chartData.timestamps,
                    datasets: [
                        {
                            label: 'Solar',
                            data: this.chartData.solar,
                            borderColor: '#f59e0b',
                            backgroundColor: 'rgba(245, 158, 11, 0.1)',
                            tension: 0.4,
                            fill: true
                        },
                        {
                            label: 'Home',
                            data: this.chartData.home_loads,
                            borderColor: '#06b6d4',
                            backgroundColor: 'rgba(6, 182, 212, 0.1)',
                            tension: 0.4,
                            fill: true
                        },
                        {
                            label: 'Battery',
                            data: this.chartData.battery,
                            borderColor: '#10b981',
                            backgroundColor: 'rgba(16, 185, 129, 0.1)',
                            tension: 0.4,
                            fill: false
                        },
                        {
                            label: 'Grid',
                            data: this.chartData.grid,
                            borderColor: '#3b82f6',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            tension: 0.4,
                            fill: false
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    },
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        x: {
                            display: true,
                            ticks: {
                                maxTicksLimit: 6,
                                font: { size: 10 }
                            }
                        },
                        y: {
                            display: true,
                            title: {
                                display: true,
                                text: 'Power (W)'
                            }
                        }
                    }
                }
            });
        },

        // Control actions
        // Control functions with confirmation modal
        setOperatingMode(mode) {
            // Mode mapping from FranklinWH extension registers (15507)
            // 0=Standby, 1=Backup Reserve, 2=Self-Consumption, 3=Time-of-Use, 4=Normal
            const modeNames = ['Standby', 'Backup Reserve', 'Self-Consumption', 'Time-of-Use', 'Normal'];
            const currentMode = this.data.extensions?.operatingMode || 0;

            // Warning for special modes
            let warning = null;
            let countdown = 0;

            // When switching TO Emergency (1) or TOU (3) mode
            if (mode === 1) {
                warning = '⚠️ Emergency/Backup Reserve mode maintains full charge for power outages. Manual charging/discharging is NOT recommended and will reduce backup availability.';
                countdown = 5;
            } else if (mode === 3) {
                warning = '⚠️ Time-of-Use mode uses automatic scheduling to optimize for electricity rates. Manual charging/discharging will interfere with the optimization algorithm.';
                countdown = 5;
            }

            this.controlModal = {
                show: true,
                title: 'Change Operating Mode',
                currentValue: modeNames[currentMode] || 'Unknown',
                newValue: modeNames[mode],
                status: 'idle',
                errorMsg: '',
                warning: warning,
                countdown: countdown,
                action: async () => {
                    // Actually execute the mode change
                    const response = await fetch('/api/mode', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ mode })
                    });
                    if (!response.ok) throw new Error('Failed to write mode');

                    // Wait 2 seconds then verify
                    await new Promise(r => setTimeout(r, 2000));
                    await this.refreshData();

                    // Verify the change took effect
                    if (this.data.extensions?.operatingMode !== mode) {
                        throw new Error('Mode change not verified - aGate may be in LOCAL mode');
                    }
                }
            };

            // Start countdown if needed
            if (countdown > 0) {
                this.startControlModalCountdown();
            }
        },

        startControlModalCountdown() {
            const interval = setInterval(() => {
                if (this.controlModal.countdown > 0) {
                    this.controlModal.countdown--;
                } else {
                    clearInterval(interval);
                }
            }, 1000);
        },

        setReserveSoc(value) {
            const currentValue = this.data.extensions?.reserveSocSelfConsumption || 0;
            const currentMode = this.data.extensions?.operatingMode || 0;

            // Warning if in Emergency/TOU mode
            let warning = null;
            if (currentMode === 1) {
                warning = '⚠️ Currently in Emergency/Backup Reserve mode. Changing reserve settings may reduce backup availability.';
            } else if (currentMode === 3) {
                warning = '⚠️ Currently in Time-of-Use mode. Self-Consumption reserve is not active in this mode.';
            }

            this.controlModal = {
                show: true,
                title: 'Set Self-Consumption Reserve',
                currentValue: `${currentValue}%`,
                newValue: `${value}%`,
                status: 'idle',
                errorMsg: '',
                warning: warning,
                countdown: 0,
                action: async () => {
                    const response = await fetch('/api/reserve', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ value, type: 'self_consumption' })
                    });
                    if (!response.ok) throw new Error('Failed to write reserve SOC');

                    await new Promise(r => setTimeout(r, 2000));
                    await this.refreshData();

                    if (this.data.extensions?.reserveSocSelfConsumption !== value) {
                        throw new Error('Reserve SOC change not verified');
                    }
                }
            };
        },

        setReserveSoc2(value) {
            const currentValue = this.data.extensions?.reserveSocTou || 0;
            const currentMode = this.data.extensions?.operatingMode || 0;

            // Warning if not in TOU mode
            let warning = null;
            if (currentMode === 1) {
                warning = '⚠️ Currently in Emergency/Backup Reserve mode. TOU reserve is not active in this mode.';
            } else if (currentMode !== 3) {
                warning = '⚠️ TOU reserve only applies in Time-of-Use mode. Current mode: ' + ['Standby', 'Backup Reserve', 'Self-Consumption', 'Time-of-Use', 'Normal'][currentMode] || 'Unknown';
            }

            this.controlModal = {
                show: true,
                title: 'Set Time-of-Use Reserve',
                currentValue: `${currentValue}%`,
                newValue: `${value}%`,
                status: 'idle',
                errorMsg: '',
                warning: warning,
                countdown: 0,
                action: async () => {
                    const response = await fetch('/api/reserve', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ value, type: 'tou' })
                    });
                    if (!response.ok) throw new Error('Failed to write reserve SOC 2');

                    await new Promise(r => setTimeout(r, 2000));
                    await this.refreshData();

                    if (this.data.extensions?.reserveSocTou !== value) {
                        throw new Error('Reserve SOC 2 change not verified');
                    }
                }
            };
        },

        // Apply battery force charge/discharge power
        async applyBatteryPower() {
            try {
                this.batteryControl.applying = true;
                const powerW = this.batteryControl.powerWatts;

                const response = await fetch('/api/battery/power', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ power_watts: powerW })
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Failed to set battery power');
                }

                const result = await response.json();
                this.batteryControl.currentPower = powerW;
                this.batteryControl.vppActive = result.vpp_active || false;

                this.addToast(`Battery power set to ${powerW}W`, 'success');
                await this.fetchData();  // Refresh to show new state
            } catch (error) {
                console.error('Battery power error:', error);
                this.addToast(error.message, 'error');
            } finally {
                this.batteryControl.applying = false;
            }
        },

        async executeControlAction() {
            this.controlModal.status = 'writing';
            try {
                await this.controlModal.action();
                this.controlModal.status = 'success';
                this.addLog(this.controlModal.title + ' completed', 'success');
            } catch (e) {
                this.controlModal.status = 'error';
                this.controlModal.errorMsg = e.message || 'Unknown error';
                this.addLog(this.controlModal.title + ' failed: ' + e.message, 'error');
            }
        },

        // === POWER LIMIT CONTROLS ===

        applyPowerLimits() {
            const currentMode = this.data.extensions?.operatingMode || 0;

            let maxChargeKw, maxDischargeKw;
            let modeText, valueText;

            if (this.powerLimitMode === 'unlimited') {
                maxChargeKw = 0;  // 0 = unlimited
                maxDischargeKw = 0;
                modeText = 'Unlimited';
                valueText = 'No limits';
            } else if (this.powerLimitMode === 'kW') {
                maxChargeKw = this.powerLimitChargeKw;
                maxDischargeKw = this.powerLimitDischargeKw;
                modeText = 'kW Limits';
                valueText = `${maxChargeKw}kW charge / ${maxDischargeKw}kW discharge`;
            } else if (this.powerLimitMode === 'percent') {
                // Convert % to kW based on rated capacity
                const ratedPower = (this.data.capacity?.max_charge_w || 5000) / 1000;
                maxChargeKw = (this.powerLimitChargePct / 100) * ratedPower;
                maxDischargeKw = (this.powerLimitDischargePct / 100) * ratedPower;
                modeText = 'Percentage Limits';
                valueText = `${this.powerLimitChargePct}% / ${this.powerLimitDischargePct}%`;
            }

            // Warning for special modes
            let warning = null;
            let countdown = 0;

            if (currentMode === 1) {
                warning = '⚠️ Currently in Emergency/Backup Reserve mode. Manual power limits may reduce backup availability.';
                countdown = 5;
            } else if (currentMode === 3) {
                warning = '⚠️ Currently in Time-of-Use mode. Manual power limits will interfere with automatic scheduling.';
                countdown = 5;
            }

            this.controlModal = {
                show: true,
                title: 'Apply Power Limits',
                currentValue: `Mode: ${this.powerLimitMode === 'unlimited' ? 'Unlimited' : 'Limited'}`,
                newValue: valueText,
                status: 'idle',
                errorMsg: '',
                warning: warning,
                countdown: countdown,
                action: async () => {
                    await this.sendPowerLimitsToDevice(maxChargeKw, maxDischargeKw);
                }
            };

            if (countdown > 0) {
                this.startControlModalCountdown();
            }
        },

        async applyUnlimitedMode() {
            // Call sendPowerLimitsToDevice with 0/0 which triggers DELETE /api/battery/limits
            await this.sendPowerLimitsToDevice(0, 0);
        },

        async loadCurrentPowerLimits() {
            // Called on page load to initialize sliders with actual applied limits
            // Throttled: Only reload if 10+ seconds since last load (prevents spam on tab switching)
            const now = Date.now();
            const minInterval = 10000; // 10 seconds

            if (this.lastPowerLimitsLoad && (now - this.lastPowerLimitsLoad) < minInterval) {
                // Too soon - skip reload
                return;
            }
            try {
                const response = await fetch('/api/battery/safety-status');
                if (response.ok) {
                    const data = await response.json();

                    const chargeLimit = data.current_limits?.charge_kw || 0;
                    const dischargeLimit = data.current_limits?.discharge_kw || 0;

                    if (chargeLimit > 0 || dischargeLimit > 0) {
                        // Limits are applied
                        this.powerLimitMode = 'kW';
                        this.powerLimitChargeKw = chargeLimit || 5.0;
                        this.powerLimitDischargeKw = dischargeLimit || 5.0;
                    } else {
                        // Unlimited mode
                        this.powerLimitMode = 'unlimited';
                        this.powerLimitChargeKw = 5.0;
                        this.powerLimitDischargeKw = 5.0;
                    }

                    this.lastPowerLimitsLoad = now;
                }
            } catch (e) {
                // Keep defaults on error
                console.warn('Could not load power limits:', e);
            }
        },

        async sendPowerLimitsToDevice(maxChargeKw, maxDischargeKw) {
            this.powerLimitSaving = true;
            try {
                // Convert kW to W for API
                const maxChargeW = Math.round(maxChargeKw * 1000);
                const maxDischargeW = Math.round(maxDischargeKw * 1000);

                // Call real API endpoint
                if (maxChargeKw === 0 && maxDischargeKw === 0) {
                    // Unlimited mode - DELETE request
                    const response = await fetch('/api/battery/limits', {
                        method: 'DELETE'
                    });

                    if (!response.ok) {
                        const error = await response.json();
                        throw new Error(error.detail || 'Failed to remove limits');
                    }

                    const data = await response.json();

                    // NOTE: Do NOT overwrite capacity - that's HARDWARE rated max (5000W)!
                    // this.data.capacity.max_charge_w = 0;
                    // this.data.capacity.max_discharge_w = 0;

                    // Optimistic update: Set mode to unlimited so UI persists on tab switch
                    this.powerLimitMode = 'unlimited';

                    this.addToast(data.message || 'Power limits removed (unlimited)', 'success');

                } else {
                    // Limited mode - POST request
                    const response = await fetch('/api/power_limits', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            max_charge_kw: maxChargeKw,
                            max_discharge_kw: maxDischargeKw
                        })
                    });

                    if (!response.ok) {
                        const error = await response.json();
                        throw new Error(error.detail || 'Failed to apply limits');
                    }

                    const data = await response.json();

                    // NOTE: Do NOT update data.capacity.max_charge_w or max_discharge_w
                    // Those are HARDWARE RATED CAPACITY (always 5000W) - not current limits!
                    // The "Current Limits" display uses powerLimitChargeKw/powerLimitDischargeKw

                    // Show warnings if any
                    if (data.warnings && data.warnings.length > 0) {
                        data.warnings.forEach(w => this.addToast(w, 'warning'));
                    }

                    // Optimistic update: Update sliders immediately so values persist on tab switch
                    this.powerLimitChargeKw = maxChargeKw;
                    this.powerLimitDischargeKw = maxDischargeKw;

                    const msg = `Power limits applied: ${maxChargeKw.toFixed(1)}kW charge / ${maxDischargeKw.toFixed(1)}kW discharge`;
                    this.addToast(msg, 'success');
                }

                return true;
            } catch (e) {
                this.addToast('Failed to apply power limits: ' + e.message, 'error');
                throw e;
            } finally {
                this.powerLimitSaving = false;
            }
        },

        async readRawRegisters() {
            this.terminalLoading = true;
            this.terminalMessage = '';
            try {
                // Calculate actual address based on mode
                let startAddr = parseInt(this.rawStartAddr);
                if (this.readMode === 'sunspec' && this.config.modbus?.base_address) {
                    startAddr = this.config.modbus.base_address + startAddr;
                }

                const response = await fetch('/api/raw_registers', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        start_address: startAddr,
                        count: parseInt(this.rawCount) || 10
                    })
                });

                if (!response.ok) throw new Error('Failed to read registers');

                const data = await response.json();
                this.rawRegisters = data.registers || [];

                // Add to history
                this.addTerminalHistory('read', `addr=${startAddr} count=${this.rawCount}`, 'OK');
            } catch (e) {
                this.terminalMessage = e.message || 'Failed to read registers';
                this.terminalError = true;
                this.addTerminalHistory('read', `addr=${this.rawStartAddr}`, 'ERROR');
            }
            this.terminalLoading = false;
        },

        async writeRegister() {
            this.terminalLoading = true;
            this.terminalMessage = '';
            this.terminalError = false;

            try {
                // Parse value (support decimal or hex like 0xFFFF)
                let value = this.writeValue;
                if (typeof value === 'string' && value.startsWith('0x')) {
                    value = parseInt(value, 16);
                } else {
                    value = parseInt(value, 10);
                }

                if (isNaN(value)) throw new Error('Invalid value');

                const response = await fetch('/api/write_register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        address: parseInt(this.writeAddress),
                        value: value,
                        data_type: this.writeDataType
                    })
                });

                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || 'Write failed');
                }

                const data = await response.json();
                this.terminalMessage = data.message || 'Write successful';
                this.terminalError = false;
                this.addTerminalHistory('write', `addr=${this.writeAddress} val=0x${value.toString(16).padStart(4, '0')}`, 'OK');

                // Clear write form
                this.writeValue = '';
            } catch (e) {
                this.terminalMessage = e.message || 'Failed to write register';
                this.terminalError = true;
                this.addTerminalHistory('write', `addr=${this.writeAddress}`, 'ERROR');
            }
            this.terminalLoading = false;
        },

        loadForWrite(reg) {
            this.writeAddress = reg.addr;
            this.writeValue = reg.uint16.toString();
        },

        addTerminalHistory(type, message, result) {
            const now = new Date();
            const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
            this.terminalHistory.unshift({ type, time, message, result });
            // Keep only last 50 entries
            if (this.terminalHistory.length > 50) {
                this.terminalHistory = this.terminalHistory.slice(0, 50);
            }
        },

        initTerminal() {
            // Terminal is ready
        },

        generateTerminalPassword() {
            // Generate random 6-character password
            const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
            let pwd = '';
            for (let i = 0; i < 6; i++) {
                pwd += chars.charAt(Math.floor(Math.random() * chars.length));
            }
            this.terminalAuthPassword = pwd;
            this.terminalAuthInput = '';
        },

        async readSunSpecModel() {
            this.sunspecLoading = true;
            this.sunspecError = '';
            this.sunspecOutput = '';

            try {
                // Build query params with advanced options
                const params = new URLSearchParams();
                params.append('detail', this.sunspecDetail);
                if (this.sunspecOpts.compact) params.append('compact', 'true');
                if (this.sunspecOpts.map) params.append('map', 'true');
                if (this.sunspecOpts.vals) params.append('vals', 'true');
                if (this.sunspecOpts.verbose) params.append('verbose', 'true');

                const response = await fetch(`/api/sunspec/${this.sunspecModel}?${params}`);

                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || 'Failed to read SunSpec model');
                }

                const data = await response.json();
                this.sunspecOutput = data.output || 'No output';
            } catch (e) {
                this.sunspecError = e.message || 'Failed to read SunSpec model';
            }
            this.sunspecLoading = false;
        },

        async scanSunSpecModels() {
            this.sunspecLoading = true;
            this.sunspecError = '';
            this.sunspecOutput = '';

            try {
                const response = await fetch('/api/sunspec_scan');

                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || 'Failed to scan SunSpec models');
                }

                const data = await response.json();
                this.sunspecOutput = data.output || 'No output';
            } catch (e) {
                this.sunspecError = e.message || 'Failed to scan SunSpec models';
            }
            this.sunspecLoading = false;
        },

        copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                this.addToast('Copied to clipboard', 'success');
            }).catch(() => {
                this.addToast('Failed to copy', 'error');
            });
        },

        // Logs page
        logsData: [],
        logsStats: null,
        logsLimit: 100,
        logsOffset: 0,
        showLogsFilter: false,
        activeLogsFilters: [], // Array of active log levels (e.g., ['ERROR', 'WARNING'])
        logsSortColumn: 'timestamp',
        logsSortDirection: 'desc',
        logsFilter: {
            level: '',
            source: '',
            search: '',
            startDate: '',
            endDate: ''
        },

        get hasActiveFilters() {
            return this.activeLogsFilters.length > 0 || this.logsFilter.level || this.logsFilter.source ||
                this.logsFilter.search || this.logsFilter.startDate ||
                this.logsFilter.endDate;
        },

        toggleLogLevelFilter(level) {
            const index = this.activeLogsFilters.indexOf(level);
            if (index > -1) {
                // Remove filter
                this.activeLogsFilters.splice(index, 1);
            } else {
                // Add filter
                this.activeLogsFilters.push(level);
            }
            // Auto-apply filter
            this.logsOffset = 0;
            this.loadLogs();  // Already async, will auto-refresh
            this.loadLogsStats();  // Refresh stats to show accurate counts
        },

        isLogLevelActive(level) {
            return this.activeLogsFilters.includes(level);
        },

        sortLogsBy(column) {
            if (this.logsSortColumn === column) {
                // Toggle direction
                this.logsSortDirection = this.logsSortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                this.logsSortColumn = column;
                this.logsSortDirection = 'desc';
            }
            this.loadLogs();
        },

        async initLogs() {
            await this.loadLogsStats();
            await this.loadLogs();
        },

        async loadLogs() {
            try {
                const params = new URLSearchParams();
                params.append('limit', this.logsLimit);
                params.append('offset', this.logsOffset);
                // Active badge filters (multi-select)
                if (this.activeLogsFilters.length > 0) {
                    this.activeLogsFilters.forEach(level => params.append('levels', level));
                }
                // Traditional filter (single level)
                if (this.logsFilter.level) params.append('level', this.logsFilter.level);
                if (this.logsFilter.source) params.append('source', this.logsFilter.source);
                if (this.logsFilter.search) params.append('search', this.logsFilter.search);
                if (this.logsFilter.startDate) params.append('start_date', this.logsFilter.startDate);
                if (this.logsFilter.endDate) params.append('end_date', this.logsFilter.endDate);

                const response = await fetch(`/api/logs?${params}`);
                if (!response.ok) throw new Error('Failed to load logs');

                const data = await response.json();
                this.logsData = data.logs || [];
            } catch (e) {
                this.addToast('Failed to load logs', 'error');
            }
        },

        async loadLogsStats() {
            try {
                const response = await fetch('/api/logs/stats');
                if (!response.ok) throw new Error('Failed to load stats');
                this.logsStats = await response.json();
            } catch (e) {
                console.error('Failed to load log stats:', e);
            }
        },

        async applyLogsFilter() {
            this.logsOffset = 0;
            await this.loadLogs();
        },

        async clearLogsFilter() {
            this.logsFilter = {
                level: '',
                source: '',
                search: '',
                startDate: '',
                endDate: ''
            };
            this.activeLogsFilters = []; // Clear badge filters too
            this.logsOffset = 0;
            await this.loadLogs();
        },

        async loadLogsPrev() {
            if (this.logsOffset >= this.logsLimit) {
                this.logsOffset -= this.logsLimit;
                await this.loadLogs();
            }
        },

        async loadLogsNext() {
            this.logsOffset += this.logsLimit;
            await this.loadLogs();
        },

        formatLogTime(timestamp) {
            const date = new Date(timestamp);
            const hours = String(date.getHours()).padStart(2, '0');
            const minutes = String(date.getMinutes()).padStart(2, '0');
            const seconds = String(date.getSeconds()).padStart(2, '0');
            const milliseconds = String(date.getMilliseconds()).padStart(3, '0');
            return `${hours}:${minutes}:${seconds}.${milliseconds}`;
        },

        exportLogs(format) {
            const params = new URLSearchParams();
            params.append('format', format);
            if (this.logsFilter.startDate) params.append('start_date', this.logsFilter.startDate);
            if (this.logsFilter.endDate) params.append('end_date', this.logsFilter.endDate);

            window.open(`/api/logs/export?${params}`, '_blank');
        },

        getSunSpecCommand() {
            let cmd = `modbus_sunspec2_reader.py -i ${this.config.modbus?.host || '192.168.0.110'} -m ${this.sunspecModel}`;
            cmd += ` -d ${this.sunspecDetail}`;
            if (this.sunspecOpts.compact) cmd += ' --compact';
            if (this.sunspecOpts.map) cmd += ' --map';
            if (this.sunspecOpts.vals) cmd += ' --vals';
            if (this.sunspecOpts.nz) cmd += ' --nz';
            if (this.sunspecOpts.match) cmd += ' --match';
            if (this.sunspecOpts.json) cmd += ' --json';
            if (this.sunspecOpts.verbose) cmd += ' -v';
            if (this.sunspecOpts.point) cmd += ` --point ${this.sunspecOpts.point}`;
            if (this.sunspecOpts.raw) cmd += ` --raw ${this.sunspecOpts.raw}`;
            return cmd;
        },

        async readSunSpecPoint() {
            if (!this.sunspecOpts.point) return;
            this.sunspecLoading = true;
            this.sunspecError = '';
            this.sunspecOutput = '';

            try {
                const response = await fetch('/api/sunspec_point', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        point: this.sunspecOpts.point,
                        verbose: this.sunspecOpts.verbose
                    })
                });

                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || 'Failed to read point');
                }

                const data = await response.json();
                this.sunspecOutput = data.output || 'No output';
            } catch (e) {
                this.sunspecError = e.message || 'Failed to read point';
            }
            this.sunspecLoading = false;
        },

        async readSunSpecRaw() {
            if (!this.sunspecOpts.raw) return;
            this.sunspecLoading = true;
            this.sunspecError = '';
            this.sunspecOutput = '';

            try {
                const response = await fetch('/api/sunspec_raw', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        raw: this.sunspecOpts.raw,
                        nz: this.sunspecOpts.nz,
                        match: this.sunspecOpts.match,
                        verbose: this.sunspecOpts.verbose
                    })
                });

                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || 'Failed to read raw registers');
                }

                const data = await response.json();
                this.sunspecOutput = data.output || 'No output';
            } catch (e) {
                this.sunspecError = e.message || 'Failed to read raw registers';
            }
            this.sunspecLoading = false;
        },

        async writeSunSpecPoint(dryRun = false) {
            this.sunspecWriteLoading = true;
            this.sunspecWriteResult = null;
            this.sunspecWriteAcknowledge = false;

            try {
                // Parse value
                let value = this.sunspecWriteValue;
                if (value.startsWith('0x')) {
                    value = parseInt(value, 16);
                } else if (!isNaN(value) && value.includes('.')) {
                    value = parseFloat(value);
                } else if (!isNaN(value)) {
                    value = parseInt(value, 10);
                }

                const response = await fetch('/api/sunspec/write', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        model_id: parseInt(this.sunspecWriteModel),
                        point_name: this.sunspecWritePoint,
                        value: value,
                        dry_run: dryRun,
                        acknowledge_danger: !dryRun  // Only acknowledge for actual writes
                    })
                });

                const result = await response.json();

                if (!response.ok) {
                    throw new Error(result.detail || 'Write failed');
                }

                this.sunspecWriteResult = result;

                if (result.success) {
                    this.addToast(
                        dryRun ? 'Validation passed (dry run)' : `Wrote ${this.sunspecWritePoint}=${value}`,
                        'success'
                    );
                    // Clear form on success
                    if (!dryRun) {
                        this.sunspecWriteValue = '';
                    }
                } else {
                    this.addToast(result.error || 'Write failed', 'error');
                }

            } catch (e) {
                this.sunspecWriteResult = {
                    success: false,
                    message: e.message
                };
                this.addToast(e.message, 'error');
            }

            this.sunspecWriteLoading = false;
        },

        async writeQuickControl(pointName, value, modelId) {
            // Special handling for Enter Service (OpCtl = 3) or Exit Service (OpCtl = 4)
            if (pointName === 'OpCtl' && (value === 3 || value === 4)) {
                const actionName = value === 3 ? 'Enter Service' : 'Exit Service';
                this.showEnterServiceWarning(actionName, value, modelId);
                return;
            }

            await this.executeQuickControlWrite(pointName, value, modelId);
        },

        showEnterServiceWarning(actionName, value, modelId) {
            this.enterServiceWarning = {
                show: true,
                actionName: actionName,
                value: value,
                modelId: modelId,
                countdown: 15,
                acknowledged: false
            };
            this.startEnterServiceCountdown();
        },

        startEnterServiceCountdown() {
            const interval = setInterval(() => {
                if (this.enterServiceWarning.countdown > 0) {
                    this.enterServiceWarning.countdown--;
                } else {
                    clearInterval(interval);
                }
            }, 1000);
        },

        async confirmEnterServiceWrite() {
            const { value, modelId } = this.enterServiceWarning;
            this.enterServiceWarning.show = false;
            await this.executeQuickControlWrite('OpCtl', value, modelId);
        },

        async executeQuickControlWrite(pointName, value, modelId) {
            this.quickControlsLoading = true;
            this.quickControlResult = null;

            try {
                const response = await fetch('/api/sunspec/write', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        model_id: modelId,
                        point_name: pointName,
                        value: parseInt(value) || 0,
                        dry_run: false,
                        acknowledge_danger: true
                    })
                });

                const result = await response.json();

                if (!response.ok) {
                    throw new Error(result.detail || 'Write failed');
                }

                this.quickControlResult = result;

                if (result.success) {
                    this.addToast(`Wrote ${pointName}=${value}`, 'success');
                    // Reset the control value
                    if (pointName === 'AlarmReset') this.quickControls.alarmReset = 0;
                    if (pointName === 'OpCtl') this.quickControls.opCtl = 0;
                } else {
                    this.addToast(result.error || 'Write failed', 'error');
                }

            } catch (e) {
                this.quickControlResult = {
                    success: false,
                    message: e.message
                };
                this.addToast(e.message, 'error');
            }

            this.quickControlsLoading = false;
        },

        // UI helpers
        addToast(message, type = 'info') {
            const id = Date.now();
            this.toasts.push({ id, message, type, visible: true });
            setTimeout(() => this.removeToast(id), 5000);
        },

        removeToast(id) {
            const toast = this.toasts.find(t => t.id === id);
            if (toast) toast.visible = false;
            setTimeout(() => {
                this.toasts = this.toasts.filter(t => t.id !== id);
            }, 300);
        },

        closeModal() {
            this.modal.open = false;
        },

        addLog(message, level = 'info') {
            this.logs.unshift({
                id: Date.now(),
                message,
                level,
                time: new Date().toLocaleTimeString()
            });
            // Keep only last 100 logs
            if (this.logs.length > 100) this.logs.pop();
        },

        clearLogs() {
            this.logs = [];
        },

        formatTime(date) {
            if (!date) return '--';
            return date.toLocaleTimeString();
        },

        // === FORMATTING HELPERS ===

        formatPower(watts, hideZero = false) {
            if (watts === null || watts === undefined || isNaN(watts)) return '--';
            const num = Number(watts);
            if (isNaN(num)) return '--';
            if (num === 0 && hideZero) return '0 W';
            if (Math.abs(num) < 1000) {
                return `${Math.round(num)} W`;
            }
            return `${(num / 1000).toFixed(2)} kW`;
        },

        formatEnergy(wh) {
            if (wh === null || wh === undefined) return '--';
            if (Math.abs(wh) < 1000) {
                return `${Math.round(wh)} Wh`;
            } else if (Math.abs(wh) < 1000000) {
                return `${(wh / 1000).toFixed(2)} kWh`;
            }
            return `${(wh / 1000000).toFixed(2)} MWh`;
        },

        // === SOC STATUS HELPERS ===

        getSocStatusClass(soc) {
            if (soc === null || soc === undefined) return { bg: 'bg-gray-100', text: 'text-gray-600' };
            if (soc <= 20) return { bg: 'bg-red-100', text: 'text-red-700' };
            if (soc <= 40) return { bg: 'bg-amber-100', text: 'text-amber-700' };
            if (soc >= 90) return { bg: 'bg-emerald-100', text: 'text-emerald-700' };
            return { bg: 'bg-blue-100', text: 'text-blue-700' };
        },

        getSocStatusText(soc) {
            if (soc === null || soc === undefined) return 'Unknown';
            if (soc <= 10) return 'Critical';
            if (soc <= 20) return 'Low';
            if (soc <= 40) return 'Moderate';
            if (soc >= 90) return 'Full';
            return 'Good';
        },

        // === POWER FLOW HELPERS ===

        getBatteryFlowClass() {
            // Model 714.DCW sign convention:
            // Negative W = charging (absorbing power)
            // Positive W = discharging (supplying power)
            const power = this.data?.battery?.power || 0;
            if (power < -50) {
                // Charging
                return { bg: 'bg-emerald-100 dark:bg-emerald-900/30', icon: 'text-emerald-600', text: 'text-emerald-600 dark:text-emerald-400' };
            } else if (power > 50) {
                // Discharging
                return { bg: 'bg-amber-100 dark:bg-amber-900/30', icon: 'text-amber-600', text: 'text-amber-600 dark:text-amber-400' };
            }
            return { bg: 'bg-gray-100 dark:bg-gray-800', icon: 'text-gray-500', text: 'text-gray-500' };
        },

        getBatteryFlowDirection() {
            // Model 714.DCW:
            // Negative = charging (arrow down = absorbing power into battery)
            // Positive = discharging (arrow up = supplying power from battery)
            const power = this.data?.battery?.power || 0;
            if (power < -50) return 'fa-arrow-down';  // Charging
            if (power > 50) return 'fa-arrow-up';     // Discharging
            return 'fa-minus';
        },

        getEstimatedGridPower() {
            // CRITICAL FIX: Use Model 701.W directly - this IS the AC grid power
            // Do NOT calculate from Home - Solar - Battery (fails in low PF scenarios)
            //
            // Model 701.W (data.inverter.power) represents AC Grid Power:
            // - Positive (+) = Importing from grid (grid supplying power)
            // - Negative (-) = Exporting to grid (sending power to grid)
            //
            // In low power factor scenarios (e.g. 0.006 PF when house is idle),
            // calculated power from V×A×PF is inaccurate. The FranklinWH aGate
            // internally filters reactive VAR noise and provides accurate readings.
            //
            // Source: Register 15506 for home loads provides "Truth" register
            // that has already filtered out reactive Var noise.
            return this.data?.inverter?.power || 0;
        },

        getGridFlowClass() {
            const power = this.getEstimatedGridPower();
            const gridConnected = this.data?.inverter?.grid_connection_state === 1;

            if (!gridConnected) {
                return { bg: 'bg-red-100 dark:bg-red-900/30', icon: 'text-red-600', text: 'text-red-600 dark:text-red-400' };
            }
            if (Math.abs(power) < 50) {
                return { bg: 'bg-gray-100 dark:bg-gray-800', icon: 'text-gray-500', text: 'text-gray-500' };
            }
            return { bg: 'bg-blue-100 dark:bg-blue-900/30', icon: 'text-blue-600', text: 'text-blue-600 dark:text-blue-400' };
        },

        getGridFlowDirection() {
            const power = this.getEstimatedGridPower();
            const gridConnected = this.data?.inverter?.grid_connection_state === 1;

            if (!gridConnected) return 'fa-times';
            if (Math.abs(power) < 50) return 'fa-minus';

            // Down arrow ↓ = importing (power flowing from grid to house)
            // Up arrow ↑ = exporting (power flowing from house to grid)
            return power > 0 ? 'fa-arrow-down' : 'fa-arrow-up';
        },

        // === RESERVE SOC MODAL ACTIONS ===

        openReserveModal() {
            this.newReserveSoc = this.data.extensions?.reserveSoc || 20;
            this.reserveModalStatus = 'idle';
            this.reserveModalError = '';
            this.showReserveModal = true;
        },

        async saveReserveSoc() {
            this.reserveModalStatus = 'saving';
            try {
                // Determine which reserve to update based on current mode
                // Mode 3 = TOU uses reserve_soc_2, other modes use reserve_soc
                const reserveType = this.data.extensions?.mode === 3 ? 'tou' : 'self_consumption';
                const response = await fetch('/api/reserve', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        type: reserveType,
                        value: this.newReserveSoc
                    })
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Failed to update Reserve SOC');
                }

                this.reserveModalStatus = 'success';
                this.addToast('Reserve SOC updated successfully', 'success');

                // Close modal after a short delay
                setTimeout(() => {
                    this.showReserveModal = false;
                    this.reserveModalStatus = 'idle';
                }, 1000);

                // Refresh data to show updated value
                this.refreshData();
            } catch (e) {
                this.reserveModalStatus = 'error';
                this.reserveModalError = e.message;
                this.addToast('Failed to update Reserve SOC: ' + e.message, 'error');
            }
        },

        // === DASHBOARD TO MQTT PUBLISHING ===

        async publishDashboardToMQTT() {
            if (!this.mqttPublishing.enabled) return;

            try {
                const response = await fetch('/api/mqtt/publish_dashboard', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });

                if (response.ok) {
                    const data = await response.json();
                    this.mqttPublishing.lastPublish = new Date();
                    this.mqttPublishing.publishCount++;

                    // Add to log (keep last 50 entries)
                    this.mqttPublishing.errors.unshift({
                        time: new Date(),
                        type: 'success',
                        message: `Published: ${data.published.join(', ')}`,
                        values: data.values
                    });
                } else {
                    throw new Error(`HTTP ${response.status}`);
                }
            } catch (e) {
                this.mqttPublishing.errors.unshift({
                    time: new Date(),
                    type: 'error',
                    message: e.message
                });
            }

            // Keep only last 50 log entries
            if (this.mqttPublishing.errors.length > 50) {
                this.mqttPublishing.errors = this.mqttPublishing.errors.slice(0, 50);
            }
        },

        async publishToMQTT(topic, value) {
            // Generic MQTT publish for custom dashboard values
            try {
                const response = await fetch('/api/mqtt/publish', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ topic, value })
                });
                if (!response.ok) {
                    throw new Error('MQTT publish failed');
                }
                return await response.json();
            } catch (e) {
                console.error('MQTT publish error:', e);
                throw e;
            }
        }
    }
}

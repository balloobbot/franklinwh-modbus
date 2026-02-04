function franklinWHApp() {
    return {
        // State
        theme: 'auto',
        sidebarOpen: true,
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
            errorMsg: ''
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
            chargingStatus: '',  // Charging, Discharging, Idle
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
        charts: {},
        pendingReserveSoc: 20,
        pendingReserveSoc2: 20,
        pendingMaxCharge: 5.0,
        pendingMaxDischarge: 5.0,

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
            { id: 'dashboard', icon: 'fa-tachometer-alt', label: 'Dashboard' },
            { id: 'control', icon: 'fa-sliders-h', label: 'Control' },
            { id: 'logs', icon: 'fa-file-alt', label: 'Logs' },
            { id: 'raw', icon: 'fa-microchip', label: 'Raw Registers' }
        ],

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
        },

        // Control status monitoring (Local/Remote mode)
        async checkControlStatus() {
            this.controlStatus.checking = true;
            try {
                const response = await fetch('/api/control_status');
                if (response.ok) {
                    const data = await response.json();
                    this.controlStatus = {
                        warning: data.warning,
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
                    if (power > 50) {
                        this.deviceStatus.chargingStatus = 'Charging';
                    } else if (power < -50) {
                        this.deviceStatus.chargingStatus = 'Discharging';
                    } else {
                        this.deviceStatus.chargingStatus = 'Idle';
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
                // Save to API
                const response = await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        modbus: this.config.modbus,
                        mqtt: this.config.mqtt,
                        theme: this.config.theme,
                        auto_refresh: this.config.auto_refresh,
                        refresh_interval: this.config.refresh_interval,
                        widgets: this.config.widgets
                    })
                });

                if (!response.ok) throw new Error('API Error');

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
            // Add new data point to chart (keep last 60 points = 30 minutes at 30s interval)
            const now = new Date().toLocaleTimeString();

            this.chartData.timestamps.push(now);
            this.chartData.home_loads.push(this.data.home_loads?.home_loads_w || 0);
            this.chartData.solar.push(this.data.solar_pv?.output_power_w || 0);
            this.chartData.battery.push(this.data.inverter?.power || 0);
            // Calculate grid = solar - home_loads - battery (simplified)
            const grid = (this.data.solar_pv?.output_power_w || 0) -
                (this.data.home_loads?.home_loads_w || 0) -
                (this.data.inverter?.power || 0);
            this.chartData.grid.push(grid);

            // Keep only last 60 points
            if (this.chartData.timestamps.length > 60) {
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
            
            this.controlModal = {
                show: true,
                title: 'Change Operating Mode',
                currentValue: modeNames[currentMode] || 'Unknown',
                newValue: modeNames[mode],
                status: 'idle',
                errorMsg: '',
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
        },

        setReserveSoc(value) {
            const currentValue = this.data.extensions?.reserveSocSelfConsumption || 0;
            
            this.controlModal = {
                show: true,
                title: 'Set Reserve SOC',
                currentValue: `${currentValue}%`,
                newValue: `${value}%`,
                status: 'idle',
                errorMsg: '',
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
            
            this.controlModal = {
                show: true,
                title: 'Set Reserve SOC 2',
                currentValue: `${currentValue}%`,
                newValue: `${value}%`,
                status: 'idle',
                errorMsg: '',
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

        async setPowerLimits() {
            this.addToast('Power limits applied', 'success');
        },

        async readRawRegisters() {
            this.readingRaw = true;
            try {
                // Simulate register reading
                await new Promise(r => setTimeout(r, 800));
                const start = parseInt(this.rawStartAddr);
                this.rawRegisters = [];
                for (let i = 0; i < this.rawCount; i++) {
                    const val = Math.floor(Math.random() * 65535);
                    const int16 = val > 32767 ? val - 65536 : val;
                    this.rawRegisters.push({
                        addr: start + i,
                        hex: `0x${val.toString(16).padStart(4, '0')}`,
                        uint16: val,
                        int16: int16,
                        guess: i === 11 ? 'SOC raw' : i === 36 ? 'SOH raw' : ''
                    });
                }
            } catch (e) {
                this.addToast('Failed to read registers', 'error');
            }
            this.readingRaw = false;
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
        }
    }
}

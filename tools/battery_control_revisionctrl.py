class SunSpecBatteryController:
    # ... existing registers ...
    REG_TIMEOUT = 14
    REG_WSET_RVRT_TMS = 15      # NEW: WSetRvrtTms
    REG_VARSET_RVRT_TMS = 16    # NEW: VarSetRvrtTms  
    REG_VASET_RVRT_TMS = 17     # NEW: VaSetRvrtTms
    REG_WSET_RVRT_REM = 18      # NEW: WSetRvrtRem (read-only, 2 registers)
    
    def send_command(
        self, 
        command: BatteryCommand, 
        ctl_timeout: int = 60,
        wset_rvrt_tms: int = 0  # NEW parameter
    ) -> Tuple[bool, List[WriteResult]]:
        # ... extend register block to include reversion time ...
        register_block = [
            command.mode.value,     # Control mode
            max_high, max_low,      # WChaMax
            max_high, max_low,      # WDisChaMax
            w_set_high, w_set_low,  # WSet
            var_set_high, var_set_low,
            va_set_high, va_set_low,
            ctl_timeout,
            wset_rvrt_tms,          # NEW: WSetRvrtTms
            0,                      # VarSetRvrtTms (default 0)
            0                       # VaSetRvrtTms (default 0)
        ]

# 1. Try standard FranklinWH mode
python battery_control.py -i AGATE_IP --franklinwh --status

# 2. If that fails, try zero-based
python battery_control.py -i AGATE_IP --franklinwh-zero-based --status

# 3. If still failing, scan for the model
python battery_control.py -i AGATE_IP --franklinwh --scan-models

# 4. Once working, send commands
python battery_control.py -i AGATE_IP --franklinwh -p 3000W --wset-rvrt 5m

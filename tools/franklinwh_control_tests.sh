# Read status
python3 franklinwh_control.py -i 192.168.0.110 --status

# Charge at 3000W
python3 franklinwh_control.py -i 192.168.0.110 --power 3000

# Discharge at 2000W
python3 franklinwh_control.py -i 192.168.0.110 --power -2000

# Charge for 10 minutes then revert
python3 franklinwh_control.py -i 192.168.0.110 --power 3000 --revert 600

# Idle/stop
python3 franklinwh_control.py -i 192.168.0.110 --idle

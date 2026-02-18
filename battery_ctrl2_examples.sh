# Charge for 10 minutes, then auto-revert
python battery_control.py -i 192.168.1.100 -p 5000W --wset-rvrt 10m

# Discharge for 1 hour
python battery_control.py -i 192.168.1.100 -p -3000W --wset-rvrt 1h

# Set all reversion timers to 5 minutes
python battery_control.py -i 192.168.1.100 -p 4000VA --rvrt-all 5m

# Check remaining reversion time
python battery_control.py -i 192.168.1.100 --status

# No reversion (explicit)
python battery_control.py -i 192.168.1.100 -p 5000W --wset-rvrt 0

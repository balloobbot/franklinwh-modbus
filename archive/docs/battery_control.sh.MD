# Default: verify with 3 retries
python battery_control.py -i 192.168.1.100 -p 5000W

# No verification (fastest)
python battery_control.py -i 192.168.1.100 -p 5000W --no-verify

# Aggressive verification
python battery_control.py -i 192.168.1.100 -p 5000W --retry 5 --retry-interval 0.2 --verify-delay 0.05

# Quiet mode (scripting friendly)
python battery_control.py -i 192.168.1.100 -p 5000W --quiet && echo "Success" || echo "Failed"

# Full verbose with custom timing
python battery_control.py -i 192.168.1.100 -p 5000W -v --retry 10 --retry-interval 1.0

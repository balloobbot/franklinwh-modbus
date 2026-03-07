| Command | Behavior |
|---------|----------|
| `python script.py -i 192.168.0.110 --status` | Read all model statuses |
| `python script.py -i 192.168.0.110 --power 3000` | Direct charge 3000W |
| `python script.py -i 192.168.0.110 --mode self_consumption` | Auto-optimize solar use |
| `python script.py -i 192.168.0.110 --mode emergency_backup --target-soc 90` | Charge to 90% |
| `python script.py -i 192.168.0.110 --mode time_of_use` | Price arbitrage |
| `python script.py -i 192.168.0.110 --mode manual --power 1500 --duration 3600` | Timed manual control |
| `python script.py -i 192.168.0.110 -t 10.0 --status` | 10-second timeout |
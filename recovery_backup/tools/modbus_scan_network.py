#!/usr/bin/env python3
"""
SunSpec device scanner using Modbus TCP.
Scans network for SunSpec-compatible devices and displays Model 1 information.

Command-Line Options Summary

Network/Target Selection

- --ip <address> - Scan a specific IP address instead of network scan

- --network <CIDR> - Network to scan in CIDR notation (e.g., "192.168.1.0/24")
	- Default: Auto-detects local network


Modbus Configuration

- --port <number> - Modbus TCP port (default: 502)

- --unit <number> - Modbus unit/slave ID (default: 1)

- --base-address <number> - Starting Modbus register address for SunSpec scan
	- Common values: 0, 1, 40000, 50000

	- Default: Auto-detect


Performance Settings

- --threads <number> - Number of concurrent threads
	- Default: 1 (single-threaded, safe mode)

	- Recommended: 50+ for multi-threaded speed


- --timeout <seconds> - Connection timeout in seconds (default: 0.5)

Output Control

- -v or --verbose - Show detailed error messages for non-compliant devices

# Try specific IP with base address 40000
python3 modbus_scan_network.py --ip 192.168.1.100 --base-address 40000 -v

# Try base address 0
python3 modbus_scan_network.py --ip 192.168.1.100 --base-address 0 -v

# Try base address 50000
python3 modbus_scan_network.py --ip 192.168.1.100 --base-address 50000 -v

# Scan network with specific base address
python3 modbus_scan_network.py --network 192.168.1.0/24 --base-address 40000 -v

# Multi-threaded scan with base address
python3 modbus_scan_network.py --threads 50 --base-address 40000

"""

import argparse
import ipaddress
import sys
from typing import Dict, List, Optional, Tuple
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Try different import paths for pysunspec2
client = None
try:
    import sunspec2.modbus.client as client
except ImportError:
    try:
        from sunspec2.modbus import client
    except ImportError:
        try:
            import pysunspec2.modbus.client as client
        except ImportError:
            try:
                from pysunspec2.modbus import client
            except ImportError:
                print(
                    "Error: pysunspec2 library not found or cannot be imported.",
                    file=sys.stderr,
                )
                sys.exit(1)


print_lock = Lock()


def scan_sunspec_device(
    ip: str, 
    port: int = 502, 
    unit: int = 1, 
    timeout: float = 0.5, 
    verbose: bool = False,
    base_address: Optional[int] = None
) -> Tuple[Optional[Dict], Optional[str]]:
    """
    Scan a single IP for SunSpec device and retrieve Model 1 data.
    
    Args:
        ip: IP address to scan
        port: Modbus TCP port (default 502)
        unit: Modbus unit ID (default 1)
        timeout: Connection timeout in seconds
        verbose: If True, return detailed error messages
        base_address: Starting Modbus address for SunSpec scan (default: auto-detect)
        
    Returns:
        Tuple of (device_info dict or None, error_message or None)
    """
    device = None
    try:
        # Create Modbus TCP client
        try:
            if base_address is not None:
                device = client.SunSpecModbusClientDeviceTCP(
                    slave_id=unit, 
                    ipaddr=ip, 
                    ipport=port, 
                    timeout=timeout,
                    ctx_base_addr=base_address
                )
            else:
                device = client.SunSpecModbusClientDeviceTCP(
                    slave_id=unit, ipaddr=ip, ipport=port, timeout=timeout
                )
        except TypeError:
            device = client.SunSpecModbusClientDeviceTCP(
                slave_id=unit, ipaddr=ip, ipport=port, timeout=timeout
            )
            if base_address is not None and hasattr(device, 'base_addr'):
                device.base_addr = base_address
            elif base_address is not None and hasattr(device, 'ctx'):
                if hasattr(device.ctx, 'base_addr'):
                    device.ctx.base_addr = base_address
        
        # Try to connect
        try:
            device.scan()
        except Exception as e:
            error_msg = f"Scan failed: {type(e).__name__}: {str(e)}"
            if device:
                try:
                    device.close()
                except:
                    pass
            return None, error_msg if verbose else None
        
        # Check if Model 1 (Common) exists
        # device.common might be a list or a single object
        common = None
        if hasattr(device, 'common'):
            if isinstance(device.common, list):
                # If it's a list, take the first element
                if len(device.common) > 0:
                    common = device.common[0]
            else:
                # If it's a single object, use it directly
                common = device.common
        
        if common is None:
            error_msg = "Device responded but has no SunSpec Common Model (Model 1)"
            if verbose:
                error_msg += f" at base address {base_address if base_address else 'auto'}"
            try:
                device.close()
            except:
                pass
            return None, error_msg if verbose else None
            
        # Extract Model 1 fields
        try:
            device_info = {
                "ip_address": ip,
                "port": port,
                "unit_id": unit,
                "base_address": base_address if base_address else "auto",
                "manufacturer": common.Mn.value if hasattr(common, 'Mn') and common.Mn else "",
                "model": common.Md.value if hasattr(common, 'Md') and common.Md else "",
                "options": common.Opt.value if hasattr(common, 'Opt') and common.Opt else "",
                "version": common.Vr.value if hasattr(common, 'Vr') and common.Vr else "",
                "serial_number": common.SN.value if hasattr(common, 'SN') and common.SN else "",
                "device_address": common.DA.value if hasattr(common, 'DA') and common.DA else unit,
            }
        except Exception as e:
            error_msg = f"Failed to extract Model 1 fields: {type(e).__name__}: {str(e)}"
            try:
                device.close()
            except:
                pass
            return None, error_msg if verbose else None
        
        device.close()
        return device_info, None
        
    except ConnectionRefusedError:
        return None, "Connection refused (port closed)" if verbose else None
    except socket.timeout:
        return None, "Connection timeout (no response)" if verbose else None
    except OSError as e:
        if "Network is unreachable" in str(e):
            return None, "Network unreachable" if verbose else None
        elif "No route to host" in str(e):
            return None, "No route to host" if verbose else None
        return None, f"OS Error: {str(e)}" if verbose else None
    except Exception as e:
        error_msg = f"Error: {type(e).__name__}: {str(e)}"
        if device:
            try:
                device.close()
            except:
                pass
        return None, error_msg if verbose else None


def get_local_network() -> str:
    """Get the local network CIDR notation."""
    try:
        # Get local IP address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        # Assume /24 network
        network = ".".join(local_ip.split(".")[:-1]) + ".0/24"
        return network
    except Exception:
        return "192.168.1.0/24"


def scan_network_single_thread(
    network: Optional[str] = None,
    port: int = 502,
    unit: int = 1,
    timeout: float = 0.5,
    verbose: bool = False,
    base_address: Optional[int] = None,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Scan network for SunSpec devices using single thread (safe mode).
    
    Args:
        network: Network in CIDR notation (e.g., "192.168.1.0/24")
        port: Modbus TCP port
        unit: Modbus unit ID
        timeout: Connection timeout in seconds
        verbose: Show detailed error messages
        base_address: Starting Modbus address for SunSpec scan
        
    Returns:
        Tuple of (list of devices, list of failures with reasons)
    """
    if network is None:
        network = get_local_network()
    
    devices = []
    failures = []
    net = ipaddress.ip_network(network, strict=False)
    hosts = list(net.hosts())
    total = len(hosts)
    
    print(f"Scanning network {network} for SunSpec devices...")
    print(f"Port: {port}, Unit ID: {unit}, Timeout: {timeout}s")
    if base_address is not None:
        print(f"Base Address: {base_address} (0x{base_address:04X})")
    print(f"Single-threaded mode: scanning {total} hosts...\n")
    
    for idx, ip in enumerate(hosts, 1):
        ip_str = str(ip)
        print(
            f"Progress: {idx}/{total} ({idx*100//total}%) - Checking {ip_str}...",
            end="\r",
        )
        
        device_info, error = scan_sunspec_device(
            ip_str, port, unit, timeout, verbose, base_address
        )
        if device_info:
            devices.append(device_info)
            print(f"\nFound SunSpec device at {ip_str}".ljust(70))
        elif error and verbose:
            failures.append({"ip": ip_str, "reason": error})
            print(f"\n{ip_str}: {error}".ljust(70))
    
    print(" " * 70, end="\r")
    return devices, failures


def scan_network_multi_thread(
    network: Optional[str] = None,
    port: int = 502,
    unit: int = 1,
    max_workers: int = 50,
    timeout: float = 0.5,
    verbose: bool = False,
    base_address: Optional[int] = None,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Scan network for SunSpec devices using multithreading.
    
    Args:
        network: Network in CIDR notation (e.g., "192.168.1.0/24")
        port: Modbus TCP port
        unit: Modbus unit ID
        max_workers: Number of concurrent threads
        timeout: Connection timeout in seconds
        verbose: Show detailed error messages
        base_address: Starting Modbus address for SunSpec scan
        
    Returns:
        Tuple of (list of devices, list of failures with reasons)
    """
    if network is None:
        network = get_local_network()
    
    devices = []
    failures = []
    net = ipaddress.ip_network(network, strict=False)
    hosts = list(net.hosts())
    total = len(hosts)
    
    print(f"Scanning network {network} for SunSpec devices...")
    print(f"Port: {port}, Unit ID: {unit}, Timeout: {timeout}s")
    if base_address is not None:
        print(f"Base Address: {base_address} (0x{base_address:04X})")
    print(f"Multi-threaded mode: scanning {total} hosts with {max_workers} threads...\n")
    
    scanned = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all scan tasks
        future_to_ip = {
            executor.submit(
                scan_sunspec_device, str(ip), port, unit, timeout, verbose, base_address
            ): str(ip)
            for ip in hosts
        }
        
        # Process completed scans
        for future in as_completed(future_to_ip):
            scanned += 1
            ip = future_to_ip[future]
            
            with print_lock:
                print(
                    f"Progress: {scanned}/{total} ({scanned*100//total}%)",
                    end="\r",
                )
            
            try:
                device_info, error = future.result()
                if device_info:
                    devices.append(device_info)
                    with print_lock:
                        print(
                            f"\nFound SunSpec device at {ip}".ljust(60) + "\n",
                            end="",
                        )
                elif error and verbose:
                    failures.append({"ip": ip, "reason": error})
                    with print_lock:
                        print(f"\n{ip}: {error}".ljust(60) + "\n", end="")
            except Exception as e:
                if verbose:
                    with print_lock:
                        print(f"\n{ip}: Exception: {str(e)}".ljust(60) + "\n", end="")
    
    print(" " * 60, end="\r")
    return devices, failures


def print_device_info(devices: List[Dict]):
    """Print formatted device information."""
    if not devices:
        print("\nNo SunSpec devices found.")
        return
    
    print(f"\nFound {len(devices)} SunSpec device(s):\n")
    print("=" * 70)
    
    for idx, device in enumerate(devices, 1):
        print(f"\nDevice {idx}:")
        print(f"  IP Address:      {device['ip_address']}")
        print(f"  Port:            {device['port']}")
        print(f"  Unit ID:         {device['unit_id']}")
        print(f"  Base Address:    {device['base_address']}")
        print(f"  Manufacturer:    {device['manufacturer']}")
        print(f"  Model:           {device['model']}")
        print(f"  Version:         {device['version']}")
        print(f"  Serial Number:   {device['serial_number']}")
        print(f"  Options:         {device['options']}")
        print(f"  Device Address:  {device['device_address']}")
        print("-" * 70)


def print_failures(failures: List[Dict]):
    """Print formatted failure information."""
    if not failures:
        return
    
    print(f"\n\nDevices that responded but are not SunSpec compliant:\n")
    print("=" * 70)
    
    for failure in failures:
        print(f"\n{failure['ip']}")
        print(f"  Reason: {failure['reason']}")
    
    print("-" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Scan for SunSpec devices on Modbus TCP network",
        epilog="Common base addresses: 40000 (default), 0, 1, 50000"
    )
    parser.add_argument("--ip", type=str, help="Specific IP address to scan")
    parser.add_argument(
        "--network",
        type=str,
        help='Network to scan in CIDR notation (e.g., "192.168.1.0/24")',
    )
    parser.add_argument(
        "--port", type=int, default=502, help="Modbus TCP port (default: 502)"
    )
    parser.add_argument(
        "--unit", type=int, default=1, help="Modbus unit ID (default: 1)"
    )
    parser.add_argument(
        "--base-address",
        type=int,
        help="Starting Modbus address for SunSpec scan (e.g., 40000, 0, 1, 50000). Default: auto-detect"
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=1,
        help="Number of concurrent threads (default: 1 for single-threaded, use 50+ for multi-threaded)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=0.5,
        help="Connection timeout in seconds (default: 0.5)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed error messages for devices that are not SunSpec compliant",
    )
    
    args = parser.parse_args()
    
    if args.ip:
        # Scan specific IP
        print(f"Scanning {args.ip}:{args.port} (Unit {args.unit})...")
        if args.base_address is not None:
            print(f"Using base address: {args.base_address} (0x{args.base_address:04X})")
        device_info, error = scan_sunspec_device(
            args.ip, args.port, args.unit, args.timeout, verbose=True, base_address=args.base_address
        )
        if device_info:
            devices = [device_info]
            failures = []
        else:
            devices = []
            failures = [{"ip": args.ip, "reason": error or "Unknown error"}]
    else:
        # Scan network
        if args.threads == 1:
            devices, failures = scan_network_single_thread(
                args.network, args.port, args.unit, args.timeout, args.verbose, args.base_address
            )
        else:
            devices, failures = scan_network_multi_thread(
                args.network, args.port, args.unit, args.threads, args.timeout, args.verbose, args.base_address
            )
    
    print_device_info(devices)
    
    if args.verbose:
        print_failures(failures)
    
    return devices


if __name__ == "__main__":
    main()
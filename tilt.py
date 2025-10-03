#!/usr/bin/env python3

"""
Tilt Hydrometer Scanner (macOS)

This script continuously scans for BLE advertisements from Tilt hydrometers using Apple’s CoreBluetooth APIs.
It extracts temperature (in °F), specific gravity (SG), and tilt color from each discovered advertisement,
and displays the results in a live console table.

Features:
- Scans indefinitely for iBeacon-like Tilt broadcasts
- Decodes manufacturer data into color, temperature, and gravity
- Keeps track of the last-seen timestamp for each discovered Tilt
- Periodically refreshes a console table of discovered devices
- Maps known Tilt UUIDs to color names (Red, Green, Black, etc.)

To stop, press Ctrl+C.

Prerequisites:
- macOS with Python 3
- PyObjC (for Objective-C bridge)
- Access to Bluetooth (accept any prompts)
"""

import os
import time
import threading
import binascii
from datetime import datetime
import struct
from collections import deque
import threading, time

# PyObjC / Objective-C Imports
from Foundation import *
from CoreBluetooth import *
import objc

# Store discovered Tilt device info in a global dictionary.
#   Key:   peripheral.identifier() (unique ID for each BLE device)
#   Value: dict with color, temperature, gravity, raw data, last_seen
discovered_devices = {}

# after discovered_devices = {}
history = {}  # pid -> deque([{'ts', 'temp_c', 'gravity', 'rssi'}])
_history_lock = threading.Lock()

def _append_history(pid, temp_c, gravity):
    with _history_lock:
        dq = history.get(pid)
        if dq is None:
            dq = deque(maxlen=3600)  # ~2 hours at 2s cadence
            history[pid] = dq
        dq.append({
            'ts': int(time.time() * 1000),
            'temp_c': temp_c,
            'gravity': gravity
        })

def clear_terminal():
    """
    Clears the terminal screen, using 'cls' on Windows or 'clear' on other OSes.
    """
    os.system("cls" if os.name == "nt" else "clear")


def print_panel():
    """
    Clears the terminal and prints a table of discovered Tilt devices.
    Includes:
      - Peripheral ID
      - Color (mapped from the Tilt's UUID)
      - Temperature (°F)
      - Temperature (°C)
      - Gravity (SG)
      - Batt (weeks),
      - Last-seen timestamp
      - Raw manufacturer data in hex
    """
    clear_terminal()
    print("=== Tilt Hydrometer Data ===")
    print("{:36s} | {:8s} | {:9s} | {:8s} | {:12s} | {:12s} | {:19s} | {}".format(
        "Peripheral ID",
        "Color",
        "Temp (F)",
        "Temp (C)",
        "Gravity",
        "Batt (weeks)",
        "Last Seen",
        "Raw Data"
    ))
    print("-" * 120)

    # Iterate over each discovered device and print a row.
    for pid, info in discovered_devices.items():
        color     = info.get("color", "N/A")
        temp      = info.get("temperature", "N/A")
        temp_c    = info.get("temperature_c", None)
        temp_c    = f"{temp_c:.1f}" if isinstance(temp_c, (int, float)) else "N/A"        
        gravity   = info.get("gravity", "N/A")
        batt_wks  = info.get("battery_weeks", None)
        batt_wks  = str(batt_wks) if batt_wks is not None else "N/A"        
        raw_hex   = info.get("raw_hex", "N/A")
        last_seen = info.get("last_seen", "N/A")

        print("{:36s} | {:8s} | {:9s} | {:8s} | {:12s} | {:12s} | {:19s} | {}".format(
            str(pid),
            color,
            str(temp),
            temp_c,
            str(gravity),
            batt_wks,
            last_seen,
            raw_hex
        ))

    print("\n(Press Ctrl+C to stop)")


def refresh_panel_forever(interval=2.0):
    """
    Runs in a background thread, refreshing the console table every 'interval' seconds.
    """
    while True:
        print_panel()
        time.sleep(interval)


def parse_tilt_advertisement(data_bytes):
    """
    Attempts to parse a Tilt hydrometer's iBeacon-like manufacturer data.

    Returns:
      dict with {'color', 'temperature', 'gravity'} if the data matches
      a Tilt advertisement, otherwise None.

    Expected data structure (>=25 bytes):
      - bytes 0..1:  0x4C 0x00 (Apple's company ID)
      - bytes 2..3:  0x02 0x15 (iBeacon indicator)
      - bytes 4..19: Proximity UUID (16 bytes)
      - bytes 20..21: Major (temp in °F)
      - bytes 22..23: Minor (gravity * 1000)
      - byte 24:     Tx Power (not used here)
    """
    if len(data_bytes) < 25:
        return None

    # Check for iBeacon prefix (Apple ID + iBeacon indicator)
    if data_bytes[0:2] != b'\x4c\x00' or data_bytes[2:4] != b'\x02\x15':
        return None

    uuid_bytes = data_bytes[4:20]
    major      = data_bytes[20:22]
    minor      = data_bytes[22:24]
    tx_byte    = data_bytes[24]

    temperature = int.from_bytes(major, byteorder='big')    # 2 bytes -> int
    temperature_c = (temperature - 32) * 5.0 / 9.0
    gravity     = int.from_bytes(minor, byteorder='big')/1000.0

    # Convert Tilt's 16-byte UUID into an uppercase hex string
    uuid_str = binascii.hexlify(uuid_bytes).decode('utf-8').upper()

    # Known Tilt color map from the official doc
    color_map = {
        "A495BB10C5B14B44B5121370F02D74DE": "Red",
        "A495BB20C5B14B44B5121370F02D74DE": "Green",
        "A495BB30C5B14B44B5121370F02D74DE": "Black",
        "A495BB40C5B14B44B5121370F02D74DE": "Purple",
        "A495BB50C5B14B44B5121370F02D74DE": "Orange",
        "A495BB60C5B14B44B5121370F02D74DE": "Blue",
        "A495BB70C5B14B44B5121370F02D74DE": "Yellow",
        "A495BB80C5B14B44B5121370F02D74DE": "Pink"
    }
    color = color_map.get(uuid_str, "Unknown")

    # 0..152 => weeks since battery change; 0xC5 (-59) is legacy/placeholder, ignore.
    tx_raw        = tx_byte
    tx_dbm        = struct.unpack('b', bytes([tx_byte]))[0]  # signed form
    battery_weeks = tx_raw if 0 <= tx_raw <= 152 else None
    if tx_raw == 0xC5:
        battery_weeks = None

    return {
        "color":       color,
        "temperature": temperature,
        "temperature_c": temperature_c,        
        "gravity":     gravity,
        "battery_weeks": battery_weeks,
        "tx_raw": tx_raw,
        "tx_dbm": tx_dbm
    }

class CentralManagerDelegate(NSObject):
    """
    Delegate class for CBCentralManager. Handles state updates and
    discovered peripheral callbacks.
    """
    def init(self):
        self = objc.super(CentralManagerDelegate, self).init()
        if self is None:
            return None
        self.central = None
        return self

    def centralManagerDidUpdateState_(self, central):
        """
        Called when the central manager's Bluetooth state changes.
        """
        # CBManagerStatePoweredOn == 5 means Bluetooth is ON
        if central.state() == 5:
            print("Bluetooth is powered on. Scanning for Tilt advertisements...")
            self.central = central
            # Scan for all peripherals, allowing duplicates so we get repeated updates
            self.central.scanForPeripheralsWithServices_options_(
                None,
                { CBCentralManagerScanOptionAllowDuplicatesKey: True }
            )
        else:
            print(f"Bluetooth state changed: {central.state()}")

    def centralManager_didDiscoverPeripheral_advertisementData_RSSI_(
            self, central, peripheral, advertisementData, RSSI
    ):
        """
        Called whenever a peripheral is discovered or rediscovered
        with advertisement data. We filter for Tilt manufacturer data.
        """
        manufacturer_data = advertisementData.get("kCBAdvDataManufacturerData", None)
        if not manufacturer_data:
            return  # Not a manufacturer data packet

        data_bytes = bytes(manufacturer_data)
        tilt_info  = parse_tilt_advertisement(data_bytes)

   #     if tilt_info:
   #         # Raw battery/Tx debug print (safe: only for Tilts)
   #         tx_raw = data_bytes[24] if len(data_bytes) >= 25 else None
   #         tx_dbm = struct.unpack('b', bytes([tx_raw]))[0] if tx_raw is not None else None
   #         batt   = tilt_info.get("battery_weeks")
   #         print(f"[BAT] {tilt_info['color']} {peripheral.identifier()}: "
   #             f"tx_raw={f'0x{tx_raw:02X}' if tx_raw is not None else '??'} "
   #             f"unsigned={tx_raw if tx_raw is not None else '??'} "
   #             f"signed={tx_dbm if tx_dbm is not None else '??'} "
   #             f"weeks={'N/A' if batt is None else batt}")

# Convert NSNumber -> int; 127 means "not available" on iOS/macOS
        try:
            rssi_dbm = int(RSSI)  # PyObjC will coerce NSNumber
        except Exception:
            rssi_dbm = None
        if rssi_dbm == 127:
            rssi_dbm = None

        if tilt_info:
            pid = peripheral.identifier()
            discovered_devices[pid] = {
                "color":       tilt_info["color"],
                "temperature": tilt_info["temperature"],
                "temperature_c": tilt_info.get("temperature_c"),                
                "gravity":     tilt_info["gravity"],
                "rssi":          rssi_dbm,
                "battery_weeks": tilt_info.get("battery_weeks"),
                "tx_raw": tilt_info.get("tx_raw"),
                "tx_dbm": tilt_info.get("tx_dbm"),
                "raw_hex":     data_bytes.hex(),
                "last_seen":   datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            _append_history(pid,
                    tilt_info.get("temperature_c"),
                    tilt_info["gravity"])

            # Write a CSV line for each new advertisement (single-tilt case)
            try:
                now_dt = datetime.now()
                append_to_mead_csv(now_dt, tilt_info["gravity"], tilt_info.get("temperature_c", 0.0))
            except Exception:
                pass

# --- Add CSV append helper and lock ---
CSV_PATH = os.path.join(os.path.dirname(__file__), 'mead.csv')
_csv_lock = threading.Lock()

def ensure_csv_header():
    """
    Ensure mead.csv exists and contains the header line.
    Safe to call repeatedly.
    """
    with _csv_lock:
        if not os.path.exists(CSV_PATH):
            with open(CSV_PATH, 'w', encoding='utf-8') as f:
                f.write('Timepoint,SG,Temp (°C)\n')

def append_to_mead_csv(timepoint_dt, gravity, temp_c):
    """
    Append a line like:
      12/31/2024 15:42:49,1.001,22.8
    timepoint_dt: datetime
    gravity: float (SG)
    temp_c: float (°C)
    """
    try:
        ensure_csv_header()
        line = f"{timepoint_dt.strftime('%m/%d/%Y %H:%M:%S')},{gravity:.3f},{temp_c:.1f}\n"
        with _csv_lock:
            # ensure file ends with newline so appended rows don't join the last line
            need_newline = False
            try:
                with open(CSV_PATH, 'rb') as rf:
                    rf.seek(0, os.SEEK_END)
                    size = rf.tell()
                    if size > 0:
                        rf.seek(size - 1)
                        last = rf.read(1)
                        if last != b'\n':
                            need_newline = True
            except Exception:
                # non-fatal - continue to append
                pass

            with open(CSV_PATH, 'a', encoding='utf-8') as f:
                if need_newline:
                    f.write('\n')
                f.write(line)
    except Exception as e:
        # keep scan running even if disk write fails
        print(f"Failed to append to {CSV_PATH}: {e}")

# --- end CSV helper ---

def main():
    """
    Main entry point:
      - Starts a background thread to refresh the console panel every 2 seconds
      - Creates a CBCentralManager with a custom delegate
      - Enters the run loop until Ctrl+C is pressed
    """
    # Start the background refresher thread (daemon=True means it won't block exit)
    refresher = threading.Thread(target=refresh_panel_forever, args=(2.0,), daemon=True)
    refresher.start()

    # Create the delegate and central manager
    delegate = CentralManagerDelegate.alloc().init()
    manager  = CBCentralManager.alloc().initWithDelegate_queue_options_(delegate, None, None)

    # Keep the main thread alive so we can receive BLE events
    try:
        NSRunLoop.currentRunLoop().run()
    except KeyboardInterrupt:
        print("\nStopped.")

# tilt.py (add near the bottom)
from CoreBluetooth import CBCentralManager
import threading

_delegate = None
_manager = None
_ble_started = False

def start_ble_scanner():
    """
    Start CoreBluetooth scanning on a background dispatch queue so it
    coexists with Flask. Safe to call more than once.
    """
    global _delegate, _manager, _ble_started
    if _ble_started:
        return
    _ble_started = True

    _delegate = CentralManagerDelegate.alloc().init()

    # Use libdispatch queue so we don't need NSRunLoop
    try:
        import dispatch  # pip install pyobjc-framework-libdispatch
        q = dispatch.dispatch_queue_create(b"tilt.scanner", None)
    except Exception:
        q = None  # falls back to main queue; only works if you run an NSRunLoop

    _manager = CBCentralManager.alloc().initWithDelegate_queue_options_(_delegate, q, None)

if __name__ == "__main__":
    main()
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

# PyObjC / Objective-C Imports
from Foundation import *
from CoreBluetooth import *
import objc

# Store discovered Tilt device info in a global dictionary.
#   Key:   peripheral.identifier() (unique ID for each BLE device)
#   Value: dict with color, temperature, gravity, raw data, last_seen
discovered_devices = {}

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

        # If it's recognized as a Tilt hydrometer, update our global dictionary
        if tilt_info:
            pid = peripheral.identifier()
            discovered_devices[pid] = {
                "color":       tilt_info["color"],
                "temperature": tilt_info["temperature"],
                "temperature_c": tilt_info.get("temperature_c"),                
                "gravity":     tilt_info["gravity"],
                "battery_weeks": tilt_info.get("battery_weeks"),
                "tx_raw": tilt_info.get("tx_raw"),
                "tx_dbm": tilt_info.get("tx_dbm"),
                "raw_hex":     data_bytes.hex(),
                "last_seen":   datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }


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


if __name__ == "__main__":
    main()
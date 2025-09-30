#!/usr/bin/env python3
"""
Flask web dashboard for Tilt Hydrometer readings.
Displays latest readings in large, colored text.
"""
from flask import Flask, render_template_string
import threading
import time
from tilt import discovered_devices, refresh_panel_forever

COLOR_MAP = {
    "Red": "#FF4B4B",
    "Green": "#4BFF4B",
    "Black": "#222222",
    "Purple": "#A020F0",
    "Orange": "#FFA500",
    "Blue": "#4B4BFF",
    "Yellow": "#FFFF4B",
    "Pink": "#FF69B4",
    "Unknown": "#CCCCCC"
}

TEMPLATE = """
<!DOCTYPE html>
<html lang='en'>
<head>
    <meta charset='UTF-8'>
    <title>Tilt Hydrometer Dashboard</title>
    <meta http-equiv="refresh" content="2">
    <style>
        body { background: #222; color: #fff; font-family: Helvetica, Arial, sans-serif; }
        .tilt-card {
            margin: 20px auto; padding: 30px; border-radius: 20px;
            width: 80%; max-width: 600px; text-align: center;
            box-shadow: 0 4px 24px rgba(0,0,0,0.2);
        }
        .tilt-title { font-size: 3em; font-weight: bold; margin-bottom: 10px; }
        .tilt-values { font-size: 2em; }
    </style>
</head>
<body>
    <h1 style='text-align:center;'>Tilt Hydrometer Dashboard</h1>
    {% for pid, info in devices.items() %}
        <div class="tilt-card" style="background: {{ colors[info['color']] }}; color: #fff;">
            <div class="tilt-title">{{ info['color'] }}</div>
            <div class="tilt-values">Temp: {{ info['temperature_c']|float|round(2) }}°C &nbsp; Gravity: {{ info['gravity'] }}</div>
        </div>
    {% else %}
        <div style='text-align:center; margin-top:40px;'>No Tilt devices found.</div>
    {% endfor %}
</body>
</html>
"""

app = Flask(__name__)

@app.route("/")
def index():
    return render_template_string(TEMPLATE, devices=discovered_devices, colors=COLOR_MAP)

def start_ble_thread():
    t = threading.Thread(target=refresh_panel_forever, args=(2.0,), daemon=True)
    t.start()

from tilt import discovered_devices, start_ble_scanner  # <-- import the starter

app = Flask(__name__)

@app.route("/")
def index():
    return render_template_string(TEMPLATE, devices=discovered_devices, colors=COLOR_MAP)

if __name__ == "__main__":
    start_ble_scanner()
    # Important: avoid the Flask reloader so you don’t start BLE twice
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=1234)


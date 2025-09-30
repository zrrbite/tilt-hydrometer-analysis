#!/usr/bin/env python3
"""
Flask web dashboard for Tilt Hydrometer readings.
Displays latest readings in large, colored text.
"""
from flask import Flask, render_template_string
import threading
import time
from tilt import discovered_devices, refresh_panel_forever
from flask import Flask, render_template_string, jsonify
from tilt import discovered_devices, history, start_ble_scanner

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
  <style>
    body { background: #fff; color: #111; font-family: Helvetica, Arial, sans-serif; }
    .tilt-card {
      margin: 20px auto; padding: 28px; border-radius: 20px;
      width: 90%; max-width: 900px; text-align: center;
      box-shadow: 0 4px 24px rgba(0,0,0,0.12);
      background: #fff; border: 1px solid #e6e6e6;
    }
    .tilt-title { font-size: 2.2em; font-weight: 800; margin-bottom: 6px; letter-spacing: -0.02em; }
    .tilt-sub { color: #666; font-size: 0.95em; margin-bottom: 14px; display:flex; gap:10px; justify-content:center; align-items:center; flex-wrap:wrap; }
    .dot { width: 10px; height: 10px; border-radius: 50%; display:inline-block; border: 1px solid rgba(0,0,0,0.25); }
    .chip { display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 0.82em; font-weight: 700; }
    .chip-rssi  { background: #e9f3ff; color: #0a84ff; border: 1px solid #d5e8ff; }

    .stats { display: grid; gap: 12px; }
    .stat { background: #f7f7f9; border: 1px solid #eee; border-radius: 14px; padding: 14px; }
    .stat-label { text-transform: uppercase; font-weight: 700; font-size: 0.85em; letter-spacing: 0.06em; color: #666; margin-bottom: 6px; }
    .stat-value { font-weight: 900; font-size: clamp(2.2rem, 6vw, 4rem); line-height: 1; letter-spacing: -0.02em; }
    .stat-temp  { color: #ff3b30; }
    .stat-grav  { color: #0a84ff; }
  </style>
</head>
<body>
  <h1 style='text-align:center;'>Tilt Hydrometer Dashboard</h1>

  {% for pid, info in devices.items() %}
<div class="tilt-card">
  <div class="tilt-sub">
    <span class="dot" style="background: {{ colors[info['color']] }};" title="{{ info['color'] }}"></span>
    <span class="chip chip-rssi">RSSI: <span id="rssi-{{ pid }}">{{ info.get('rssi', 'N/A') }}</span></span>
    <span>Raw: <span id="raw-{{ pid }}">{{ info['raw_hex'][:12] }}…</span></span>
  </div>

  <div class="stats">
    <div class="stat">
      <div class="stat-label">Temperature</div>
      <div class="stat-value stat-temp"><span id="temp-{{ pid }}">{{ info['temperature_c']|float|round(2) }}</span> C</div>
    </div>

    <div class="stat">
      <div class="stat-label">Gravity</div>
      <div class="stat-value stat-grav"><span id="grav-{{ pid }}">{{ info['gravity']|float|round(3) }}</span></div>
    </div>
  </div>
</div>
  {% else %}
    <div style='text-align:center; margin-top:40px;'>No Tilt devices found.</div>
  {% endfor %}

  <script>
    async function refreshStats() {
      try {
        const res = await fetch('/api/devices', { cache: 'no-store' });
        const devices = await res.json();
        for (const [pid, info] of Object.entries(devices)) {
          const t = document.getElementById('temp-' + pid);
          const g = document.getElementById('grav-' + pid);
          const r = document.getElementById('rssi-' + pid);
          const rw = document.getElementById('raw-' + pid);
          if (t && info.temperature_c != null) t.textContent = Number(info.temperature_c).toFixed(2);
          if (g && info.gravity != null)      g.textContent = Number(info.gravity).toFixed(3);
          if (r && info.rssi != null)         r.textContent = info.rssi;
          if (rw && info.raw_hex)             rw.textContent = (info.raw_hex || '').slice(0, 12) + '…';
        }
      } catch (e) {
        console.error(e);
      }
    }
    setInterval(refreshStats, 2000);
    refreshStats();
  </script>
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

@app.get("/api/history")
def api_history():
    out = {}
    # snapshot for thread safety; GIL is enough here but copy is cheap
    for pid, dq in list(history.items()):
        out[str(pid)] = {
            "color": discovered_devices.get(pid, {}).get("color", "Unknown"),
            "points": list(dq)  # [{'ts','temp_c','gravity','rssi'}, ...]
        }
    return jsonify(out)

if __name__ == "__main__":
    start_ble_scanner()
    # Important: avoid the Flask reloader so you don’t start BLE twice
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=1234)


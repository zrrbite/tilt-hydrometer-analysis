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
    background: #fff;
    border: 1px solid #e6e6e6;
  }
  .tilt-title { font-size: 2.2em; font-weight: 800; margin-bottom: 6px; letter-spacing: -0.02em; }
  .tilt-sub { color: #666; font-size: 0.95em; margin-bottom: 14px; }

  /* Stats */
  .stats { display: grid; gap: 12px; }
  .stat {
    background: #f7f7f9; border: 1px solid #eee; border-radius: 14px; padding: 14px;
  }
  .stat-label { text-transform: uppercase; font-weight: 700; font-size: 0.85em; letter-spacing: 0.06em; color: #666; margin-bottom: 6px; }
  .stat-value { 
    font-weight: 900; 
    font-size: clamp(2.2rem, 6vw, 4rem); 
    line-height: 1; 
    letter-spacing: -0.02em;
    text-shadow: 0 1px 0 rgba(255,255,255,0.6);
  }
  .stat-temp  { color: #ff3b30; }   /* Temp accent */
  .stat-grav  { color: #0a84ff; }   /* Gravity accent */

  /* Small chips under the title */
  .chip { display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 0.82em; font-weight: 700; }
  .chip-color { background: #111; color: #fff; }
  .chip-rssi  { background: #e9f3ff; color: #0a84ff; border: 1px solid #d5e8ff; margin-left: 8px; }

  .chart-wrap { background: #fff; padding: 12px; border-radius: 12px; border: 1px solid #eee; margin-top: 10px; }
  canvas { width: 100%; height: 260px; }
</style>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
  <h1 style='text-align:center;'>Tilt Hydrometer Dashboard</h1>

  {% for pid, info in devices.items() %}
<div class="tilt-card">
  <div class="tilt-title">{{ info['color'] }}</div>
  <div class="tilt-sub">
    <span class="chip chip-color">{{ info['color'] }}</span>
    <span class="chip chip-rssi">RSSI: {{ info.get('rssi', 'N/A') }}</span>
    &nbsp; Raw: {{ info['raw_hex'][:12] }}…
  </div>

  <div class="stats">
    <div class="stat">
      <div class="stat-label">Temperature</div>
      <div class="stat-value stat-temp">
        {{ info['temperature_c']|float|round(2) }} °C
      </div>
    </div>

    <div class="stat">
      <div class="stat-label">Gravity</div>
      <div class="stat-value stat-grav">
        {{ info['gravity']|float|round(3) }}
      </div>
    </div>
  </div>

  <div class="chart-wrap">
    <canvas id="chart-{{ pid }}"></canvas>
  </div>
</div>
  {% else %}
    <div style='text-align:center; margin-top:40px;'>No Tilt devices found.</div>
  {% endfor %}

<script>
const charts = {};

function ensureChart(pid, colorName) {
  const ctx = document.getElementById("chart-" + pid);
  if (!ctx) return null;
  if (charts[pid]) return charts[pid];

  charts[pid] = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
    datasets: [
        { label: 'Temp (°C)', data: [], yAxisID: 'yTemp', borderWidth: 3, pointRadius: 0, borderColor: '#ff3b30' },
        { label: 'Gravity',   data: [], yAxisID: 'yGrav', borderWidth: 3, pointRadius: 0, borderColor: '#0a84ff' }
    ]
    },
    options: {
      responsive: true,
      animation: false,
      interaction: { mode: 'nearest', intersect: false },
      scales: {
        x: {
          type: 'time',
          time: { unit: 'minute' },
          ticks: { color: '#ddd' },
          grid: { color: 'rgba(255,255,255,0.1)' }
        },
        yTemp: {
          position: 'left',
          ticks: { color: '#ddd' },
          grid: { color: 'rgba(255,255,255,0.1)' }
        },
        yGrav: {
          position: 'right',
          ticks: { color: '#ddd' },
          min: 0.98, max: 1.10,  // tweak for your range
          grid: { drawOnChartArea: false }
        }
      },
      plugins: {
        legend: { labels: { color: '#fff' } },
        tooltip: { enabled: true }
      }
    }
  });
  return charts[pid];
}

async function refreshCharts() {
  try {
    const res = await fetch('/api/history', { cache: 'no-store' });
    const data = await res.json();
    for (const [pid, dev] of Object.entries(data)) {
      const chart = ensureChart(pid, dev.color);
      if (!chart) continue;
      const labels = [];
      const temps  = [];
      const gravs  = [];
      for (const p of dev.points) {
        labels.push(new Date(p.ts));
        temps.push(p.temp_c);
        gravs.push(p.gravity);
      }
      chart.data.labels = labels;
      chart.data.datasets[0].data = temps;
      chart.data.datasets[1].data = gravs;
      chart.update('none');
    }
  } catch (e) {
    console.error(e);
  }
}

setInterval(refreshCharts, 2000);
refreshCharts();
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


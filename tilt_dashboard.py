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
    body { background: #222; color: #fff; font-family: Helvetica, Arial, sans-serif; }
    .tilt-card {
      margin: 20px auto; padding: 30px; border-radius: 20px;
      width: 90%; max-width: 900px; text-align: center;
      box-shadow: 0 4px 24px rgba(0,0,0,0.2);
    }
    .tilt-title { font-size: 2.2em; font-weight: bold; margin-bottom: 10px; }
    .tilt-values { font-size: 1.4em; margin-bottom: 12px; }
    .chart-wrap { background: rgba(0,0,0,0.2); padding: 12px; border-radius: 12px; }
    canvas { width: 100%; height: 260px; }
  </style>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
  <h1 style='text-align:center;'>Tilt Hydrometer Dashboard</h1>

  {% for pid, info in devices.items() %}
    <div class="tilt-card" style="background: {{ colors[info['color']] }}; color: #fff;">
      <div class="tilt-title">{{ info['color'] }}</div>
      <div class="tilt-values">
        Temp: {{ info['temperature_c']|float|round(2) }} °C
        &nbsp; | &nbsp; Gravity: {{ info['gravity']|float|round(3) }}
        &nbsp; | &nbsp; RSSI: {{ info.get('rssi', 'N/A') }}
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
        { label: 'Temp (°C)', data: [], yAxisID: 'yTemp', borderWidth: 2, pointRadius: 0 },
        { label: 'Gravity',   data: [], yAxisID: 'yGrav', borderWidth: 2, pointRadius: 0 }
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


# TILT Hydrometer Data Capture and Analysis

This repository contains:

1. A script to connect to and capture real-time data from the **TILT Hydrometer** on macOS.
2. Another script to analyze the collected data, visualize it, and fit an **exponential decay model** for specific gravity (SG) during fermentation.

This repo is also a companion to [my blog](https://codebeats.net/).

## Features

- **Data Capture**: Connects to the TILT Hydrometer via Bluetooth Low Energy (BLE) on macOS, allowing you to log temperature and SG readings without pairing.
- **Data Analysis**: Processes the logged data to:
  - Plot fermentation trends.
  - Fit an exponential decay model:
    \[
    SG(t) = FG + (OG - FG) \cdot e^{-k \cdot t}
    \]
- ** Flask server that presents Tilt cards
<img width="1020" height="498" alt="image" src="https://github.com/user-attachments/assets/c8fe75e9-2e2e-4f6d-8508-1e8e43185335" />

## Requirements

- macOS with Python 3.x
- Libraries: `pandas`, `numpy`, `matplotlib`, `seaborn`, `scipy`, `pyobjc`

## Usage

1. Run the flask server **tilt_dashboard.py** to connect and log SG and temperature readings from the TILT Hydrometer.
2. Use the analysis script **Hydrometer Regression.ipynb** to plot and analyze the logged data.

## License

MIT License. See `LICENSE` for details.

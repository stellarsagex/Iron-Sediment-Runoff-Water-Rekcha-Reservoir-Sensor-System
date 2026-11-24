# Rekcha Reservoir Sediment & Iron Flux Early-Warning System

An IoT and geochemical soft-sensor system built to protect the storage capacity and water quality of the Rekcha community reservoir (2,100 m² surface area, 4 m depth) in rural Nepal.

## The Situation in Rekcha
The Rekcha reservoir is the primary lifeline for local agriculture and aquaculture. However, like many hill-catchment reservoirs in Nepal, it faces severe seasonal runoff during the monsoon alongside high background iron concentrations.

When heavy rains hit, turbid runoff (measured up to 591 NTU in baseline field tests) carries heavy suspended silt and dissolved iron into the basin. As this iron oxidizes and settles alongside incoming soil sediment, it silently eats away at the reservoir's 8,400 m³ storage depth. Because the treatment infrastructure—consisting of a forebay and bioswales—is entirely passive and lacks motorized gates or full-time lab staff, villagers have no visibility into how fast the basin is filling up until dry-season irrigation shortages hit or fish ponds suffer from iron toxicity.

## How This System Secures Rekcha's Water
Instead of relying on expensive laboratory analyzers or grid-powered mechanical gates, this system pairs rugged, low-cost inlet sensors with real-time thermodynamic modeling to act as an autonomous maintenance trigger:

1. **Inlet Edge Telemetry (ESP32 + MicroPython):**
   A solar-powered ESP32 node deployed at the reservoir inlet continuously measures four durable physical parameters: **Turbidity (NTU)**, **Electrical Conductivity (EC)**, **pH**, and **Temperature (°C)**.
2. **Geochemical Soft-Sensor (`phreeqpython` + `phreeqc.dat`):**
   Sensor packets stream via MQTT to a Python backend running USGS PHREEQC. Using live EC to scale seasonal ionic strength and carbonate alkalinity—and live pH and temperature to govern oxidation kinetics—the engine solves aqueous iron speciation in real time. It separates incoming iron into dissolved fraction versus solid **Ferrihydrite ($\text{Fe(OH)}_3$)** precipitate.
3. **Cumulative Mass-Balance & Storage Tracking:**
   The backend integrates the mass of precipitated iron hydroxide sludge alongside suspended sediment load (derived from calibrated turbidity-TSS curves) over exact elapsed flow intervals. It continuously tracks cumulative deposition against a **20% reservoir storage-loss threshold** (1,680 m³, or ~2,184 tonnes of wet iron-silt mass).
4. **Zero-App Community Alerting (Physical Pole Beacon):**
   When cumulative sediment and iron accumulation crosses the 20% threshold, the server sends a reverse MQTT command to trigger a relay on the ESP32, illuminating a high-visibility **Red LED Pole Light** at the reservoir. Villagers and the local water user committee get an unmistakable physical signal to schedule manual desilting before reservoir depth and dry-season water security are compromised.

## System Architecture
* **Edge Hardware:** ESP32 (MicroPython), DS18B20 Temperature Probe, Analog pH, EC ($K=1.0$), and Turbidity Sensors, 5V Relay + 12V IP65 Red Pole Beacon.
* **Geochemical Engine:** Python 3.12, `phreeqpython` (`phreeqc.dat` thermodynamic database).
* **Telemetry & SCADA:** Two-way MQTT (`umqtt.simple` on edge, `paho-mqtt` on server) + Node-RED operational dashboard.

## Repository Files
* `main.py` – MicroPython firmware running on the ESP32 edge node (reads calibrated sensors, publishes JSON telemetry, and listens for relay commands).
* `rekcha_live_server.py` – Python backend integrating live sensor streams with PHREEQC iron speciation, cumulative mass-balance tracking, and threshold relay control.
* `node_red_flow.json` – Node-RED dashboard configuration for remote monitoring of reservoir depth loss and inlet water quality.

## Running the System
1. **Flash the Edge Node:** Upload `main.py` to your ESP32 using Thonny or `mpremote` after updating `WIFI_SSID` and `WIFI_PASS`.
2. **Install Server Dependencies:**
   ```bash
   pip install phreeqpython paho-mqtt
   ```
3. **Start the Geochemical Backend:**
   ```bash
   python rekcha_live_server.py
   ```
4. **Launch SCADA View:** Start `node-red` in your terminal, open `http://127.0.0`, import `node_red_flow.json`, click **Deploy**, and open `http://127.0.0dashboard/rekcha`.

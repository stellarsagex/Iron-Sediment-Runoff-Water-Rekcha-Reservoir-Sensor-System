import time
import json
import paho.mqtt.client as mqtt
from phreeqpython import PhreeqPython

# 1. Initialize PHREEQC
pp = PhreeqPython(database='phreeqc.dat')

# 2. MQTT Topics
BROKER = "test.mosquitto.org"
PORT = 1883
TOPIC_ESP32_IN   = "saksham/rekcha/inlet/sensors"     # From ESP32
TOPIC_ESP32_OUT  = "saksham/rekcha/inlet/pole_light"  # To ESP32 Relay
TOPIC_SCADA_OUT  = "saksham/rekcha/reservoir/telemetry" # To Node-RED Dashboard

# 3. Rekcha Reservoir Geometry (2,100 m2 x 4 m = 8,400 m3)
THRESHOLD_MASS_TONNES = (2100.0 * 4.0 * 0.20 * 1300.0) / 1000.0  # 2,184.0 tonnes
INLET_FLOW_L_SEC = 15.0  # Replace with ultrasonic/weir flow rate if available

cumulative_load_tonnes = 0.0
last_packet_time = time.time()

def calculate_iron_and_sediment(turbidity_ntu, ec_uScm, pH, temp_C):
    ec_factor = max(0.2, ec_uScm / 250.0)
    incoming_fe_mgL = round(max(0.20, (turbidity_ntu / 591.0) * 3.5), 3)
    
    water = pp.add_solution({
        'temp': temp_C, 'pH': pH, 'pe': 4.0, 'units': 'mg/L',
        'Fe': incoming_fe_mgL,
        'Ca': 40.0 * ec_factor,
        'Alkalinity': f'{120.0 * ec_factor} as CaCO3',
        'Cl': f'{20.0 * ec_factor} charge'
    })
    
    water.equalize(['Fe(OH)3(a)'], [0.0])
    fe_dissolved_mgL = water.total('Fe', units='mg')
    fe_precipitated_mgL = max(0.0, incoming_fe_mgL - fe_dissolved_mgL)
    
    # Solid Fe(OH)3 sludge + suspended sediment (mg/L)
    total_solids_mgL = round((fe_precipitated_mgL * 1.91) + (turbidity_ntu * 1.2), 2)
    water.forget()
    return round(fe_precipitated_mgL, 3), total_solids_mgL

def on_connect(client, userdata, flags, reason_code, properties):
    print("Connected to MQTT Broker! Listening for Rekcha ESP32 sensor packets...")
    client.subscribe(TOPIC_ESP32_IN)

def on_message(client, userdata, msg):
    global cumulative_load_tonnes, last_packet_time
    
    try:
        data = json.loads(msg.payload.decode())
        now = time.time()
        elapsed_seconds = max(1.0, now - last_packet_time)
        last_packet_time = now
        
        turb = float(data["turbidity_NTU"])
        ec   = float(data["EC_uScm"])
        ph   = float(data["pH"])
        temp = float(data["temp_C"])
        
        fe_precip_mgL, total_solids_mgL = calculate_iron_and_sediment(turb, ec, ph, temp)
        
        # Real-time mass integration over exact elapsed seconds
        liters_entered = INLET_FLOW_L_SEC * elapsed_seconds
        added_tonnes = (total_solids_mgL * liters_entered) / 1_000_000_000.0
        cumulative_load_tonnes = round(cumulative_load_tonnes + added_tonnes, 6)
        
        storage_loss_pct = round((cumulative_load_tonnes / THRESHOLD_MASS_TONNES) * 20.0, 4)
        red_light_on = cumulative_load_tonnes >= THRESHOLD_MASS_TONNES
        
        # 1. Send Relay Command back to ESP32 Red Pole Light
        client.publish(TOPIC_ESP32_OUT, "ON" if red_light_on else "OFF")
        
        # 2. Send Full Telemetry to Node-RED SCADA Dashboard
        scada_payload = {
            "inlet_turbidity_NTU": turb,
            "inlet_EC_uScm": ec,
            "inlet_pH": ph,
            "inlet_temp_C": temp,
            "Fe_precipitated_mgL": fe_precip_mgL,
            "cumulative_load_tonnes": cumulative_load_tonnes,
            "storage_loss_pct": storage_loss_pct,
            "red_pole_light": red_light_on,
            "status_message": "RED LIGHT ON (DESILT RESERVOIR)" if red_light_on else "LIGHT OFF (DEPTH OK)"
        }
        client.publish(TOPIC_SCADA_OUT, json.dumps(scada_payload))
        print(f"ESP32 Packet -> Turb: {turb} NTU | pH: {ph} | Fe Precip: {fe_precip_mgL} mg/L | Cum Load: {cumulative_load_tonnes} t")
        
    except Exception as e:
        print("Error processing ESP32 packet:", e)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, 60)
client.loop_forever()

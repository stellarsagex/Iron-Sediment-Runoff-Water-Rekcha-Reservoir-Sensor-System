import time
import json
import network
import machine
import onewire, ds18x20
from umqtt.simple import MQTTClient

# --- 1. WI-FI & MQTT CONFIGURATION ---
WIFI_SSID = "YOUR_WIFI_NAME"
WIFI_PASS = "YOUR_WIFI_PASSWORD"

BROKER = "test.mosquitto.org"
CLIENT_ID = "rekcha_esp32_inlet_01"
TOPIC_SENSORS = b"saksham/rekcha/inlet/sensors"      # ESP32 -> Python PHREEQC
TOPIC_RELAY   = b"saksham/rekcha/inlet/pole_light"   # Python PHREEQC -> ESP32

# --- 2. HARDWARE PIN SETUP ---
relay_pin = machine.Pin(26, machine.Pin.OUT)
relay_pin.value(0)  # Start with Red Pole Light OFF

# Temperature Sensor (DS18B20 on GPIO 4)
ds_sensor = ds18x20.DS18X20(onewire.OneWire(machine.Pin(4)))
roms = ds_sensor.scan()

# Analog Sensors on ADC1 (0 - 3.3V range)
adc_ph   = machine.ADC(machine.Pin(34))
adc_ec   = machine.ADC(machine.Pin(35))
adc_turb = machine.ADC(machine.Pin(32))

for adc in (adc_ph, adc_ec, adc_turb):
    adc.atten(machine.ADC.ATTN_11DB)  # Full 0 - 3.3V range
    adc.width(machine.ADC.WIDTH_12BIT) # 0 - 4095 raw reading

# --- 3. CONNECT TO WI-FI ---
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(WIFI_SSID, WIFI_PASS)
while not wlan.isconnected():
    time.sleep(0.5)
print("Connected to Wi-Fi:", wlan.ifconfig())

# --- 4. HANDLE RED POLE LIGHT COMMANDS FROM PYTHON ---
def on_mqtt_message(topic, msg):
    if topic == TOPIC_RELAY:
        command = msg.decode().strip()
        if command == "ON":
            relay_pin.value(1)
            print(">>> RED POLE LIGHT TURNED ON (20% THRESHOLD EXCEEDED)")
        else:
            relay_pin.value(0)
            print(">>> Red Pole Light OFF (Reservoir Depth OK)")

client = MQTTClient(CLIENT_ID, BROKER, port=1883)
client.set_callback(on_mqtt_message)
client.connect()
client.subscribe(TOPIC_RELAY)
print("Connected to MQTT Broker & Subscribed to Relay Commands")

# --- 5. SENSOR CALIBRATION HELPERS (Adjust after 2-point buffer calibration) ---
def read_voltage(adc):
    # Average 10 samples to smooth electrical noise
    total = sum(adc.read() for _ in range(10)) / 10.0
    return (total / 4095.0) * 3.3

def read_sensors():
    # Temperature (C)
    temp_c = 22.0
    if roms:
        ds_sensor.convert_temp()
        time.sleep_ms(750)
        temp_c = round(ds_sensor.read_temp(roms[0]), 2)
    
    # pH Calibration (Standard linear conversion: ~1.65V = pH 7.0)
    v_ph = read_voltage(adc_ph)
    ph_val = round(7.0 + ((1.65 - v_ph) / 0.18), 2)
    
    # EC Calibration (uS/cm with temperature compensation)
    v_ec = read_voltage(adc_ec)
    raw_ec = (v_ec / 3.3) * 1000.0  # Scale factor for K=1.0 probe
    ec_val = round(raw_ec / (1.0 + 0.02 * (temp_c - 25.0)), 1)
    
    # Turbidity Calibration (NTU: clean water ~2.5V = 0 NTU, drops as mud increases)
    v_turb = read_voltage(adc_turb)
    turb_val = round(max(0.0, (2.5 - v_turb) * 400.0), 1)
    
    return temp_c, ph_val, ec_val, turb_val

# --- 6. MAIN FIELD TELEMETRY LOOP ---
while True:
    try:
        client.check_msg()  # Check if Python sent a Red Light command
        
        temp_c, ph_val, ec_val, turb_val = read_sensors()
        
        payload = json.dumps({
            "temp_C": temp_c,
            "pH": ph_val,
            "EC_uScm": ec_val,
            "turbidity_NTU": turb_val
        })
        
        client.publish(TOPIC_SENSORS, payload)
        print("Published Live Sensor Data:", payload)
        
        time.sleep(5)  # Send sensor packet every 5 seconds
    except Exception as e:
        print("MQTT/Sensor Error, reconnecting...", e)
        time.sleep(5)
        machine.reset()

"""
Integrates DS18B20 flame sensor, MQ135 smoke sensor, and temperature sensor
through a RP Pico W using MicroPython to turn on/off lighting and notify users through a webpage
Additional files: index.html, 
Authors: Claire Saunders-Kong, Taya Short, Julia Kalhous
"""


import machine, time, network, socket, math, onewire, ds18x20, json
from machine import ADC, Pin

#initialize sensor data in dictionary
sensor_data = {"smoke": 0, "tempC": 0, "flameDetected": False}

# onboard LED, create an output pin
led_onboard = Pin(16, Pin.OUT)

# light mode: AUTO, MANUAL_ON, MANUAL_OFF
light_mode = "AUTO"

# assigns resistance of physical sensor(kilo-ohms)
RLOAD = 1.0

# set sensor resistance ratio for clean air
RO_CALIBRATION_FACTOR = 3.6

# curve constants for CO2: PPM = a*(Rs/Ro)^b
CO2_A = 110.47
CO2_B = -2.86

# locate sensor, assign variable name to data
MQ135 = ADC(Pin(26))
#conversion factor 
conversion_factor = 3.3 / 65535

# initial code for temperature sensor
ds_pin = machine.Pin(22)
ds_sensor = ds18x20.DS18X20(onewire.OneWire(ds_pin))

roms = ds_sensor.scan()
if not roms:
    print("No DS18B20 found")
else:
    print("Sensor found at:", roms[0])
    print("Found DS devices:", roms)

# initial code for flame sensor
DO_PIN = Pin(0, Pin.IN)


#converts reading from MQ135 to voltage then to resistance using Rs=Rload(Vin/Vout-1)
def get_resistance():
    volts = MQ135.read_u16() * (conversion_factor)
    if volts == 0:
        return 0.1
    
    resistance = ((3.3 / volts) - 1) * RLOAD
    return resistance

def calibrate_resistance():
    print("Calibrating initial resistance in clean air...")
    print("Please wait 10 seconds.")
    total_resistance = 0
    #averages 50 readings of the initial resistance
    for _ in range(50):
        total_resistance += get_resistance()
        time.sleep(0.1)
        
    resistance_o = (total_resistance / 50) / RO_CALIBRATION_FACTOR
    print("Calibration is complete. Initial resistance is {:.2f} kOhm".format(resistance_o))
    return resistance_o

def update_sensors():
    global sensor_data
    # reads temp sensor, assigns value to tempC, and prints temperature
    if roms:
        ds_sensor.convert_temp()
        time.sleep_ms(750)
        val = ds_sensor.read_temp(roms[0])

    if val is not None:
        sensor_data["tempC"] = val
        print("Temperature: {:.2f}".format(val))

    else:
        sensor_data["tempC"] = 0

    # flameDetected is false if DO_PIN.value()== 1, true if 0
    sensor_data["flameDetected"] = (DO_PIN.value() == 0)

    # ratio 1 if air clean, <1 if smoke present, converts to ppm
    resistance = get_resistance()
    ratio = resistance / resistance_initial
    sensor_data["smoke"] = CO2_A * math.pow(ratio, CO2_B)

def apply_light_logic():
    global light_mode

    if light_mode == "MANUAL_ON":
        led_onboard.value(1)

    elif light_mode == "MANUAL_OFF":
        led_onboard.value(0)

    else:
    # AUTO mode
        smoke_threshold = 1500
        temp_threshold = 60

        smoke_alarm = (sensor_data["smoke"] >= smoke_threshold)
        temp_alarm = (sensor_data["tempC"] >= temp_threshold)
        flame_alarm = (sensor_data["flameDetected"])

        if smoke_alarm and (temp_alarm or flame_alarm):
            led_onboard.value(1)
            
        elif temp_alarm and flame_alarm :
            led_onboard.value(1)
            
        else:
            led_onboard.value(0)

# run calibrate_ro to set initial resistance
resistance_initial = calibrate_resistance()

# Create an Access Point
ssid = 'Fire Safety Systems Co'
password = 'FireGals'

ap = network.WLAN(network.AP_IF)
ap.config(essid=ssid, password=password)
ap.active(True)

while ap.active() == False:
    pass

print("Connection is successful")
print(ap.ifconfig())

# Create a socket server
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('', 80))
s.listen(5)
s.settimeout(1.0)

while True:
    update_sensors()
    apply_light_logic()

    try:
        conn, addr = s.accept()
        request = conn.recv(1024).decode('utf-8')
        first_line = request.split("\r\n")[0]
        print(first_line)

        if "GET /light?mode=on" in first_line:
            light_mode = "MANUAL_ON"
            apply_light_logic()
            response = json.dumps({"status": "ok","mode": light_mode,"lightIsOn": True})

            conn.send("HTTP/1.1 200 OK\r\n")
            conn.send("Content-Type: application/json\r\n")
            conn.send("Connection: close\r\n\r\n")
            conn.send(response)

        elif "GET /light?mode=off" in first_line:
            light_mode = "MANUAL_OFF"
            apply_light_logic()

            response = json.dumps({
            "status": "ok",
            "mode": light_mode,
            "lightIsOn": False
            })

            conn.send("HTTP/1.1 200 OK\r\n")
            conn.send("Content-Type: application/json\r\n")
            conn.send("Connection: close\r\n\r\n")
            conn.send(response)

        elif "GET /light?mode=auto" in first_line:
            light_mode = "AUTO"
            apply_light_logic()

            response = json.dumps({
            "status": "ok",
            "mode": light_mode,
            "lightIsOn": bool(led_onboard.value())
            })

            conn.send("HTTP/1.1 200 OK\r\n")
            conn.send("Content-Type: application/json\r\n")
            conn.send("Connection: close\r\n\r\n")
            conn.send(response)

        elif "GET /readings" in first_line:
            update_sensors()
            apply_light_logic()

            readings = {
            "smoke": sensor_data["smoke"],
            "tempC": sensor_data["tempC"],
            "flameDetected": sensor_data["flameDetected"],
            "lightMode": light_mode,
            "lightIsOn": bool(led_onboard.value())
            }

            conn.send("HTTP/1.1 200 OK\r\n")
            conn.send("Content-Type: application/json\r\n")
            conn.send("Connection: close\r\n\r\n")
            conn.send(json.dumps(readings))

        else:
            with open("index.html", "r") as f:
                conn.send("HTTP/1.1 200 OK\r\n")
                conn.send("Content-Type: text/html\r\n")
                conn.send("Connection: close\r\n\r\n")

                while True:
                    chunk = f.read(512)
                    if not chunk:break
                    conn.sendall(chunk)

        conn.close()

    except OSError:
        pass
    except Exception as e:
        print("Error:", e)
    try:
        conn.close()
    except:
        pass


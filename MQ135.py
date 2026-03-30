"""
MQ135 solo code to print MQ135 data from Raspberry Pi ADC pin
"""
import time
import network
import socket
import math
from machine import ADC, Pin

"""PIN_MQ135 = 26"""
# assign load resistance (kilo-ohms)
RLOAD = 1.0
# set sensor resistance ratio for clean air
RO_CALIBRATION_FACTOR = 3.6

#curve constants for CO2: PPM = a*(Rs/Ro)^b
CO2_A = 110.47
CO2_B = -2.86

#locate sensor and assign variable name to data
MQ135 = ADC(Pin(26))
conversion_factor = 3.3 / 65535

def get_resistance():
    volts = MQ135.read_u16()*(3.3/65535)
    if volts == 0: return 0.1 # to avoid div by 0
    resistance = ((3.3 / volts) - 1) *RLOAD
    return resistance

def calibrate_resistance():
    print("Calibrating initial resistance in clean air...")
    print("Please wait 10 seconds.")
    total_resistance = 0
    for _ in range (50):
        total_resistance += get_resistance()
        time.sleep(0.1)
    resistance_o = (total_resistance / 50) / RO_CALIBRATION_FACTOR
    print(f"Calibration is complete. Initial resistance is {resistance_o:.2f} kOhm")
    return resistance_o

# run calibrate_ro to set inital resistance
resistance_initial = calibrate_resistance()

# Create an Access Point
ssid = 'Fire Safety Systems Co'       #Set access point name. you can change this name.
password = 'FireGals'      #Set your access point password. You can use your own password

ap = network.WLAN(network.AP_IF)
ap.config(essid=ssid, password=password)
ap.active(True)            # Activate the access point

while ap.active() == False:
  pass
print('Connection is successful')
print(ap.ifconfig()) # this line will print the IP address of the Pico board

# Create a socket server
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('', 80))
s.listen(5) # maximum number of requests that can be queued


while True:
    try:
        # Response when connection received 
        conn, addr = s.accept()
        print('Got a connection from %s' % str(addr))
        request = conn.recv(1024)
    
        #read data and convert to voltage
        voltage = MQ135.read_u16()*conversion_factor
        #calculate PPM
        resistance = get_resistance()
        ratio = resistance / resistance_initial
        ppm = CO2_A * math.pow(ratio, CO2_B)
    
        #print voltage
        print(f"Voltage: {voltage:.2f}V | PPM: {ppm:.1f}")
         
        #load HTML file
        with open('index.html', 'r') as f:
            html = f.read()
            
        #format data for website
        response = html.replace('%VALUE%', f" {ppm:.1f}")
        
        conn.send("HTTP/1.1 200 OK\r\n")
        conn.send("Content-Type: text/html\r\n")
        conn.send("Connection: close\r\n\r\n")
        conn.sendall(response)
        conn.close()
    
    except Exception as e:
        print("Error:", e)
        if 'conn' in locals(): conn.close()
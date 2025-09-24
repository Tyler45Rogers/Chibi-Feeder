from machine import Pin, RTC
import time
import network
import ntptime
from microdot import Microdot, Response
import _thread

# ----------------------------
# User Config - Internet Stuff
# ----------------------------
SSID = ""
PASSWORD = ""

STEP_PIN = 17
DIR_PIN = 16
MOTOR_DIR = True  # True or False depending on desired rotation

FEED_DURATION = 2  # seconds
STEP_DELAY = 0.001  # stepper speed

# ----------------------------
# Globals
# ----------------------------
hourTime = 8
minuteTime = 0

# ----------------------------
# Setup Microdot
# ----------------------------
app = Microdot()

# ----------------------------
# Stepper Setup
# ----------------------------
step_pin = Pin(STEP_PIN, Pin.OUT)
dir_pin = Pin(DIR_PIN, Pin.OUT)
dir_pin.value(MOTOR_DIR)

def rotate_motor(duration=FEED_DURATION, step_delay=STEP_DELAY):
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < duration * 1000:
        step_pin.value(1)
        time.sleep(step_delay)
        step_pin.value(0)
        time.sleep(step_delay)

# ----------------------------
# Wi-Fi
# ----------------------------
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    while not wlan.isconnected():
        print("Connecting to Wi-Fi...")
        time.sleep(1)
    print("Connected!", wlan.ifconfig())

connect_wifi()

# ----------------------------
# NTP Sync (once)
# ----------------------------
def sync_time():
    try:
        ntptime.host = "pool.ntp.org"
        ntptime.settime()
        print("NTP time synced")
    except OSError as e:
        print("Failed to sync NTP:", e)

sync_time()

# ----------------------------
# Central Time with DST
# ----------------------------
def get_central_time():
    rtc = RTC()
    utc_time = list(rtc.datetime())  # tuple → list
    year, month, day, weekday, hour, minute, second, subseconds = utc_time

    # DST adjustment
    if (month > 3 and month < 11) or (month == 3 and day >= 10) or (month == 11 and day < 3):
        timezone_offset = -5  # CDT
    else:
        timezone_offset = -6  # CST

    hour += timezone_offset
    if hour < 0:
        hour += 24
        day -= 1
    elif hour >= 24:
        hour -= 24
        day += 1

    utc_time[4] = hour
    utc_time[2] = day

    return tuple(utc_time)

# ----------------------------
# Feeding Time Functions
# ----------------------------
def setFeedingTime(h, m):
    global hourTime, minuteTime
    hourTime = h
    minuteTime = m
    print(f"Time set to Hour: {hourTime}, Minute: {minuteTime}")

def getHourTime():
    return hourTime

def getMinuteTime():
    return minuteTime

# ----------------------------
# Check Feeding Time Loop
# ----------------------------
def check_feeding_time():
    while True:
        rtc_time = get_central_time()
        hour, minute = rtc_time[4], rtc_time[5]

        if hour == hourTime and minute == minuteTime:
            print("Feeding time! Rotating motor...")
            rotate_motor()
            # Wait 60 seconds to prevent multiple triggers in same minute
            time.sleep(60)
        time.sleep(1)

# Start thread for motor checking
_thread.start_new_thread(check_feeding_time, ())

# ----------------------------
# Microdot Web Interface
# ----------------------------
@app.route('/', methods=['GET', 'POST'])
def index(request):
    global hourTime, minuteTime
    
    if request.method == 'POST':
        try:
            h = int(request.form.get('hour'))
            m = int(request.form.get('minute'))
            am_pm = request.form.get('ampm')
            
            if 1 <= h <= 12 and 0 <= m < 60 and am_pm in ['AM', 'PM']:
                if am_pm == 'AM':
                    hour24 = 0 if h == 12 else h
                else:
                    hour24 = 12 if h == 12 else h + 12
                    
                setFeedingTime(hour24, m)
            else:
                return "Invalid time entered", 400
        except (TypeError, ValueError):
            return "Invalid input", 400

    # Display stored time in 12-hour format
    if hourTime == 0:
        disp_hour = 12
        disp_ampm = 'AM'
    elif hourTime < 12:
        disp_hour = hourTime
        disp_ampm = 'AM'
    elif hourTime == 12:
        disp_hour = 12
        disp_ampm = 'PM'
    else:
        disp_hour = hourTime - 12
        disp_ampm = 'PM'

    html = f'''<!DOCTYPE html>
    <html>
    <head>
      <title>Feeding Time Setup</title>
      <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f4f7f8; color: #333; display: flex; justify-content: center; align-items: flex-start; height: 100vh; margin: 0; padding: 20px; }}
        .container {{ background: white; padding: 25px 35px; border-radius: 12px; box-shadow: 0 8px 20px rgba(0,0,0,0.1); width: 320px; }}
        h2 {{ margin-top: 0; text-align: center; color: #2c3e50; }}
        p {{ text-align: center; font-size: 1.1em; margin-bottom: 25px; color: #34495e; }}
        label {{ display: block; margin-bottom: 8px; font-weight: 600; }}
        input[type=number], select {{ width: 100%; padding: 8px 10px; margin-bottom: 18px; border: 1px solid #ccd6dd; border-radius: 6px; font-size: 1em; box-sizing: border-box; transition: border-color 0.3s ease; }}
        input[type=number]:focus, select:focus {{ border-color: #3498db; outline: none; }}
        input[type=submit] {{ width: 100%; background-color: #3498db; border: none; padding: 12px 0; font-size: 1.1em; color: white; border-radius: 6px; cursor: pointer; transition: background-color 0.3s ease; }}
        input[type=submit]:hover {{ background-color: #2980b9; }}
      </style>
    </head>
    <body>
      <div class="container">
        <h2>Set Feeding Time</h2>
        <p>Current feeding time: {disp_hour}:{minuteTime:02d} {disp_ampm}</p>
        <form method="POST">
          <label for="hour">Hour (1-12):</label>
          <input id="hour" name="hour" type="number" min="1" max="12" value="{disp_hour}" required>
          
          <label for="minute">Minute (0-59):</label>
          <input id="minute" name="minute" type="number" min="0" max="59" value="{minuteTime}" required>
          
          <label for="ampm">AM/PM:</label>
          <select id="ampm" name="ampm">
            <option value="AM" {"selected" if disp_ampm == "AM" else ""}>AM</option>
            <option value="PM" {"selected" if disp_ampm == "PM" else ""}>PM</option>
          </select>
          
          <input type="submit" value="Update Time">
        </form>
      </div>
    </body>
    </html>
    '''
    resp = Response(html)
    resp.headers['Content-Type'] = 'text/html'
    return resp

# ----------------------------
# Start Web Server
# ----------------------------
app.run(host="0.0.0.0", port=80)

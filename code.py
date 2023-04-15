# Outside Temperature Visualizer

#######################
# Imports
#######################
import gc                                                               # garbage colletor
import supervisor                                                       # system management

import math                                                             # maths
import time                                                             # timing
import board                                                            # base
import busio                                                            # serial protocols
import alarm                                                            # alarm used for power savings

from adafruit_esp32spi import adafruit_esp32spi                         # ESP32
import adafruit_esp32spi.adafruit_esp32spi_socket as socket             # ESP32 socket for network

from digitalio import DigitalInOut                                      # input/output
import digitalio
import analogio                                                         # light sensor

import neopixel                                                         # NeoPixel
import adafruit_requests as requests                                    # adafruit HTTP library
import displayio                                                        # display

from adafruit_bitmap_font import bitmap_font                            # font loading
from adafruit_display_text.label import Label                           # fancy text labels

from adafruit_lc709203f import LC709203F, PackSize                      # battery voltage

import adafruit_touchscreen                                             # capacitive capture
import audiomp3                                                         # audio mp3
import audioio                                                          # audio

print("I AM ALIVE:", str(time.monotonic()))

# simple monotonic logger
def log(*msg):
    message = ("[", str(time.monotonic()), "]:", str(msg))
    print(' '.join(message))

#######################
# Pre-Hardware Globals
#######################

STATUS_LIGHT_BRIGHTNESS = 0.3
SLEEP_INTERVAL          = 10
BATTERY_PACK_SIZE       = PackSize.MAH2000
LAST_RUNTIME            = 0

#######################
# Hardware Init
#######################

# https://docs.espressif.com/projects/esp-idf/en/latest/api-reference/peripherals/spi_master.html
ESP32_CS       = DigitalInOut(board.ESP_CS)
ESP32_READY    = DigitalInOut(board.ESP_BUSY)
ESP32_RESET    = DigitalInOut(board.ESP_RESET)
SPI            = busio.SPI(board.SCK, board.MOSI, board.MISO)
ESP            = adafruit_esp32spi.ESP_SPIcontrol(SPI, ESP32_CS, ESP32_READY, ESP32_RESET)
STATUS_LIGHT   = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=STATUS_LIGHT_BRIGHTNESS)
LIGHT_SENSOR   = analogio.AnalogIn(board.LIGHT)
DISPLAY        = board.DISPLAY

#######################
# Mode Toggles
#######################

DEBUG           = False

#######################
# Display
#######################

# display groups
splash = displayio.Group()
bg_group = displayio.Group()
splash.append(bg_group)

# let there be light
#if not DEBUG:
DISPLAY.show(splash)

#######################
# Socket Init
#######################

socket.set_interface(ESP)
requests.set_socket(socket, ESP)

#######################
# Touchscreen Init
#######################

touchscreen = adafruit_touchscreen.Touchscreen(
    board.TOUCH_XL,
    board.TOUCH_XR,
    board.TOUCH_YD,
    board.TOUCH_YU,
    size=(board.DISPLAY.width, board.DISPLAY.height),
)

#######################
# Fonts and Labels
#######################

cwd                    = ("/"+__file__).rsplit('/', 1)[0]
big_font               = bitmap_font.load_font(cwd+"/fonts/Nunito-Light-75.bdf")
big_font.load_glyphs(b'0123456789:')

# label positions and colors
temp_position          = (30, 110)
text_color             = 0xFFFFFF

# label group
textarea               = Label(big_font, text='  ')
textarea.x             = temp_position[0]
textarea.y             = temp_position[1]
textarea.color         = text_color
textarea.scale         = 3
splash.append(textarea)

#######################
# Background Colors
#######################

color_black            = 0x000000
color_white            = 0xFFFFFF
color_bitmap           = displayio.Bitmap(320, 240, 1)
colorp_black           = displayio.Palette(1)
colorp_white           = displayio.Palette(1)
colorp_red             = displayio.Palette(1)
colorp_yellow          = displayio.Palette(1)
colorp_purple_dark     = displayio.Palette(1)
colorp_purple_light    = displayio.Palette(1)
colorp_blue_dark       = displayio.Palette(1)
colorp_blue_light      = displayio.Palette(1)
colorp_black[0]        = color_black
colorp_white[0]        = color_white
colorp_red[0]          = 0xEF0808
colorp_purple_dark[0]  = 0x6008A1
colorp_purple_light[0] = 0xC990F3
colorp_blue_dark[0]    = 0x180AEE
colorp_blue_light[0]   = 0x90E3FF
colorp_yellow[0]       = 0xEFFF00

#######################
# Backgrounds
#######################

bg_black               = displayio.TileGrid(color_bitmap, pixel_shader=colorp_black,        x=0, y=0)
bg_white               = displayio.TileGrid(color_bitmap, pixel_shader=colorp_white,        x=0, y=0)
bg_red                 = displayio.TileGrid(color_bitmap, pixel_shader=colorp_red,          x=0, y=0)
bg_yellow              = displayio.TileGrid(color_bitmap, pixel_shader=colorp_yellow,       x=0, y=0)
bg_purple_dark         = displayio.TileGrid(color_bitmap, pixel_shader=colorp_purple_dark,  x=0, y=0)
bg_purple_light        = displayio.TileGrid(color_bitmap, pixel_shader=colorp_purple_light, x=0, y=0)
bg_blue_dark           = displayio.TileGrid(color_bitmap, pixel_shader=colorp_blue_dark,    x=0, y=0)
bg_blue_light          = displayio.TileGrid(color_bitmap, pixel_shader=colorp_blue_light,   x=0, y=0)

#######################
# Secrets Init
#######################

try:
    from secrets import secrets
except ImportError:
    log("failed to import secrets.py")
    raise

#######################
# Metrics Init
#######################

influxdb_query    = "SELECT LAST(temperature_f) FROM weather WHERE location='outside' AND time >= now() - 30m"

influxdb_path     = secrets["influx_query_path"] + "?db=" + secrets["influx_database"]
influxdb_base_url = secrets["influx_scheme"] + "://" + secrets["influx_host"] + ":" + secrets["influx_port"] + influxdb_path
influxdb_url      = influxdb_base_url + "&q=" + influxdb_query

#######################
# Functions
#######################

def set_backlight(val):
    val = max(0, min(1.0, val))
    board.DISPLAY.brightness = val

def UpdateBacklightOnLightValue():
    val = LIGHT_SENSOR.value

    if val < 750:
        set_backlight(0.3)  # lights are dim
    elif val < 900:
        set_backlight(0.5)  # lights are less dim
    elif val < 2000:
        set_backlight(0.7)  # lights are somewhat bright
    elif val < 6000:
        set_backlight(0.8)  # daylight around 2000-2500+ in the living room
    elif val <= 65535:
        set_backlight(1)    # flashlight directly on sensor

def SwitchTextColor():
    if textarea.color == color_white:
        textarea.color = color_black
    else:
        textarea.color = color_white

def UpdateDisplay(temperature):

    while bg_group:
        bg_group.pop()
    if temperature < 0:        # Daisy needs boots
        bg_group.append(bg_purple_dark)
        textarea.color = color_white
        textarea.scale = 3
    elif temperature < 20:     # Daisy needs foot wax
        bg_group.append(bg_purple_light)
        textarea.color = color_white
        textarea.scale = 3
    elif temperature < 40:     # Daisy needs a coat
        bg_group.append(bg_blue_dark)
        textarea.color = color_white
        textarea.scale = 3
    elif temperature < 65:     # Ryan needs a coat
        bg_group.append(bg_blue_light)
        textarea.color = color_black
        textarea.scale = 3
    elif temperature < 80:     # Ryan needs shorts
        bg_group.append(bg_yellow)
        textarea.color = color_black
        textarea.scale = 3
    elif temperature < 200:    # Ryan needs suntan lotion
        bg_group.append(bg_red)
        textarea.color = color_white
        textarea.scale = 2
    elif temperature < 500:    # Ryan needs underground bunker
        bg_group.append(bg_white)
        textarea.color = color_black
        textarea.scale = 2
    else:
        bg_group.append(bg_black)
        textarea.color = color_white

    textarea.text = str(temperature)

# update neopixel using hexadecimal strings (convert to RGB color tuple)
def set_neo_hex(hex):
    payload_clean = hex.lstrip('#')
    return tuple(int(payload_clean[i:i+2], 16) for i in (0, 2, 4))

def go_to_sleep(sleep_period):
    # Create an alarm that will trigger sleep_period number of seconds from now.
    time_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + sleep_period)

    # Exit and deep sleep until the alarm wakes us.
    alarm.exit_and_deep_sleep_until_alarms(time_alarm)

def connect():
    if ESP.status == adafruit_esp32spi.WL_CONNECTED:
        log("ESP32 found and already connected, exiting")
        return
    elif ESP.status == adafruit_esp32spi.WL_IDLE_STATUS:
        log("ESP32 found and in idle mode, continuing")
    else:
        log("ESP32 unknown status:", ESP.status)
        return

    log("Firmware version:", ESP.firmware_version)
    log("MAC address:", [hex(i) for i in ESP.MAC_address])

    log("Connecting to AP")
    while not ESP.is_connected:
        try:
            ESP.connect_AP(secrets["ssid"], secrets["password"])
        except OSError as e:
            log("Could not connect to AP, retrying:", e)
            continue

    log("Connected to:", str(ESP.ssid, "utf-8"), "RSSI:", ESP.rssi)
    log("IP address:", ESP.pretty_ip(ESP.ip_address))

#######################
# Main Init
#######################

connect()

#######################
# Main Loop
#######################

while True:
    # update backlight based on light sensor
    UpdateBacklightOnLightValue()

    # ensure we reconnect to wifi
    if not ESP.is_connected:
        connect()

    # attempt query with exception handling
    try:
        response = requests.post(influxdb_url)\
    # this exception is sometimes unrecoverable
    except RuntimeError as re:
        # ('ESP32 unknown status:', 6)
        # ('POST request RunTimeError', RuntimeError('Sending request failed',))
        log("POST request RunTimeError", re)
        supervisor.reload()
        continue
    except Exception as e:
        log("POST request failed", e)
        time.sleep(SLEEP_INTERVAL)
        continue

    # this condition was unrecoverable before an ESP32 firmware upgrade to 1.7.4
    if response._received_length == 0:
        log("POST response had zero (0) length")
        supervisor.reload()
        continue

    # attempt json parsing
    try:
        json_data = response.json()
    except Exception as e:
        log("JSON parsing failed", response, e)
        response.close()
        time.sleep(SLEEP_INTERVAL)
        continue

    # get value
    temperature = math.floor(json_data["results"][0]["series"][0]["values"][0][1])

    # update display
    UpdateDisplay(temperature)

    # close the response
    response.close()

    # delete the data
    del response
    del json_data

    # garbage collect
    gc.collect()

    # sleep
    time.sleep(SLEEP_INTERVAL)

#######################
# Should not terminate
#######################

print("I AM SLAIN:", str(time.monotonic()))
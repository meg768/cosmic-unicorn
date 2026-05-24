# Wi-Fi network used by the Pico W / Pico 2 W.
WIFI_SSID = "your-wifi-name"
WIFI_PASSWORD = "your-wifi-password"

# Board model. Used to choose the scroll delay.
# Supported values: "Pico W" and "Pico 2 W".
COSMIC_UNICORN_MODEL = "Pico W"

# Default banner request. MQTT text messages can override these fields.
BANNER_TEXT = "👍"
BANNER_BASE_URL = "http://cosmic-unicorn.egelberg.se/"
BANNER_HEIGHT = 32
BANNER_FONT = ""
BANNER_SIZE = None
BANNER_WIDTH = None
BANNER_COLOR = None
BANNER_BACKGROUND = "black"
BANNER_PADDING = None
BANNER_GAP = None
BANNER_FORMAT = "bmp"

# MQTT broker and topic for incoming text/animation messages.
MQTT_HOST = "server.example.com"
MQTT_PORT = 1883
MQTT_TOPIC = "cosmic-unicorn"
MQTT_USERNAME = "your-mqtt-username"
MQTT_PASSWORD = "your-mqtt-password"

# MQTT reconnect and keepalive timing, in milliseconds.
MQTT_RECONNECT_MS = 5000
MQTT_PING_MS = 25000

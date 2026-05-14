import time
import network

try:
    from secrets import WIFI_SSID, WIFI_PASSWORD
except ImportError:
    WIFI_SSID = None
    WIFI_PASSWORD = None


def connect_wifi(timeout=15):
    if not WIFI_SSID or not WIFI_PASSWORD:
        print("Missing WiFi credentials in secrets.py")
        return None

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        return wlan

    print("Connecting to WiFi:", WIFI_SSID)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)

    start_time = time.time()
    while time.time() - start_time < timeout:
        status = wlan.status()
        if status == 3:
            return wlan
        if status < 0:
            break
        time.sleep(1)

    print("WiFi connection failed, status:", wlan.status())
    return None

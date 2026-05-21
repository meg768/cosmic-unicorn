import time
import network
import config


def connect_wifi(timeout=15):
    if not config.WIFI_SSID or not config.WIFI_PASSWORD:
        print("Missing WiFi credentials in config.py")
        return None

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        print("WiFi address:", wlan.ifconfig()[0])
        return wlan

    print("Connecting to WiFi:", config.WIFI_SSID)
    wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)

    start_time = time.time()
    while time.time() - start_time < timeout:
        status = wlan.status()
        if status == 3:
            print("WiFi address:", wlan.ifconfig()[0])
            return wlan
        if status < 0:
            break
        time.sleep(1)

    print("WiFi connection failed, status:", wlan.status())
    return None

import time
import network
import config


def config_value(name, default=None):
    return getattr(config, name, default)


def connect_wifi(timeout=15):
    wifi_ssid = config_value("WIFI_SSID")
    wifi_password = config_value("WIFI_PASSWORD")

    if not wifi_ssid or not wifi_password:
        print("Missing WiFi credentials in config.py")
        return None

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        print("WiFi address:", wlan.ifconfig()[0])
        return wlan

    print("Connecting to WiFi:", wifi_ssid)
    wlan.connect(wifi_ssid, wifi_password)

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

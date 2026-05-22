import time
import network
import ntptime
import clock


def connect(ssid, password, timeout=15):
    if not ssid or not password:
        raise ValueError("Missing WiFi credentials")

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        ntptime.settime()
        print("Connected to Wi-Fi, local time is {}".format(clock.format_time()))
        return wlan

    wlan.connect(ssid, password)

    start_time = time.time()
    while time.time() - start_time < timeout:
        status = wlan.status()
        if status == 3:
            ntptime.settime()
            print("Connected to Wi-Fi, local time is {}".format(clock.format_time()))
            return wlan
        if status < 0:
            break
        time.sleep(1)

    raise OSError("WiFi connection failed, status: {}".format(wlan.status()))

import os
import socket
import time
import machine

try:
    import ujson as json
except ImportError:
    import json

from cosmic import CosmicUnicorn
from picographics import PicoGraphics, DISPLAY_COSMIC_UNICORN as DISPLAY
from pngdec import PNG
from wifi import connect_wifi

try:
    from umqtt.simple import MQTTClient
except ImportError:
    MQTTClient = None

try:
    from secrets import MQTT_HOST
except ImportError:
    MQTT_HOST = "server.egelberg.se"

try:
    from secrets import MQTT_PORT
except ImportError:
    MQTT_PORT = 1883

try:
    from secrets import MQTT_TOPIC
except ImportError:
    MQTT_TOPIC = None

try:
    from secrets import MQTT_USERNAME
except ImportError:
    MQTT_USERNAME = None

try:
    from secrets import MQTT_PASSWORD
except ImportError:
    MQTT_PASSWORD = None


# Overclock for smoother scrolling on the Cosmic Unicorn.
machine.freq(200000000)

# Banner configuration.
BANNER_TEXT = "👍"
BANNER_BASE_URL = "http://banner.egelberg.se/"
BANNER_HEIGHT = 32
BANNER_FONT = ""
BANNER_SIZE = None
BANNER_WIDTH = None
BANNER_COLOR = None
BANNER_BACKGROUND = "black"
BANNER_PADDING = None
BANNER_GAP = None

# Local files used for safe image updates.
IMAGE = "display.png"
TEMP_IMAGE = "display.new.png"

# Display behavior.
BRIGHTNESS = 1
SCROLL_DELAY = 0.02
MQTT_RECONNECT_MS = 5000
MQTT_PING_MS = 25000

cosmic = CosmicUnicorn()
graphics = PicoGraphics(DISPLAY)
png = PNG(graphics)

WIDTH = CosmicUnicorn.WIDTH
BLACK = graphics.create_pen(0, 0, 0)
URL_SAFE_BYTES = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~"
BANNER_QUEUE = []


def file_exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False


def safe_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def url_encode(text):
    parts = []

    for value in text.encode("utf-8"):
        if value in URL_SAFE_BYTES:
            parts.append(chr(value))
        else:
            parts.append("%{:02X}".format(value))

    return "".join(parts)


def to_bytes(value):
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    return value.encode("utf-8")


def add_query_param(parts, key, value):
    if value is None or value == "":
        return

    parts.append("{}={}".format(key, url_encode(str(value))))


def build_banner_request(text=None, overrides=None):
    request = {
        "text": BANNER_TEXT if text is None else text,
        "height": BANNER_HEIGHT,
        "width": BANNER_WIDTH,
        "font": BANNER_FONT,
        "size": BANNER_SIZE,
        "color": BANNER_COLOR,
        "background": BANNER_BACKGROUND,
        "padding": BANNER_PADDING,
        "gap": BANNER_GAP,
    }

    if overrides:
        for key, value in overrides.items():
            request[key] = value

    return request


def build_image_url(banner_request):
    query_parts = []

    add_query_param(query_parts, "text", banner_request.get("text"))
    add_query_param(query_parts, "height", banner_request.get("height"))
    add_query_param(query_parts, "width", banner_request.get("width"))
    add_query_param(query_parts, "font", banner_request.get("font"))
    add_query_param(query_parts, "size", banner_request.get("size"))
    add_query_param(query_parts, "color", banner_request.get("color"))
    add_query_param(query_parts, "background", banner_request.get("background"))
    add_query_param(query_parts, "padding", banner_request.get("padding"))
    add_query_param(query_parts, "gap", banner_request.get("gap"))

    return "{}?{}".format(BANNER_BASE_URL, "&".join(query_parts))


def parse_url(url):
    if not url.startswith("http://"):
        raise ValueError("Only http:// URLs are supported")

    remainder = url[7:]
    slash_index = remainder.find("/")
    if slash_index == -1:
        host_port = remainder
        path = "/"
    else:
        host_port = remainder[:slash_index]
        path = remainder[slash_index:]

    if ":" in host_port:
        host, port_text = host_port.split(":", 1)
        port = int(port_text)
    else:
        host = host_port
        port = 80

    return host, port, path


def download_file(url, target_path):
    try:
        host, port, path = parse_url(url)
    except ValueError as error:
        print("Bad URL:", error)
        return False

    sock = None
    target = None

    try:
        address = socket.getaddrinfo(host, port)[0][-1]
        sock = socket.socket()
        sock.connect(address)

        request = "GET {} HTTP/1.0\r\nHost: {}\r\nConnection: close\r\n\r\n".format(path, host)
        sock.send(request.encode())

        target = open(target_path, "wb")
        header_buffer = b""
        headers_done = False

        while True:
            chunk = sock.recv(1024)
            if not chunk:
                break

            if not headers_done:
                header_buffer += chunk
                marker = header_buffer.find(b"\r\n\r\n")
                if marker == -1:
                    continue

                header_text = header_buffer[:marker].decode("utf-8", "ignore")
                status_line = header_text.split("\r\n", 1)[0]
                status_parts = status_line.split(" ", 2)
                status_code = int(status_parts[1]) if len(status_parts) > 1 else 0

                if status_code != 200:
                    print("HTTP error:", status_line)
                    return False

                target.write(header_buffer[marker + 4:])
                headers_done = True
            else:
                target.write(chunk)

        if not headers_done:
            print("Invalid HTTP response")
            return False

        return True
    except Exception as error:
        print("Download failed:", error)
        return False
    finally:
        if target:
            target.close()
        if sock:
            sock.close()


def activate_download():
    try:
        safe_remove(IMAGE)
        os.rename(TEMP_IMAGE, IMAGE)
        return True
    except OSError as error:
        print("Unable to activate new image:", error)
        safe_remove(TEMP_IMAGE)
        return False


def load_image_width(path):
    try:
        png.open_file(path)
        return png.get_width()
    except RuntimeError as error:
        print("Invalid PNG:", error)
        return None


def refresh_image(banner_request, wlan=None):
    image_url = build_image_url(banner_request)

    if wlan is None or not wlan.isconnected():
        wlan = connect_wifi()
    if not wlan:
        return False, None

    print("Downloading:", banner_request.get("text", ""))
    if not download_file(image_url, TEMP_IMAGE):
        safe_remove(TEMP_IMAGE)
        safe_remove(IMAGE)
        return False, wlan

    if load_image_width(TEMP_IMAGE) is None:
        safe_remove(TEMP_IMAGE)
        safe_remove(IMAGE)
        return False, wlan

    return activate_download(), wlan


def load_image():
    if not file_exists(IMAGE):
        return None

    return load_image_width(IMAGE)


def draw_frame(image_width, x):
    graphics.set_pen(BLACK)
    graphics.clear()

    if image_width is not None:
        if x > 0:
            png.decode(x, 0, source=(0, 0, WIDTH - x, 32))
        elif x > -image_width:
            png.decode(0, 0, source=(-x, 0, WIDTH, 32))

    cosmic.update(graphics)


def advance_scroll(x, image_width):
    if image_width is None:
        return x

    x -= 1
    if x < -image_width:
        return -image_width
    return x


def initialize_display():
    cosmic.set_brightness(BRIGHTNESS)
    draw_frame(None, WIDTH)


def initialize_image(banner_request, wlan):
    if mqtt_configured():
        return None, wlan

    refreshed, wlan = refresh_image(banner_request, wlan)

    if refreshed:
        return load_image(), wlan

    return None, wlan


def mqtt_configured():
    return bool(MQTT_HOST and MQTT_TOPIC and MQTT_USERNAME and MQTT_PASSWORD)


def build_mqtt_client_id():
    try:
        suffix = "".join("{:02x}".format(value) for value in machine.unique_id())
    except AttributeError:
        suffix = "pico"

    return "cosmic-unicorn-" + suffix[-8:]


def normalize_banner_request(payload):
    if not isinstance(payload, dict):
        return None

    request = {}
    allowed_keys = (
        "text",
        "height",
        "width",
        "font",
        "size",
        "color",
        "background",
        "padding",
        "gap",
    )

    for key in allowed_keys:
        if key in payload:
            request[key] = payload[key]

    if "text" in request and request["text"] is not None:
        request["text"] = str(request["text"]).strip()

    for key in ("height", "width", "size", "padding", "gap"):
        if key in request and request[key] not in (None, ""):
            try:
                request[key] = int(request[key])
            except Exception:
                print("Invalid banner field:", key)
                return None

    for key in ("font", "color", "background"):
        if key in request and request[key] is not None:
            request[key] = str(request[key]).strip()

    return build_banner_request(overrides=request)


def decode_mqtt_payload(message):
    try:
        payload = message.decode("utf-8").strip()
    except Exception:
        print("MQTT message decode failed")
        return None

    if not payload:
        return None

    if payload.startswith("{"):
        try:
            parsed = json.loads(payload)
        except Exception as error:
            print("MQTT JSON parse failed, using plain text:", error)
            return build_banner_request(text=payload)

        banner_request = normalize_banner_request(parsed)

        if banner_request is not None:
            return banner_request

        print("MQTT JSON invalid, using plain text")
        return build_banner_request(text=payload)

    return build_banner_request(text=payload)


def enqueue_banner_request(banner_request):
    BANNER_QUEUE.append(banner_request)
    print("MQTT message:", banner_request.get("text", ""), "(queue:", len(BANNER_QUEUE), ")")


def dequeue_banner_request():
    if not BANNER_QUEUE:
        return None

    return BANNER_QUEUE.pop(0)


def handle_mqtt_message(topic, message):
    banner_request = decode_mqtt_payload(message)
    if banner_request is None:
        return

    enqueue_banner_request(banner_request)


def connect_mqtt(wlan=None):
    if not mqtt_configured():
        return None, wlan

    if MQTTClient is None:
        print("MQTT unavailable: umqtt.simple not found")
        return None, wlan

    if wlan is None or not wlan.isconnected():
        wlan = connect_wifi()
    if not wlan:
        return None, None

    client = None

    try:
        client = MQTTClient(
            client_id=to_bytes(build_mqtt_client_id()),
            server=MQTT_HOST,
            port=MQTT_PORT,
            user=to_bytes(MQTT_USERNAME),
            password=to_bytes(MQTT_PASSWORD),
            keepalive=60,
        )
        client.set_callback(handle_mqtt_message)
        client.connect()
        client.subscribe(to_bytes(MQTT_TOPIC))
        print("MQTT connected:", MQTT_TOPIC)
        return client, wlan
    except Exception as error:
        print("MQTT connection failed:", error)
        if client is not None:
            try:
                client.disconnect()
            except Exception:
                pass
        return None, wlan


def disconnect_mqtt(client):
    if client is None:
        return

    try:
        client.disconnect()
    except Exception:
        pass


def mqtt_would_block(error):
    code = None

    if hasattr(error, "args") and error.args:
        code = error.args[0]

    return code in (-1, 11, 35, 110, 116, 119)


def poll_mqtt(client):
    if client is None:
        return None

    try:
        client.check_msg()
        return client
    except OSError as error:
        if mqtt_would_block(error):
            return client
        print("MQTT disconnected:", error)
        disconnect_mqtt(client)
        return None


def ping_mqtt(client):
    if client is None:
        return None

    try:
        client.ping()
        return client
    except Exception as error:
        print("MQTT ping failed:", error)
        disconnect_mqtt(client)
        return None
    except Exception as error:
        print("MQTT disconnected:", error)
        disconnect_mqtt(client)
        return None


def apply_banner_request(banner_request, image_width, wlan):
    refreshed, wlan = refresh_image(banner_request, wlan)

    if refreshed:
        new_width = load_image()
        if new_width is not None:
            print("Image updated")
            return banner_request, new_width, WIDTH, wlan

    return banner_request, None, WIDTH, wlan


def animation_finished(image_width, x):
    if image_width is None:
        return True

    return x <= -image_width


def run():
    initialize_display()

    current_request = build_banner_request()
    wlan = connect_wifi()
    if wlan:
        print("WiFi connected")
    else:
        print("WiFi not connected")

    image_width, wlan = initialize_image(current_request, wlan)
    mqtt_client = None
    next_mqtt_retry_at = time.ticks_ms()
    next_mqtt_ping_at = time.ticks_ms()
    x = WIDTH

    while True:
        draw_frame(image_width, x)
        x = advance_scroll(x, image_width)

        if mqtt_configured():
            if mqtt_client is None:
                now = time.ticks_ms()
                if time.ticks_diff(now, next_mqtt_retry_at) >= 0:
                    mqtt_client, wlan = connect_mqtt(wlan)
                    next_mqtt_retry_at = time.ticks_add(now, MQTT_RECONNECT_MS)
                    next_mqtt_ping_at = time.ticks_add(now, MQTT_PING_MS)
            else:
                mqtt_client = poll_mqtt(mqtt_client)
                if mqtt_client is None:
                    next_mqtt_retry_at = time.ticks_add(time.ticks_ms(), MQTT_RECONNECT_MS)
                else:
                    now = time.ticks_ms()
                    if time.ticks_diff(now, next_mqtt_ping_at) >= 0:
                        mqtt_client = ping_mqtt(mqtt_client)
                        if mqtt_client is None:
                            next_mqtt_retry_at = time.ticks_add(time.ticks_ms(), MQTT_RECONNECT_MS)
                        else:
                            next_mqtt_ping_at = time.ticks_add(now, MQTT_PING_MS)

        if animation_finished(image_width, x):
            next_request = dequeue_banner_request()
        else:
            next_request = None

        if next_request is not None:
            current_request = next_request
            current_request, image_width, x, wlan = apply_banner_request(current_request, image_width, wlan)

        time.sleep(SCROLL_DELAY)


if __name__ == "__main__":
    run()

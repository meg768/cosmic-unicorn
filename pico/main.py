import os
import socket
import time
import machine
import config
import gc
import ujson as json

from animations import gif as gif_animation
from animations import matrix as matrix_animation

from cosmic import CosmicUnicorn
from picographics import PicoGraphics, DISPLAY_COSMIC_UNICORN as DISPLAY
from wifi import connect
from umqtt.simple import MQTTClient


# Overclock for smoother scrolling on the Cosmic Unicorn.
machine.freq(200000000)


# Display behavior.
cosmic = CosmicUnicorn()
graphics = PicoGraphics(DISPLAY)

BLACK = graphics.create_pen(0, 0, 0)
ACTION_QUEUE = []
IMAGE_INFO = None


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
    url_safe_bytes = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~"
    parts = []

    for value in text.encode("utf-8"):
        if value in url_safe_bytes:
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
        "text": config.BANNER_TEXT if text is None else text,
        "height": config.BANNER_HEIGHT,
        "width": config.BANNER_WIDTH,
        "font": config.BANNER_FONT,
        "size": config.BANNER_SIZE,
        "color": config.BANNER_COLOR,
        "background": config.BANNER_BACKGROUND,
        "padding": config.BANNER_PADDING,
        "gap": config.BANNER_GAP,
        "format": config.BANNER_FORMAT,
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
    add_query_param(query_parts, "format", banner_request.get("format"))

    return "{}?{}".format(config.BANNER_BASE_URL, "&".join(query_parts))


def build_animation_url(name=None):
    query_parts = []

    add_query_param(query_parts, "name", name)
    add_query_param(query_parts, "format", "cuf")

    return "{}/animation?{}".format(config.BANNER_BASE_URL.rstrip("/"), "&".join(query_parts))


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
    except ValueError:
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
                    return False

                target.write(header_buffer[marker + 4:])
                headers_done = True
            else:
                target.write(chunk)

        if not headers_done:
            return False

        return True
    except Exception:
        return False
    finally:
        if target:
            target.close()
        if sock:
            sock.close()


def activate_download():
    image = "display.bmp"
    temp_image = "display.new.bmp"

    try:
        safe_remove(image)
        os.rename(temp_image, image)
        return True
    except OSError:
        safe_remove(temp_image)
        return False


def read_le_u16(data, offset):
    return data[offset] | (data[offset + 1] << 8)


def read_le_u32(data, offset):
    return (
        data[offset]
        | (data[offset + 1] << 8)
        | (data[offset + 2] << 16)
        | (data[offset + 3] << 24)
    )


def read_le_i32(data, offset):
    value = read_le_u32(data, offset)
    if value & 0x80000000:
        return value - 0x100000000
    return value


def load_bmp_info(path):
    global IMAGE_INFO

    try:
        source = open(path, "rb")
        header = source.read(54)

        if len(header) < 54 or header[0:2] != b"BM":
            return None

        pixel_offset = read_le_u32(header, 10)
        dib_size = read_le_u32(header, 14)
        width = read_le_i32(header, 18)
        stored_height = read_le_i32(header, 22)
        planes = read_le_u16(header, 26)
        bits_per_pixel = read_le_u16(header, 28)
        compression = read_le_u32(header, 30)

        if width <= 0 or stored_height == 0:
            return None

        if planes != 1 or bits_per_pixel != 24 or compression != 0:
            return None

        height = abs(stored_height)
        top_down = stored_height < 0

        IMAGE_INFO = {
            "width": width,
            "height": height,
            "bytes_per_pixel": 3,
            "top_down": top_down,
            "pixel_offset": pixel_offset,
            "row_stride": ((width * 3 + 3) // 4) * 4,
        }
        return IMAGE_INFO
    except Exception:
        return None
    finally:
        try:
            source.close()
        except Exception:
            pass


def load_image_width(path):
    try:
        info = load_bmp_info(path)
        if info is not None:
            return info["width"]
    except Exception:
        return None


def refresh_image(banner_request, wlan=None):
    image = "display.bmp"
    temp_image = "display.new.bmp"
    image_url = build_image_url(banner_request)
    collect_garbage()

    if wlan is None or not wlan.isconnected():
        wlan = connect(config.WIFI_SSID, config.WIFI_PASSWORD)

    if not download_file(image_url, temp_image):
        safe_remove(temp_image)
        safe_remove(image)
        collect_garbage()
        return False, wlan

    collect_garbage()

    if load_image_width(temp_image) is None:
        safe_remove(temp_image)
        safe_remove(image)
        collect_garbage()
        return False, wlan

    activated = activate_download()
    collect_garbage()
    return activated, wlan


def load_image():
    image = "display.bmp"

    if not file_exists(image):
        return None

    return load_image_width(image)


def draw_frame(image_width, x):
    graphics.set_pen(BLACK)
    graphics.clear()

    if image_width is not None and IMAGE_INFO is not None:
        draw_bmp_frame(x)

    cosmic.update(graphics)


def draw_bmp_frame(x):
    info = IMAGE_INFO
    image_width = info["width"]
    image_height = info["height"]

    visible_width = CosmicUnicorn.WIDTH
    source_x = 0
    screen_x = x

    if x > 0:
        visible_width = min(CosmicUnicorn.WIDTH - x, image_width)
    else:
        source_x = -x
        screen_x = 0
        visible_width = min(CosmicUnicorn.WIDTH, image_width - source_x)

    if visible_width <= 0:
        return

    visible_height = min(CosmicUnicorn.HEIGHT, image_height)

    try:
        source = open("display.bmp", "rb")
        for y in range(visible_height):
            if info["top_down"]:
                file_row = y
            else:
                file_row = image_height - 1 - y

            row_offset = info["pixel_offset"] + file_row * info["row_stride"] + source_x * info["bytes_per_pixel"]
            source.seek(row_offset)
            row = source.read(visible_width * info["bytes_per_pixel"])

            for column in range(visible_width):
                base = column * 3
                blue = row[base]
                green = row[base + 1]
                red = row[base + 2]
                graphics.set_pen(graphics.create_pen(red, green, blue))
                graphics.pixel(screen_x + column, y)
    except Exception:
        pass
    finally:
        try:
            source.close()
        except Exception:
            pass


def advance_scroll(x, image_width):
    if image_width is None:
        return x

    x -= 1
    if x < -image_width:
        return -image_width
    return x


def initialize_display():
    cosmic.set_brightness(1)
    draw_frame(None, CosmicUnicorn.WIDTH)


def mqtt_port():
    try:
        return int(config.MQTT_PORT)
    except Exception:
        return 1883


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
        "format",
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
                return None

    for key in ("font", "color", "background", "format"):
        if key in request and request[key] is not None:
            request[key] = str(request[key]).strip()

    return build_banner_request(overrides=request)


def normalize_animation_action(payload):
    if not isinstance(payload, dict):
        return None

    name = payload.get("name", payload.get("animation", None))
    if name is not None:
        name = str(name).strip()
        if not name:
            name = None

    duration = payload.get("duration", payload.get("duration_seconds", None))
    if duration is None:
        duration_ms = 60000
    else:
        try:
            duration_ms = int(duration) * 1000
        except Exception:
            return None

    if duration_ms < 1000:
        duration_ms = 1000

    return {
        "type": "animation",
        "name": name,
        "duration_ms": duration_ms,
    }


def decode_mqtt_payload(message):
    try:
        payload = message.decode("utf-8").strip()
    except Exception:
        return None

    if not payload:
        return None

    if payload.startswith("{"):
        try:
            parsed = json.loads(payload)
        except Exception:
            return {
                "type": "text",
                "request": build_banner_request(text=payload),
            }

        payload_type = str(parsed.get("type", "text")).strip().lower() if isinstance(parsed, dict) else "text"

        if payload_type == "animation":
            animation_action = normalize_animation_action(parsed)
            if animation_action is not None:
                return animation_action

            return None

        if payload_type != "text":
            return None

        banner_request = normalize_banner_request(parsed)

        if banner_request is not None:
            return {
                "type": "text",
                "request": banner_request,
            }

        return {
            "type": "text",
            "request": build_banner_request(text=payload),
        }

    return {
        "type": "text",
        "request": build_banner_request(text=payload),
    }


def enqueue_action(action):
    ACTION_QUEUE.append(action)


def dequeue_action():
    if not ACTION_QUEUE:
        return None

    return ACTION_QUEUE.pop(0)


def handle_mqtt_message(topic, message):
    action = decode_mqtt_payload(message)
    if action is None:
        return

    enqueue_action(action)


def connect_mqtt(wlan=None):
    collect_garbage()

    if wlan is None or not wlan.isconnected():
        wlan = connect(config.WIFI_SSID, config.WIFI_PASSWORD)

    client = None

    try:
        client = MQTTClient(
            client_id=to_bytes(build_mqtt_client_id()),
            server=config.MQTT_HOST,
            port=mqtt_port(),
            user=to_bytes(config.MQTT_USERNAME),
            password=to_bytes(config.MQTT_PASSWORD),
            keepalive=60,
        )
        client.set_callback(handle_mqtt_message)
        client.connect()
        client.subscribe(to_bytes(config.MQTT_TOPIC))
        collect_garbage()
        return client, wlan
    except Exception:
        if client is not None:
            try:
                client.disconnect()
            except Exception:
                pass
        collect_garbage()
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
        disconnect_mqtt(client)
        return None


def ping_mqtt(client):
    if client is None:
        return None

    try:
        client.ping()
        return client
    except Exception:
        disconnect_mqtt(client)
        return None


def maintain_mqtt(mqtt_client, wlan, next_mqtt_retry_at, next_mqtt_ping_at):
    if mqtt_client is None:
        now = time.ticks_ms()
        if time.ticks_diff(now, next_mqtt_retry_at) >= 0:
            mqtt_client, wlan = connect_mqtt(wlan)
            next_mqtt_retry_at = time.ticks_add(now, config.MQTT_RECONNECT_MS)
            next_mqtt_ping_at = time.ticks_add(now, config.MQTT_PING_MS)
        return mqtt_client, wlan, next_mqtt_retry_at, next_mqtt_ping_at

    mqtt_client = poll_mqtt(mqtt_client)
    if mqtt_client is None:
        next_mqtt_retry_at = time.ticks_add(time.ticks_ms(), config.MQTT_RECONNECT_MS)
        return mqtt_client, wlan, next_mqtt_retry_at, next_mqtt_ping_at

    now = time.ticks_ms()
    if time.ticks_diff(now, next_mqtt_ping_at) >= 0:
        mqtt_client = ping_mqtt(mqtt_client)
        if mqtt_client is None:
            next_mqtt_retry_at = time.ticks_add(time.ticks_ms(), config.MQTT_RECONNECT_MS)
        else:
            next_mqtt_ping_at = time.ticks_add(now, config.MQTT_PING_MS)

    return mqtt_client, wlan, next_mqtt_retry_at, next_mqtt_ping_at


def collect_garbage():
    gc.collect()


def play_animation_action(action, mqtt_client, wlan, next_mqtt_retry_at, next_mqtt_ping_at):
    name = action.get("name")
    duration_ms = action.get("duration_ms", 60000)
    animation_path = "animation.cuf"
    temp_animation_path = "animation.new.cuf"

    def tick():
        nonlocal mqtt_client, wlan, next_mqtt_retry_at, next_mqtt_ping_at
        mqtt_client, wlan, next_mqtt_retry_at, next_mqtt_ping_at = maintain_mqtt(
            mqtt_client,
            wlan,
            next_mqtt_retry_at,
            next_mqtt_ping_at,
        )

    if name is not None:
        name = str(name).strip()

    if name is not None and name.lower() == "matrix":
        matrix_animation.play(graphics, cosmic, BLACK, duration_ms, tick, collect_garbage)
        return mqtt_client, wlan, next_mqtt_retry_at, next_mqtt_ping_at

    collect_garbage()
    safe_remove(temp_animation_path)
    safe_remove(animation_path)

    if not download_file(build_animation_url(name), temp_animation_path):
        safe_remove(temp_animation_path)
        return mqtt_client, wlan, next_mqtt_retry_at, next_mqtt_ping_at

    try:
        os.rename(temp_animation_path, animation_path)
        collect_garbage()

        gif_animation.play(
            animation_path,
            graphics,
            cosmic,
            BLACK,
            duration_ms,
            CosmicUnicorn.WIDTH,
            CosmicUnicorn.HEIGHT,
            tick,
            collect_garbage,
        )
    finally:
        safe_remove(temp_animation_path)
        safe_remove(animation_path)
        collect_garbage()

    return mqtt_client, wlan, next_mqtt_retry_at, next_mqtt_ping_at


def apply_banner_request(banner_request, image_width, wlan):
    collect_garbage()
    refreshed, wlan = refresh_image(banner_request, wlan)

    if refreshed:
        new_width = load_image()
        if new_width is not None:
            collect_garbage()
            return banner_request, new_width, CosmicUnicorn.WIDTH, wlan

    collect_garbage()
    return banner_request, None, CosmicUnicorn.WIDTH, wlan


def animation_finished(image_width, x):
    if image_width is None:
        return True

    return x <= -image_width


def run():
    initialize_display()

    wlan = connect(config.WIFI_SSID, config.WIFI_PASSWORD)

    image_width = None
    mqtt_client = None
    next_mqtt_retry_at = time.ticks_ms()
    next_mqtt_ping_at = time.ticks_ms()
    scroll_delay = {"Pico W": 0, "Pico 2 W": 3}[config.COSMIC_UNICORN_MODEL] / 1000
    x = CosmicUnicorn.WIDTH

    while True:
        draw_frame(image_width, x)
        x = advance_scroll(x, image_width)

        mqtt_client, wlan, next_mqtt_retry_at, next_mqtt_ping_at = maintain_mqtt(
            mqtt_client,
            wlan,
            next_mqtt_retry_at,
            next_mqtt_ping_at,
        )

        if animation_finished(image_width, x):
            next_action = dequeue_action()
        else:
            next_action = None

        if next_action is not None:
            collect_garbage()
            action_type = next_action.get("type")
            if action_type == "animation":
                mqtt_client, wlan, next_mqtt_retry_at, next_mqtt_ping_at = play_animation_action(
                    next_action,
                    mqtt_client,
                    wlan,
                    next_mqtt_retry_at,
                    next_mqtt_ping_at,
                )
                image_width = None
                x = CosmicUnicorn.WIDTH
                collect_garbage()
            else:
                current_request = next_action["request"]
                current_request, image_width, x, wlan = apply_banner_request(current_request, image_width, wlan)
        elif image_width is not None and animation_finished(image_width, x):
            image_width = None
            x = CosmicUnicorn.WIDTH
            collect_garbage()

        time.sleep(scroll_delay)


if __name__ == "__main__":
    run()

import os
import random
import socket
import time
import machine

try:
    import gc
except ImportError:
    gc = None

try:
    import ujson as json
except ImportError:
    import json

from cosmic import CosmicUnicorn
from picographics import PicoGraphics, DISPLAY_COSMIC_UNICORN as DISPLAY
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
BANNER_FORMAT = "bmp"

# Local files used for safe image updates.
IMAGE = "display.bmp"
TEMP_IMAGE = "display.new.bmp"

# Display behavior.
BRIGHTNESS = 1
SCROLL_DELAY = 0.01
MQTT_RECONNECT_MS = 5000
MQTT_PING_MS = 25000
IDLE_ANIMATION_DIR = "cufs"
IDLE_MIN_MS = 60000
IDLE_INTERVAL_MS = 17 * 60 * 1000

cosmic = CosmicUnicorn()
graphics = PicoGraphics(DISPLAY)

WIDTH = CosmicUnicorn.WIDTH
HEIGHT = CosmicUnicorn.HEIGHT
BLACK = graphics.create_pen(0, 0, 0)
URL_SAFE_BYTES = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~"
BANNER_QUEUE = []
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
        "format": BANNER_FORMAT,
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


def read_le_u16(data, offset):
    return data[offset] | (data[offset + 1] << 8)


def rgb565_to_pen(value):
    red = ((value >> 11) & 0x1F) * 255 // 31
    green = ((value >> 5) & 0x3F) * 255 // 63
    blue = (value & 0x1F) * 255 // 31
    return graphics.create_pen(red, green, blue)


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
            print("Invalid BMP header")
            return None

        pixel_offset = read_le_u32(header, 10)
        dib_size = read_le_u32(header, 14)
        width = read_le_i32(header, 18)
        stored_height = read_le_i32(header, 22)
        planes = read_le_u16(header, 26)
        bits_per_pixel = read_le_u16(header, 28)
        compression = read_le_u32(header, 30)

        if width <= 0 or stored_height == 0:
            print("Invalid BMP size")
            return None

        if planes != 1 or bits_per_pixel != 24 or compression != 0:
            print("Unsupported BMP format")
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
    except Exception as error:
        print("Invalid BMP:", error)
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
    except Exception as error:
        print("Invalid image:", error)
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

    if image_width is not None and IMAGE_INFO is not None:
        draw_bmp_frame(x)

    cosmic.update(graphics)


def draw_bmp_frame(x):
    info = IMAGE_INFO
    image_width = info["width"]
    image_height = info["height"]

    visible_width = WIDTH
    source_x = 0
    screen_x = x

    if x > 0:
        visible_width = min(WIDTH - x, image_width)
    else:
        source_x = -x
        screen_x = 0
        visible_width = min(WIDTH, image_width - source_x)

    if visible_width <= 0:
        return

    visible_height = min(HEIGHT, image_height)

    try:
        source = open(IMAGE, "rb")
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
    except Exception as error:
        print("BMP draw failed:", error)
    finally:
        try:
            source.close()
        except Exception:
            pass


def join_path(directory, filename):
    if directory.endswith("/"):
        return directory + filename
    return directory + "/" + filename


def list_idle_animations():
    try:
        filenames = os.listdir(IDLE_ANIMATION_DIR)
    except OSError:
        return []

    animations = []
    for filename in filenames:
        if filename.lower().endswith(".cuf"):
            animations.append(join_path(IDLE_ANIMATION_DIR, filename))

    animations.sort()
    return animations


def choose_idle_animation():
    animations = list_idle_animations()
    if not animations:
        return None

    return animations[random.randint(0, len(animations) - 1)]


def read_cuf_header(source):
    magic = source.read(4)
    if magic != b"CUF3":
        raise ValueError("Unsupported CUF animation")

    header = source.read(10)
    if len(header) != 10:
        raise ValueError("Invalid CUF header")

    width = read_le_u16(header, 0)
    height = read_le_u16(header, 2)
    frame_count = read_le_u16(header, 4)
    delay_ms = read_le_u16(header, 6)
    palette_count = read_le_u16(header, 8)
    palette = []

    for _ in range(palette_count):
        color_data = source.read(2)
        if len(color_data) != 2:
            raise ValueError("Invalid CUF palette")
        palette.append(rgb565_to_pen(read_le_u16(color_data, 0)))

    return {
        "width": width,
        "height": height,
        "frame_count": frame_count,
        "delay_ms": delay_ms,
        "palette": palette,
    }


def read_cuf_frame_length(source):
    data = source.read(2)
    if len(data) != 2:
        raise ValueError("Invalid CUF frame")
    return read_le_u16(data, 0)


def draw_cuf_frame(frame_data, width, height, palette):
    graphics.set_pen(BLACK)
    graphics.clear()

    x_offset = max(0, (WIDTH - width) // 2)
    y_offset = max(0, (HEIGHT - height) // 2)
    visible_width = min(width, WIDTH)
    visible_height = min(height, HEIGHT)
    pixel_index = 0

    for offset in range(0, len(frame_data), 2):
        run_length = frame_data[offset]
        color_index = frame_data[offset + 1]
        pen = BLACK
        if color_index < len(palette):
            pen = palette[color_index]

        graphics.set_pen(pen)

        for _ in range(run_length):
            x = pixel_index % width
            y = pixel_index // width
            if x < visible_width and y < visible_height:
                graphics.pixel(x + x_offset, y + y_offset)
            pixel_index += 1

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
                print("Invalid banner field:", key)
                return None

    for key in ("font", "color", "background", "format"):
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


def maintain_mqtt(mqtt_client, wlan, next_mqtt_retry_at, next_mqtt_ping_at):
    if not mqtt_configured():
        return mqtt_client, wlan, next_mqtt_retry_at, next_mqtt_ping_at

    if mqtt_client is None:
        now = time.ticks_ms()
        if time.ticks_diff(now, next_mqtt_retry_at) >= 0:
            mqtt_client, wlan = connect_mqtt(wlan)
            next_mqtt_retry_at = time.ticks_add(now, MQTT_RECONNECT_MS)
            next_mqtt_ping_at = time.ticks_add(now, MQTT_PING_MS)
        return mqtt_client, wlan, next_mqtt_retry_at, next_mqtt_ping_at

    mqtt_client = poll_mqtt(mqtt_client)
    if mqtt_client is None:
        next_mqtt_retry_at = time.ticks_add(time.ticks_ms(), MQTT_RECONNECT_MS)
        return mqtt_client, wlan, next_mqtt_retry_at, next_mqtt_ping_at

    now = time.ticks_ms()
    if time.ticks_diff(now, next_mqtt_ping_at) >= 0:
        mqtt_client = ping_mqtt(mqtt_client)
        if mqtt_client is None:
            next_mqtt_retry_at = time.ticks_add(time.ticks_ms(), MQTT_RECONNECT_MS)
        else:
            next_mqtt_ping_at = time.ticks_add(now, MQTT_PING_MS)

    return mqtt_client, wlan, next_mqtt_retry_at, next_mqtt_ping_at


def collect_garbage():
    if gc is not None:
        gc.collect()


def play_idle_animation(mqtt_client, wlan, next_mqtt_retry_at, next_mqtt_ping_at):
    animation_path = choose_idle_animation()
    if animation_path is None:
        return mqtt_client, wlan, next_mqtt_retry_at, next_mqtt_ping_at

    collect_garbage()
    started_at = time.ticks_ms()
    loops = 0

    print("Idle animation:", animation_path)

    while True:
        source = None
        try:
            source = open(animation_path, "rb")
            header = read_cuf_header(source)
            width = header["width"]
            height = header["height"]
            frame_count = header["frame_count"]
            delay_ms = header["delay_ms"]
            palette = header["palette"]

            for frame_index in range(frame_count):
                frame_started_at = time.ticks_ms()
                frame_size = read_cuf_frame_length(source)
                frame_data = source.read(frame_size)
                if len(frame_data) != frame_size:
                    break

                draw_cuf_frame(frame_data, width, height, palette)
                mqtt_client, wlan, next_mqtt_retry_at, next_mqtt_ping_at = maintain_mqtt(
                    mqtt_client,
                    wlan,
                    next_mqtt_retry_at,
                    next_mqtt_ping_at,
                )

                elapsed = time.ticks_diff(time.ticks_ms(), frame_started_at)
                remaining = delay_ms - elapsed
                if remaining > 0:
                    time.sleep_ms(remaining)

                if frame_index % 20 == 0:
                    collect_garbage()
        except Exception as error:
            print("Idle animation failed:", error)
            break
        finally:
            try:
                source.close()
            except Exception:
                pass

        loops += 1
        collect_garbage()

        if time.ticks_diff(time.ticks_ms(), started_at) >= IDLE_MIN_MS:
            break

    print("Idle animation done:", animation_path, "loops:", loops)
    return mqtt_client, wlan, next_mqtt_retry_at, next_mqtt_ping_at


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
    next_idle_animation_at = time.ticks_add(time.ticks_ms(), IDLE_INTERVAL_MS)
    x = WIDTH

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
            next_request = dequeue_banner_request()
        else:
            next_request = None

        if next_request is not None:
            current_request = next_request
            current_request, image_width, x, wlan = apply_banner_request(current_request, image_width, wlan)
        elif animation_finished(image_width, x):
            now = time.ticks_ms()
            if time.ticks_diff(now, next_idle_animation_at) < 0:
                image_width = None
                x = WIDTH
                time.sleep(SCROLL_DELAY)
                continue

            mqtt_client, wlan, next_mqtt_retry_at, next_mqtt_ping_at = play_idle_animation(
                mqtt_client,
                wlan,
                next_mqtt_retry_at,
                next_mqtt_ping_at,
            )
            next_idle_animation_at = time.ticks_add(time.ticks_ms(), IDLE_INTERVAL_MS)
            image_width = None
            x = WIDTH

        time.sleep(SCROLL_DELAY)


if __name__ == "__main__":
    run()

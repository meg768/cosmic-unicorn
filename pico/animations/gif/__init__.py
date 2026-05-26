import time


FADE_MS = 500
FULL_BRIGHTNESS = 1


def animation_brightness(started_at, duration_ms):
    elapsed_ms = time.ticks_diff(time.ticks_ms(), started_at)
    remaining_ms = duration_ms - elapsed_ms
    brightness = FULL_BRIGHTNESS

    if elapsed_ms < FADE_MS:
        brightness = elapsed_ms / FADE_MS

    if remaining_ms < FADE_MS:
        fade_out_brightness = remaining_ms / FADE_MS
        if fade_out_brightness < brightness:
            brightness = fade_out_brightness

    if brightness < 0:
        return 0
    if brightness > FULL_BRIGHTNESS:
        return FULL_BRIGHTNESS
    return brightness


def read_u16(data, offset):
    return data[offset] | (data[offset + 1] << 8)


def rgb565_to_pen(graphics, value):
    red = ((value >> 11) & 0x1F) * 255 // 31
    green = ((value >> 5) & 0x3F) * 255 // 63
    blue = (value & 0x1F) * 255 // 31
    return graphics.create_pen(red, green, blue)


def read_header(source, graphics):
    magic = source.read(4)
    if magic != b"CUF3":
        raise ValueError("Unsupported CUF animation")

    header = source.read(10)
    if len(header) != 10:
        raise ValueError("Invalid CUF header")

    width = read_u16(header, 0)
    height = read_u16(header, 2)
    frame_count = read_u16(header, 4)
    delay_ms = read_u16(header, 6)
    palette_count = read_u16(header, 8)
    palette = []

    for _ in range(palette_count):
        color_data = source.read(2)
        if len(color_data) != 2:
            raise ValueError("Invalid CUF palette")
        palette.append(rgb565_to_pen(graphics, read_u16(color_data, 0)))

    return {
        "width": width,
        "height": height,
        "frame_count": frame_count,
        "delay_ms": delay_ms,
        "palette": palette,
    }


def read_frame(source):
    data = source.read(2)
    if len(data) != 2:
        raise ValueError("Invalid CUF frame")

    frame_size = read_u16(data, 0)
    frame_data = source.read(frame_size)
    if len(frame_data) != frame_size:
        raise ValueError("Invalid CUF frame data")

    return frame_data


def render_frame(graphics, cosmic, black, frame_data, width, height, palette, display_width, display_height):
    graphics.set_pen(black)
    graphics.clear()

    x_offset = max(0, (display_width - width) // 2)
    y_offset = max(0, (display_height - height) // 2)
    visible_width = min(width, display_width)
    visible_height = min(height, display_height)
    pixel_index = 0

    for offset in range(0, len(frame_data), 2):
        run_length = frame_data[offset]
        color_index = frame_data[offset + 1]
        pen = black
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


def animation_basename(path):
    name = path
    slash_index = name.rfind("/")
    if slash_index != -1:
        name = name[slash_index + 1:]

    dot_index = name.rfind(".")
    if dot_index != -1:
        name = name[:dot_index]

    return name


def play(
    animation_path,
    graphics,
    cosmic,
    black,
    duration_ms,
    display_width,
    display_height,
    tick=None,
    collect_garbage=None,
):
    animation_name = animation_basename(animation_path)
    started_at = time.ticks_ms()
    loops = 0

    while True:
        source = None
        header = None
        palette = None
        frame_data = None

        try:
            source = open(animation_path, "rb")
            header = read_header(source, graphics)
            width = header["width"]
            height = header["height"]
            frame_count = header["frame_count"]
            delay_ms = header["delay_ms"]
            palette = header["palette"]

            for frame_index in range(frame_count):
                frame_started_at = time.ticks_ms()
                frame_data = read_frame(source)
                cosmic.set_brightness(animation_brightness(started_at, duration_ms))
                render_frame(
                    graphics,
                    cosmic,
                    black,
                    frame_data,
                    width,
                    height,
                    palette,
                    display_width,
                    display_height,
                )

                if tick:
                    tick()

                elapsed = time.ticks_diff(time.ticks_ms(), frame_started_at)
                remaining = delay_ms - elapsed
                if remaining > 0:
                    time.sleep_ms(remaining)

        except Exception:
            break
        finally:
            try:
                source.close()
            except Exception:
                pass

            source = None
            header = None
            palette = None
            frame_data = None

        loops += 1

        if collect_garbage:
            collect_garbage()

        if time.ticks_diff(time.ticks_ms(), started_at) >= duration_ms:
            break

    cosmic.set_brightness(FULL_BRIGHTNESS)

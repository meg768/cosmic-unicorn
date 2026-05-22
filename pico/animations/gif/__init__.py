import os


ANIMATION_DIR = "animations/gif/cufs"


def join_path(directory, filename):
    if directory.endswith("/"):
        return directory + filename
    return directory + "/" + filename


def list_animations(animation_dir=ANIMATION_DIR):
    try:
        filenames = os.listdir(animation_dir)
    except OSError:
        return []

    animations = []
    for filename in filenames:
        if filename.lower().endswith(".cuf"):
            animations.append(join_path(animation_dir, filename))

    animations.sort()
    return animations


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

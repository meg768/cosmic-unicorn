#!/usr/bin/env python3
from pathlib import Path
import struct
import sys

from PIL import Image, ImageSequence


def rgb_to_565(red, green, blue):
    return ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)


def convert_gif(input_path, output_path):
    image = Image.open(input_path)
    width, height = image.size
    frames = []
    durations = []

    for frame in ImageSequence.Iterator(image):
        rgba = frame.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
        background.alpha_composite(rgba)
        rgb = background.convert("RGB")
        frames.append(rgb)
        durations.append(frame.info.get("duration", image.info.get("duration", 60)) or 60)

    if not frames:
        raise ValueError("GIF contains no frames")

    delay_ms = round(sum(durations) / len(durations))

    palette_source = Image.new("RGB", (width, height * len(frames)))
    for index, frame in enumerate(frames):
        palette_source.paste(frame, (0, index * height))

    paletted_source = palette_source.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    palette_bytes = paletted_source.getpalette()[: 256 * 3]
    palette = []
    for index in range(0, len(palette_bytes), 3):
        palette.append(tuple(palette_bytes[index : index + 3]))

    paletted_frames = []
    for frame in frames:
        paletted_frames.append(frame.quantize(palette=paletted_source))

    with open(output_path, "wb") as target:
        target.write(b"CUF3")
        target.write(struct.pack("<HHHHH", width, height, len(frames), delay_ms, len(palette)))

        for red, green, blue in palette:
            target.write(struct.pack("<H", rgb_to_565(red, green, blue)))

        for frame in paletted_frames:
            indexes = frame.tobytes()
            encoded = bytearray()
            run_value = indexes[0]
            run_length = 1

            for value in indexes[1:]:
                if value == run_value and run_length < 255:
                    run_length += 1
                else:
                    encoded.append(run_length)
                    encoded.append(run_value)
                    run_value = value
                    run_length = 1

            encoded.append(run_length)
            encoded.append(run_value)
            target.write(struct.pack("<H", len(encoded)))
            target.write(encoded)

    return width, height, len(frames), delay_ms


def main():
    clean_output = False

    if len(sys.argv) == 1:
        input_path = Path("gifs")
        output_path = Path("cufs")
        clean_output = True
    elif len(sys.argv) == 3:
        input_path = Path(sys.argv[1])
        output_path = Path(sys.argv[2])
    else:
        print("Usage: convert.py")
        print("   or: convert.py input.gif output.cuf")
        print("   or: convert.py input-gif-dir output-cuf-dir")
        return 2

    if input_path.is_dir():
        output_path.mkdir(parents=True, exist_ok=True)

        if clean_output:
            for cuf_path in output_path.glob("*.cuf"):
                cuf_path.unlink()

        gif_paths = sorted(input_path.glob("*.gif"))
        if not gif_paths:
            print("No GIF files found in {}".format(input_path))
            return 1

        for gif_path in gif_paths:
            cuf_path = output_path / (gif_path.stem + ".cuf")
            width, height, frame_count, delay_ms = convert_gif(gif_path, cuf_path)
            print("{}: {}x{}, {} frames, {} ms/frame".format(cuf_path, width, height, frame_count, delay_ms))
        return 0

    width, height, frame_count, delay_ms = convert_gif(input_path, output_path)
    print("{}: {}x{}, {} frames, {} ms/frame".format(output_path, width, height, frame_count, delay_ms))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

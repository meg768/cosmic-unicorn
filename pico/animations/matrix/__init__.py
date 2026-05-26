import machine
import random
import time
import clock

from cosmic import CosmicUnicorn
from picographics import PicoGraphics, DISPLAY_COSMIC_UNICORN as DISPLAY


BRIGHTNESS = 1
FADE_MS = 500
FRAME_DELAY_MS = 0

WIDTH = CosmicUnicorn.WIDTH
HEIGHT = CosmicUnicorn.HEIGHT


def animation_brightness(started_at, duration_ms):
    elapsed_ms = time.ticks_diff(time.ticks_ms(), started_at)
    remaining_ms = duration_ms - elapsed_ms
    brightness = BRIGHTNESS

    if elapsed_ms < FADE_MS:
        brightness = elapsed_ms / FADE_MS

    if remaining_ms < FADE_MS:
        fade_out_brightness = remaining_ms / FADE_MS
        if fade_out_brightness < brightness:
            brightness = fade_out_brightness

    if brightness < 0:
        return 0
    if brightness > BRIGHTNESS:
        return BRIGHTNESS
    return brightness


def hsl_to_rgb(hue, saturation, luminance):
    hue = hue % 360
    saturation = max(0, min(100, saturation)) / 100
    luminance = max(0, min(100, luminance)) / 100

    chroma = (1 - abs(2 * luminance - 1)) * saturation
    hue_section = hue / 60
    second = chroma * (1 - abs((hue_section % 2) - 1))

    if hue_section < 1:
        red, green, blue = chroma, second, 0
    elif hue_section < 2:
        red, green, blue = second, chroma, 0
    elif hue_section < 3:
        red, green, blue = 0, chroma, second
    elif hue_section < 4:
        red, green, blue = 0, second, chroma
    elif hue_section < 5:
        red, green, blue = second, 0, chroma
    else:
        red, green, blue = chroma, 0, second

    match = luminance - chroma / 2
    return (
        int((red + match) * 255),
        int((green + match) * 255),
        int((blue + match) * 255),
    )


def current_time_hue():
    now = clock.localtime()
    hour = now[3] % 12
    minute = now[4]
    return int(360 * ((hour * 60) + minute) / (12 * 60))


class Worm:
    def __init__(self, column, height):
        self.column = column
        self.height = height
        self.reset()

    def reset(self):
        self.length = random.randint(max(3, self.height // 10), self.height)
        self.row = -self.length
        loop_options = (0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 3, 3, 4, 5)
        self.loops = loop_options[random.randint(0, len(loop_options) - 1)]
        self.ticks = 0
        self.hue = current_time_hue()

    def render(self, graphics):
        x = self.column
        y = self.row

        if y >= 0 and y < self.height:
            graphics.set_pen(graphics.create_pen(*hsl_to_rgb(self.hue, 100, 80)))
            graphics.pixel(x, y)
        y -= 1

        for index in range(self.length + 1):
            luminance_index = (self.length - index) / self.length
            if y >= 0 and y < self.height:
                luminance = int(luminance_index * 50)
                graphics.set_pen(graphics.create_pen(*hsl_to_rgb(self.hue, 100, luminance)))
                graphics.pixel(x, y)
            y -= 1

        self.ticks += 1
        if self.ticks >= self.loops:
            self.ticks = 0
            self.row += 1

            if self.row - self.length > self.height:
                self.reset()


def create_worms(width=WIDTH, height=HEIGHT):
    return [Worm(column, height) for column in range(width)]


def render_frame(graphics, cosmic, black, worms):
    graphics.set_pen(black)
    graphics.clear()

    for worm in worms:
        worm.render(graphics)

    cosmic.update(graphics)


def play(graphics, cosmic, black, duration_ms, tick=None, collect_garbage=None):
    started_at = time.ticks_ms()
    worms = create_worms(WIDTH, HEIGHT)

    while time.ticks_diff(time.ticks_ms(), started_at) < duration_ms:
        frame_started_at = time.ticks_ms()
        cosmic.set_brightness(animation_brightness(started_at, duration_ms))
        render_frame(graphics, cosmic, black, worms)

        if tick:
            tick()

        elapsed = time.ticks_diff(time.ticks_ms(), frame_started_at)
        remaining = FRAME_DELAY_MS - elapsed
        if remaining > 0:
            time.sleep_ms(remaining)

    worms = None
    cosmic.set_brightness(BRIGHTNESS)

    if collect_garbage:
        collect_garbage()


def run():
    machine.freq(200000000)
    cosmic = CosmicUnicorn()
    graphics = PicoGraphics(DISPLAY)
    black = graphics.create_pen(0, 0, 0)

    cosmic.set_brightness(BRIGHTNESS)
    worms = create_worms(WIDTH, HEIGHT)

    while True:
        render_frame(graphics, cosmic, black, worms)
        time.sleep_ms(FRAME_DELAY_MS)


if __name__ == "__main__":
    run()

# cosmic-unicorn

A MicroPython project for a Pimoroni Cosmic Unicorn with Pico W or Pico 2 W.

This version uses:

- Wi-Fi for networking
- NTP for clock sync
- MQTT for incoming text and animation messages
- [cosmic-unicorn.egelberg.se](http://cosmic-unicorn.egelberg.se) to render text as 24-bit BMP and serve CUF animations
- a local queue on the Pico so multiple messages are shown in order

## Idea

The Cosmic Unicorn does not generate text graphics on its own.

Instead, it works like this:

1. The Pico connects to Wi-Fi
2. The Pico syncs its clock with NTP
3. The Pico connects to MQTT
4. A message arrives on the configured MQTT topic
5. Text messages are rendered by `cosmic-unicorn.egelberg.se` as 24-bit BMP
6. Animation messages play either Matrix rain or a CUF animation downloaded from `cosmic-unicorn.egelberg.se`
7. The next MQTT message waits in queue until the current banner or animation is finished

This lets typography, emojis, colors, layout, and GIF-to-CUF animation storage be handled server-side, while the Pico only needs to display the downloaded output.

## Project Layout

The repository is split into Pico files and computer-side helper files.

Files under [pico/](/Users/magnus/Documents/GitHub/cosmic-unicorn/pico) are the files that belong on the Pico:

- [pico/main.py](/Users/magnus/Documents/GitHub/cosmic-unicorn/pico/main.py)
- [pico/config.example.py](/Users/magnus/Documents/GitHub/cosmic-unicorn/pico/config.example.py)
- [pico/wifi/](/Users/magnus/Documents/GitHub/cosmic-unicorn/pico/wifi)
- [pico/clock/](/Users/magnus/Documents/GitHub/cosmic-unicorn/pico/clock)
- [pico/umqtt/](/Users/magnus/Documents/GitHub/cosmic-unicorn/pico/umqtt)
- [pico/animations/](/Users/magnus/Documents/GitHub/cosmic-unicorn/pico/animations)

Computer-side files:

- [gifs/](/Users/magnus/Documents/GitHub/cosmic-unicorn/gifs) contains source GIF animations
- [tools/convert.py](/Users/magnus/Documents/GitHub/cosmic-unicorn/tools/convert.py) converts GIF files to CUF files for local experiments
- [casing/](/Users/magnus/Documents/GitHub/cosmic-unicorn/casing) contains casing and cutout files

On the Pico itself, upload the contents of `pico/` to the device root. The Pico root should then contain:

- `main.py`
- `config.py`
- `wifi/`
- `clock/`
- `umqtt/`
- `animations/`

`display.bmp` and `animation.cuf` are created and updated on the Pico at runtime and do not need to exist in the repository beforehand.

## Configuration

Create a local `pico/config.py` based on [pico/config.example.py](/Users/magnus/Documents/GitHub/cosmic-unicorn/pico/config.example.py).

`pico/config.py` contains local Wi-Fi and MQTT settings and should not be committed.

Example:

```python
WIFI_SSID = "your-wifi-name"
WIFI_PASSWORD = "your-wifi-password"

COSMIC_UNICORN_MODEL = "Pico W"

BANNER_TEXT = "👍"
BANNER_BASE_URL = "http://cosmic-unicorn.egelberg.se/"
BANNER_HEIGHT = 32
BANNER_FONT = ""
BANNER_SIZE = None
BANNER_WIDTH = None
BANNER_COLOR = None
BANNER_BACKGROUND = "black"
BANNER_PADDING = None
BANNER_GAP = None
BANNER_FORMAT = "bmp"

MQTT_HOST = "server.example.com"
MQTT_PORT = 1883
MQTT_TOPIC = "cosmic-unicorn"
MQTT_USERNAME = "your-mqtt-username"
MQTT_PASSWORD = "your-mqtt-password"

MQTT_RECONNECT_MS = 5000
MQTT_PING_MS = 25000
```

`COSMIC_UNICORN_MODEL` controls the scroll delay:

- `"Pico W"` uses `0` ms
- `"Pico 2 W"` uses `5` ms

## MQTT Format

The project accepts two types of MQTT payloads.

### 1. Plain Text

The simplest format:

```text
Happy birthday! 🥳
```

This becomes a banner using the default settings in `config.py`.

### 2. JSON

If the payload starts with `{`, it is parsed as JSON.

JSON messages can be either text messages or animation messages. When `type` is omitted, the message is treated as `type: "text"` for backwards compatibility.

Example:

```json
{
  "type": "text",
  "text": "Weather today [color=gold]☀️[/color] 18°C",
  "font": "impact",
  "size": 18,
  "color": "white",
  "background": "midnightblue",
  "padding": 4,
  "gap": 2,
  "height": 32
}
```

Supported text fields:

- `type`: optional, use `"text"` for explicit text messages
- `text`
- `height`
- `width`
- `font`
- `size`
- `color`
- `background`
- `padding`
- `gap`
- `format`

Animation examples:

```json
{
  "type": "animation",
  "name": "matrix",
  "duration": 60
}
```

```json
{
  "type": "animation",
  "name": "fireplace",
  "duration": 120
}
```

Supported animation fields:

- `type`: use `"animation"`
- `name`: optional; either `"matrix"` or the name of an animation served by `cosmic-unicorn.egelberg.se`
- `duration`: duration in seconds, default `60`

If `name` is omitted, `cosmic-unicorn.egelberg.se` chooses a random animation:

```json
{
  "type": "animation"
}
```

## Text Syntax

The `text` field supports plain text, emojis, and inline color markup handled by `banner`.

Basic examples:

```text
Hello world
```

```text
Coffee time ☕
```

```text
This is [color=blue]blue[/color] and this is [color=#FF00FF]magenta[/color]
```

The inline syntax is:

- `[color=name]text[/color]` for named colors
- `[color=#RRGGBB]text[/color]` for hex colors
- `[font=name]text[/font]` for inline font changes

Example JSON payload using the text syntax:

```json
{
  "text": "Market [color=gold]up[/color] 📈 and [color=red]down[/color] 📉",
  "background": "black",
  "height": 32
}
```

## Available Fonts

The `font` field is backed by the fonts available in the `banner` service.

Currently available font names:

- `arial`
- `arial-bold`
- `arial-black`
- `arial-rounded`
- `calibri`
- `century-gothic`
- `century-gothic-italic`
- `digital`
- `djb-digital`
- `gotham`
- `impact`
- `prototype`
- `roboto`
- `tahoma`
- `verdana`
- `verdana-bold`

Example:

```json
{
  "text": "[font=impact]Breaking[/font] news 🚨",
  "height": 32,
  "background": "black"
}
```

## Queue Behavior

Incoming MQTT messages are placed in an internal queue.

This means that if Homey sends multiple messages in quick succession:

- the current banner or animation is not interrupted
- the next message waits its turn
- messages are shown in order

This is important for Homey flows where several RSS or status messages may arrive almost at the same time.

## Animations

Animations are triggered by MQTT JSON messages with `type: "animation"`.

The animation behavior is:

- the display stays black when the MQTT queue is empty
- animation messages are queued in the same queue as text messages
- `matrix` plays the generated Matrix animation from `pico/animations/matrix/`
- other names download converted GIF/CUF animations from `cosmic-unicorn.egelberg.se/animation?format=cuf`
- CUF animations repeat until the requested duration has passed
- the current animation loop is always allowed to finish
- MQTT is still polled while animations play
- queued text messages wait until the current animation window is done

The Pico only stores one downloaded CUF at a time in `animation.cuf`, then deletes it after playback.

Source GIF and generated CUF files are managed by the `banner` service. The local converter is still useful for experiments:

```bash
python3 tools/convert.py
```

This converts all `gifs/*.gif` files into local `cufs/*.cuf`.

Useful 32 x 32 GIF collections:

- [LED Pixel Art Collection](https://ledpixelart.com/art/)
- [SmartMatrix 32x32 GIF Collection](https://community.pixelmatix.com/t/collection-of-32x32-gifs/51)

## Banner Service

The Pico always fetches plain `http://` images from:

- [cosmic-unicorn.egelberg.se](http://cosmic-unicorn.egelberg.se)

`pico/main.py` builds URLs roughly like this:

```text
http://cosmic-unicorn.egelberg.se/?text=Hello&height=32&font=impact&color=gold&format=bmp
```

This means all text layout happens outside the Pico.

## Startup Behavior

At startup, the Pico connects to Wi-Fi, syncs time with NTP, connects to MQTT, and waits for incoming messages.

This means:

- no default banner is downloaded from the network at boot
- the screen may remain empty until the first MQTT message arrives

If you want different boot behavior, that needs to be added in `pico/main.py`.

## Limitations

- The Pico only supports `http://` in this code, not `https://`
- if `banner` returns an invalid or too-large BMP, nothing new will be shown
- very long texts can still become too large for Pico memory
- retained MQTT messages are not a great fit here; normal non-retained messages work best

## Thonny

Typical Thonny workflow:

1. Connect to the Pico
2. Upload the contents of `pico/` to the root of `Raspberry Pi Pico`
3. Create or update `config.py` on the Pico
4. Run `main.py`
5. Send MQTT text or animation messages to the configured topic

The runtime is mostly quiet. Wi-Fi/NTP prints one connection time line; normal MQTT messages and image updates do not print status lines.

## Sync

The easiest way to upload the Pico files is with `mpremote`:

```bash
tools/sync-pico.sh
```

Useful variants:

```bash
tools/sync-pico.sh --dry-run
tools/sync-pico.sh --reset
tools/sync-pico.sh --connect /dev/cu.usbmodem1101
```

The script uploads the contents of `pico/` to the device root. It skips local editor files, `.DS_Store` files, and CUF files. `pico/config.py` is uploaded if it exists.

## Homey

This project works well with Homey flows.

Typical setup:

1. Homey triggers on RSS, weather, or another event
2. Homey sends text or JSON to the configured MQTT topic
3. The Cosmic Unicorn shows the messages in order

This is especially useful for:

- RSS headlines
- weather
- finance/market updates
- reminders
- manual messages

## Operating Model

This project is intentionally simple on the Pico side:

- networking
- MQTT
- BMP download
- scrolling
- small animation playback

All polished text presentation lives in `banner`.

That keeps the Pico small, robust, and easy to use as a dedicated information display.

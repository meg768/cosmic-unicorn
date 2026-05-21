# cosmic-unicorn

A MicroPython project for a Pimoroni Cosmic Unicorn with Pico W.

This version uses:

- Wi-Fi for networking
- MQTT for incoming messages
- [banner.egelberg.se](http://banner.egelberg.se) to render text as BMP
- a local queue on the Pico so multiple messages are shown in order

## Idea

The Cosmic Unicorn does not generate text graphics on its own.

Instead, it works like this:

1. The Pico connects to Wi-Fi
2. The Pico connects to MQTT
3. A message arrives on the `cosmic-unicorn` topic
4. The Pico builds a URL to `banner.egelberg.se`
5. `banner` returns a 24-bit BMP
6. The Pico downloads the BMP and scrolls it across the display
7. The next MQTT message waits in queue until the current banner is finished

This lets typography, emojis, colors, and layout be handled server-side, while the Pico only needs to display the image.

## Files

The main files used in this project are:

- [main.py](/Users/magnus/Documents/GitHub/cosmic-unicorn/main.py)
- [wifi.py](/Users/magnus/Documents/GitHub/cosmic-unicorn/wifi.py)
- [config.example.py](/Users/magnus/Documents/GitHub/cosmic-unicorn/config.example.py)
- [`umqtt/`](/Users/magnus/Documents/GitHub/cosmic-unicorn/umqtt)

On the Pico itself you should have:

- `main.py`
- `wifi.py`
- `config.py`
- `umqtt/simple.py`
- `umqtt/__init__.py`
- `cufs/*.cuf` for MQTT-triggered animations, optional
- `animations/gif.py` for converted GIF/CUF animations, optional
- `animations/matrix.py` for the generated Matrix animation, optional

`display.bmp` is created and updated on the Pico at runtime and does not need to exist in the repository beforehand.

## Configuration

### `config.py`

Create a local `config.py` based on [config.example.py](/Users/magnus/Documents/GitHub/cosmic-unicorn/config.example.py).

`config.py` is ignored in [`.gitignore`](/Users/magnus/Documents/GitHub/cosmic-unicorn/.gitignore) and should not be committed.

Example:

```python
WIFI_SSID = "your-wifi-name"
WIFI_PASSWORD = "your-wifi-password"
COSMIC_UNICORN_MODEL = "Pico W"
MQTT_HOST = "server.example.com"
MQTT_PORT = 1883
MQTT_TOPIC = "cosmic-unicorn"
MQTT_USERNAME = "your-mqtt-username"
MQTT_PASSWORD = "your-mqtt-password"

MQTT_RECONNECT_MS = 5000
MQTT_PING_MS = 25000

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
```

These values are used to build the `banner` URL.

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

Animation example:

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
- `name`: optional; either `"matrix"` or the name of a `.cuf` file in `cufs/` without the `.cuf` extension
- `duration`: duration in seconds, default `60`

If `name` is omitted, a random available animation is chosen:

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

- the current banner is not interrupted
- the next banner waits its turn
- messages are shown in order

This is important for Homey flows where several RSS or status messages may arrive almost at the same time.

## Animations

Animations are triggered by MQTT JSON messages with `type: "animation"`.

The animation behavior is:

- the display stays black when the MQTT queue is empty
- animation messages are queued in the same queue as text messages
- `matrix` plays the generated Matrix animation from `animations/matrix.py`
- other names play converted GIF/CUF animations from `cufs/`
- CUF animations repeat until the requested duration has passed
- the current animation loop is always allowed to finish
- MQTT is still polled while animations play
- queued text messages wait until the current animation window is done

GIF files in `gifs/` can be converted to compressed CUF files with:

```bash
python3 tools/gif_to_cuf.py gifs cufs
```

## Banner Service

The Pico always fetches plain `http://` images from:

- [banner.egelberg.se](http://banner.egelberg.se)

`main.py` builds URLs roughly like this:

```text
http://banner.egelberg.se/?text=Hello&height=32&font=impact&color=gold&format=bmp
```

This means all text layout happens outside the Pico.

## Startup Behavior

If MQTT is configured, the display starts up and waits for incoming messages.

This means:

- no default banner is downloaded from the network at boot
- the screen may remain empty until the first MQTT message arrives

If you want different boot behavior, that needs to be added in `main.py`.

## Limitations

- The Pico only supports `http://` in this code, not `https://`
- if `banner` returns an invalid or too-large PNG, nothing new will be shown
- some very long texts may become too large for the Pico's PNG handling
- retained MQTT messages are not a great fit here; normal non-retained messages work best

## Thonny

Typical Thonny workflow:

1. Connect to the Pico
2. Make sure these files exist on `Raspberry Pi Pico`:
   `main.py`, `wifi.py`, `config.py`, `umqtt/`
3. Run `main.py`
4. Look in the `Shell` for:

```text
WiFi connected
MQTT connected: cosmic-unicorn
```

When messages arrive, you should see something like:

```text
MQTT message: Hello world (queue: 1)
Downloading: Hello world
Image updated
```

## Homey

This project works well with Homey flows.

Typical setup:

1. Homey triggers on RSS, weather, or another event
2. Homey sends text or JSON to the MQTT topic `cosmic-unicorn`
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
- PNG download
- scrolling

All polished presentation lives in `banner`.

That keeps the Pico small, robust, and easy to use as a dedicated information display.

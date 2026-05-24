# Project Context

This repo contains the MicroPython code and hardware/casing files for the Pimoroni Cosmic Unicorn displays.

## Current Direction

The Pico code is now intentionally thin:

- It connects to Wi-Fi and MQTT.
- Text messages are sent to `cosmic-unicorn.egelberg.se` and downloaded as 24-bit BMP.
- Animation messages download one CUF file from `cosmic-unicorn.egelberg.se` when needed.
- The Pico stores only one temporary animation file, `animation.cuf`, during playback.
- Local CUF animation libraries are no longer uploaded to the Pico.

This was done mainly to make Pico W useful again by avoiding flash pressure from local CUF files.

## Runtime Flow

Text:

1. MQTT receives plain text or JSON with `type: "text"`.
2. `main.py` builds a request to `BANNER_BASE_URL`.
3. The service returns BMP.
4. The Pico saves it as `display.bmp` and scrolls it.

Animation:

1. MQTT receives JSON with `type: "animation"`.
2. If `name` is `"matrix"`, the local Matrix animation runs.
3. Otherwise the Pico requests `/animation?format=cuf`.
4. If `name` is present, it is included as `/animation?name=<name>&format=cuf`.
5. If `name` is omitted, the server chooses a random animation.
6. The Pico saves the download as `animation.cuf`, plays it, then deletes it.

## Important URLs

Default service base URL:

```python
BANNER_BASE_URL = "http://cosmic-unicorn.egelberg.se/"
```

Browser GIF preview:

```text
http://cosmic-unicorn.egelberg.se/animation?name=tree
```

Pico CUF download:

```text
http://cosmic-unicorn.egelberg.se/animation?name=tree&format=cuf
```

Random CUF download:

```text
http://cosmic-unicorn.egelberg.se/animation?format=cuf
```

## Pico Files

Files under `pico/` are uploaded to the root of the Pico.

`pico/config.py` is local configuration and should not be committed. It contains Wi-Fi and MQTT secrets.

`pico/config.example.py` is the tracked template.

## Sync

Use:

```bash
tools/sync-pico.sh --reset
```

The sync script:

- uploads `pico/`
- includes `pico/config.py` if present
- excludes CUF files
- removes old `animations/gif/cufs/`, `animation.cuf`, and `animation.new.cuf` from the Pico if they exist

Useful dry run:

```bash
tools/sync-pico.sh --dry-run
```

## Current Architecture Notes

- Same Pico code should run on Pico W and Pico 2 W, with only `config.py` differing per device.
- Scroll delay is selected from `COSMIC_UNICORN_MODEL` in config.
- MQTT topics are configured per display, for example `cosmic-unicorn/one`, `/two`, `/three`.
- MQTT is still polled while animations play.
- Current animation loop is allowed to finish before the next queued message.
- Pico W stability is the key thing to test after moving animations server-side.

## Related Repo

The server-side renderer is:

```text
/Users/magnus/Documents/GitHub/cosmic-unicorn-service
```

It serves text as PNG/BMP, GIF previews for browsers, and CUF files for the Pico.

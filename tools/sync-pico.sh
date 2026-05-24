#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PICO_DIR="$ROOT_DIR/pico"
CONNECT="auto"
DRY_RUN=0
INCLUDE_CONFIG=1
INCLUDE_CUFS=1
SOFT_RESET=0
SHOW_TREE=0

usage() {
  cat <<'EOF'
Usage: tools/sync-pico.sh [options]

Uploads the contents of pico/ to the root of the connected MicroPython device.

Options:
  --connect NAME   mpremote connection name or serial port. Default: auto
  --dry-run        Show what would be uploaded, but do not upload
  --no-config      Do not upload pico/config.py
  --no-cufs        Do not upload converted CUF animation files
  --reset          Soft reset the Pico after upload
  --tree           Show the Pico filesystem tree after upload
  -h, --help       Show this help

Examples:
  tools/sync-pico.sh
  tools/sync-pico.sh --dry-run
  tools/sync-pico.sh --connect /dev/cu.usbmodem1101 --reset
  tools/sync-pico.sh --no-cufs
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --connect)
      CONNECT="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --no-config)
      INCLUDE_CONFIG=0
      shift
      ;;
    --no-cufs)
      INCLUDE_CUFS=0
      shift
      ;;
    --reset)
      SOFT_RESET=1
      shift
      ;;
    --tree)
      SHOW_TREE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! python3 -m mpremote --help >/dev/null 2>&1; then
  echo "mpremote is not installed. Install it with: python3 -m pip install mpremote" >&2
  exit 1
fi

if [ ! -d "$PICO_DIR" ]; then
  echo "Missing pico directory: $PICO_DIR" >&2
  exit 1
fi

STAGING_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$STAGING_DIR"
}
trap cleanup EXIT

RSYNC_EXCLUDES=(
  "--exclude=.DS_Store"
  "--exclude=__pycache__/"
  "--exclude=*.pyc"
  "--exclude=.micropico"
  "--exclude=.vscode/"
  "--exclude=config.example.py"
)

if [ "$INCLUDE_CONFIG" -eq 0 ]; then
  RSYNC_EXCLUDES+=("--exclude=config.py")
fi

if [ "$INCLUDE_CUFS" -eq 0 ]; then
  RSYNC_EXCLUDES+=("--exclude=animations/gif/cufs/")
fi

rsync -a "${RSYNC_EXCLUDES[@]}" "$PICO_DIR/" "$STAGING_DIR/pico/"

if [ "$INCLUDE_CONFIG" -eq 1 ] && [ ! -f "$PICO_DIR/config.py" ]; then
  echo "Warning: pico/config.py does not exist, so no device config will be uploaded." >&2
fi

echo "Files prepared for upload:"
(cd "$STAGING_DIR/pico" && find . -type f | sed 's#^\./##' | sort)

if [ "$DRY_RUN" -eq 1 ]; then
  echo
  echo "Dry run only. Nothing uploaded."
  exit 0
fi

echo
echo "Uploading pico/ to device root using mpremote connect $CONNECT ..."
UPLOAD_PATHS=("$STAGING_DIR/pico"/*)
python3 -m mpremote connect "$CONNECT" fs cp -r -f "${UPLOAD_PATHS[@]}" :

if [ "$SHOW_TREE" -eq 1 ]; then
  echo
  python3 -m mpremote connect "$CONNECT" fs tree :
fi

if [ "$SOFT_RESET" -eq 1 ]; then
  echo
  echo "Soft resetting device ..."
  python3 -m mpremote connect "$CONNECT" soft-reset
fi

echo "Done."

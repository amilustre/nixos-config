{ pkgs, lib, config, ... }:

let
  sofleFlash = pkgs.writeShellScriptBin "sofle-flash" ''
    set -euo pipefail

    # Accept firmware path as argument (defaults to ./sofle.uf2)
    UF2="''${1:-./sofle.uf2}"

    if [ ! -f "$UF2" ]; then
      echo "❌ Firmware file not found: $UF2"
      echo "   Usage: sofle-flash [path/to/firmware.uf2]"
      echo "   (defaults to ./sofle.uf2 in current directory)"
      exit 1
    fi

    NICENANO=""
    TIMEOUT=30
    ELAPSED=0

    echo "=== Sofle Flasher ==="
    echo "Firmware: $UF2"
    echo "1. Put keyboard in bootloader mode (double-tap reset)"
    echo ""
    for i in 10 9 8 7 6 5 4 3 2 1; do
      printf "\rStarting in %2ds... (double-tap reset now)      " "$i"
      sleep 1
    done
    echo ""
    echo "Looking for NICENANO drive..."
    while [ -z "$NICENANO" ] && [ "$ELAPSED" -lt "$TIMEOUT" ]; do
      printf "\rWaiting for NICENANO drive... (double-tap reset) [%2ds/%ds]" "$ELAPSED" "$TIMEOUT"

      # Try common automount paths first
      for candidate in /run/media/*/NICENANO /media/*/NICENANO; do
        if [ -d "$candidate" ]; then
          NICENANO="$candidate"
          break
        fi
      done

      # Try udisksctl to mount the NICENANO volume if available
      if [ -z "$NICENANO" ] && command -v udisksctl >/dev/null 2>&1; then
        NICENANO_DEV=$(lsblk -o NAME,LABEL -nr 2>/dev/null | awk '/^[a-z]/ && $2 == "NICENANO" {print "/dev/" $1; exit}')
        if [ -n "$NICENANO_DEV" ]; then
          udisksctl mount -b "$NICENANO_DEV" 2>/dev/null || true
        fi
        # Recheck after mount attempt
        for candidate in /run/media/*/NICENANO /media/*/NICENANO; do
          if [ -d "$candidate" ]; then
            NICENANO="$candidate"
            break
          fi
        done
      fi

      # Try to find it anywhere on the filesystem
      if [ -z "$NICENANO" ]; then
        FOUND=$(find / -maxdepth 4 -name NICENANO -type d 2>/dev/null | head -1)
        if [ -n "$FOUND" ]; then
          NICENANO="$FOUND"
        fi
      fi

      if [ -z "$NICENANO" ]; then
        sleep 2
        ELAPSED=$((ELAPSED + 2))
      fi
    done

    echo ""
    echo ""

    if [ -z "$NICENANO" ]; then
      echo "❌ Timed out after 30s — NICENANO drive not found."
      echo "   Available disks:"
      lsblk -o NAME,LABEL,SIZE,TYPE,MOUNTPOINT
      echo ""
      echo "If NICENANO does not appear above, double-tap the reset button on your keyboard."
      echo "If it appears but has no mountpoint, mount it manually:"
      echo "  sudo mount /dev/sdX /mnt    # (replace sdX with the right device)"
      exit 1
    fi

    echo "3. Found NICENANO at: $NICENANO"
    echo "   Copying $UF2 ..."
    cp "$UF2" "$NICENANO/"
    echo "✅ Flashed! Keyboard will restart automatically."
  '';
in {
  environment.systemPackages = [ sofleFlash ];

  services.gvfs.enable = true;

  # ESP32 via USB serial may appear as /dev/ttyACM0 (not /dev/ttyUSB0).
  # Check available ports with: ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
  services.udev.packages = [ (pkgs.writeTextDir "etc/udev/rules.d/99-nicenano.rules" ''
    # Nice!Nano in bootloader mode (Adafruit UF2)
    SUBSYSTEM=="usb", ATTRS{idVendor}=="239a", ATTRS{idProduct}=="0029", MODE="0666", GROUP="dialout"
    # Nice!Nano v2 in bootloader mode
    SUBSYSTEM=="usb", ATTRS{idVendor}=="239a", ATTRS{idProduct}=="012f", MODE="0666", GROUP="dialout"
  '') ];
}

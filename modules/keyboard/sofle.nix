{ pkgs, lib, config, ... }:

let
  sofleFlash = pkgs.writeShellScriptBin "sofle-flash" ''
    set -euo pipefail

    NICENANO=""
    TIMEOUT=30
    ELAPSED=0

    echo "=== Sofle Flasher ==="
    echo "1. Put keyboard in bootloader mode (double-tap reset)"
    echo ""
    sleep 3  # Give user time to reach the keyboard
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
    echo "   Copying firmware..."
    if [ -f ./sofle.uf2 ]; then
      cp ./sofle.uf2 "$NICENANO/"
      echo "✅ Flashed! Keyboard will restart automatically."
    else
      echo "❌ No sofle.uf2 found in current directory"
      exit 1
    fi
  '';
in {
  environment.systemPackages = [ sofleFlash ];

  # gvfs + udisks2 handle automounting removable media on desktop environments.
  # Enable this if you're on NixOS and NICENANO does not automount:
  # services.gvfs.enable = true;

  services.udev.packages = [ (pkgs.writeTextDir "etc/udev/rules.d/99-nicenano.rules" ''
    # Nice!Nano in bootloader mode (Adafruit UF2)
    SUBSYSTEM=="usb", ATTRS{idVendor}=="239a", ATTRS{idProduct}=="0029", MODE="0666", GROUP="dialout"
    # Nice!Nano v2 in bootloader mode
    SUBSYSTEM=="usb", ATTRS{idVendor}=="239a", ATTRS{idProduct}=="012f", MODE="0666", GROUP="dialout"
  '') ];
}

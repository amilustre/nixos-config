{ pkgs, lib, config, ... }:

let
  sofleFlash = pkgs.writeShellScriptBin "sofle-flash" ''
    echo "=== Sofle Flasher ==="
    echo "1. Put keyboard in bootloader mode (double-tap reset)"
    echo "2. Waiting for NICENANO drive..."
    while [ ! -d /run/media/*/NICENANO ] && [ ! -d /media/*/NICENANO ]; do
      sleep 1
    done
    echo "3. Copying firmware..."
    if [ -f ./sofle.uf2 ]; then
      cp ./sofle.uf2 /run/media/*/NICENANO/ 2>/dev/null || cp ./sofle.uf2 /media/*/NICENANO/ 2>/dev/null
      echo "✅ Flashed! Keyboard will restart automatically."
    else
      echo "❌ No sofle.uf2 found in current directory"
    fi
  '';
in {
  environment.systemPackages = [ sofleFlash ];

  services.udev.packages = [ (pkgs.writeTextDir "etc/udev/rules.d/99-nicenano.rules" ''
    # Nice!Nano in bootloader mode (Adafruit UF2)
    SUBSYSTEM=="usb", ATTRS{idVendor}=="239a", ATTRS{idProduct}=="0029", MODE="0666", GROUP="dialout"
    # Nice!Nano v2 in bootloader mode
    SUBSYSTEM=="usb", ATTRS{idVendor}=="239a", ATTRS{idProduct}=="012f", MODE="0666", GROUP="dialout"
  '') ];
}

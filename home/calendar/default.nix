{ pkgs, ... }:

# Pop-up de calendario (clic en el reloj de waybar) con los eventos de Google
# Calendar vía «dirección secreta en formato iCal» (solo lectura, sin OAuth).
# Las URLs viven en ~/.config/gcal-popup/calendars (secreto, fuera del repo).
let
  python = pkgs.python3.withPackages (ps: [
    ps.pygobject3
    ps.icalendar
    ps.recurring-ical-events
  ]);

  gcalPopup = pkgs.stdenv.mkDerivation {
    pname = "gcal-popup";
    version = "1.0";
    src = ./gcal-popup.py;
    dontUnpack = true;
    # wrapGAppsHook3 → GI_TYPELIB_PATH de gtk3 y gtk-layer-shell en el wrapper.
    nativeBuildInputs = [ pkgs.wrapGAppsHook3 pkgs.gobject-introspection ];
    buildInputs = [ python pkgs.gtk3 pkgs.gtk-layer-shell ];
    installPhase = ''
      install -Dm755 $src $out/bin/gcal-popup
    '';
  };
in
{
  home.packages = [ gcalPopup ];
}

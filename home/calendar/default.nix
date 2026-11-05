{ pkgs, ... }:

# Pop-up de calendario (clic en el reloj de waybar) con los eventos de Google
# Calendar que sirve HomeHub (/calendar, que ya tiene la cuenta conectada):
# sin OAuth ni secretos aquí. Límites de HomeHub en la cabecera de
# gcal-popup.py.
let
  python = pkgs.python3.withPackages (ps: [ ps.pygobject3 ]);

  gcalPopup = pkgs.stdenv.mkDerivation {
    pname = "gcal-popup";
    version = "2.0";
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

{ pkgs, ... }:

# Pop-up de calendario (clic en el reloj de waybar) con los eventos de Google
# Calendar vía API (solo lectura, OAuth): calendarios visibles, nombres y
# colores salen de Google. Cliente OAuth y token viven en ~/.config/gcal-popup
# (secretos, fuera del repo); ver la cabecera de gcal-popup.py.
let
  python = pkgs.python3.withPackages (ps: [
    ps.pygobject3
    ps.google-auth-oauthlib
    ps.requests
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

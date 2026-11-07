{ config, pkgs, ... }:

# Firefox con la extensión Vivagg (~/Proyectos/vivagg/extension) cargada en cada arranque.
# No hay firma de Mozilla: vivagg-loader.js (autoconfig) la instala como complemento temporal.
# Cambios en la extensión: basta con reiniciar Firefox (se lee del directorio del proyecto, no del store).
let
  extensionDir = "${config.home.homeDirectory}/Proyectos/vivagg/extension";
  loader = pkgs.writeText "vivagg-loader.js"
    (builtins.replaceStrings [ "@VIVAGG_EXTENSION_DIR@" ] [ extensionDir ] (builtins.readFile ./vivagg-loader.js));
in
{
  home.packages = [
    (pkgs.firefox.override { extraPrefsFiles = [ loader ]; })
  ];
}

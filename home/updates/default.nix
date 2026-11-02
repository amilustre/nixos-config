{ config, pkgs, lib, ... }:

# Alertas de actualizaciones: un timer compara los inputs del flake.lock con
# sus ramas en GitHub, evalúa qué paquetes cambiarían (kernel, NVIDIA, apps de
# sistema y de home-manager) y lo muestra en waybar (custom/updates) y con una
# notificación de dunst cuya acción abre update-apply en una terminal.
let
  flakeDir = "${config.home.homeDirectory}/nixos-config";

  # update-check se pasa por entorno (UPDATE_CHECK_BIN) para no crear un ciclo
  # entre las dos derivaciones.
  updateApply = pkgs.writeShellApplication {
    name = "update-apply";
    runtimeInputs = [ pkgs.git pkgs.jq pkgs.procps pkgs.coreutils ];
    text = builtins.readFile ./update-apply.sh;
  };

  updateCheck = pkgs.stdenvNoCC.mkDerivation {
    pname = "update-check";
    version = "1.0";
    src = ./update-check.py;
    dontUnpack = true;
    nativeBuildInputs = [ pkgs.makeWrapper ];
    buildInputs = [ pkgs.python3 ];
    installPhase = ''
      install -Dm755 $src $out/bin/update-check
    '';
    # nix/nixos-version/systemd-run/alacritty vienen del sistema (PATH heredado).
    postFixup = ''
      wrapProgram $out/bin/update-check \
        --prefix PATH : ${lib.makeBinPath [ pkgs.git pkgs.libnotify pkgs.procps ]} \
        --set UPDATE_CHECK_FLAKE ${flakeDir} \
        --set UPDATE_CHECK_BIN $out/bin/update-check \
        --set UPDATE_APPLY_BIN ${lib.getExe updateApply}
    '';
  };
in
{
  home.packages = [ updateCheck updateApply ];

  systemd.user.services.update-check = {
    Unit.Description = "Comprobar actualizaciones de NixOS (inputs del flake)";
    Service = {
      Type = "oneshot";
      ExecStart = "${updateCheck}/bin/update-check check";
      Nice = 10;
      # Sin red al arrancar sesión → reintenta en vez de esperar 6 h.
      Restart = "on-failure";
      RestartSec = "10min";
    };
  };

  systemd.user.timers.update-check = {
    Unit.Description = "Comprobar actualizaciones de NixOS cada 6 h";
    Timer = {
      OnStartupSec = "3min";
      OnUnitActiveSec = "6h";
    };
    Install.WantedBy = [ "timers.target" ];
  };
}

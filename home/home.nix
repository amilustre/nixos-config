{ config, pkgs, inputs, ... }:

let
  # Thunderbird en segundo plano: vive en el workspace especial "mail" de
  # Hyprland (Thunderbird 159 no tiene "minimizar a bandeja" en Linux y su
  # icono de bandeja no se puede colorear). El aviso lo da custom/mail:
  # dunst marca el flag al recibir la notificación de correo de Thunderbird
  # y se borra en cuanto se mira Thunderbird (enfocado o workspace visible).
  jq = "${pkgs.jq}/bin/jq";
  pkill = "${pkgs.procps}/bin/pkill";

  mailStatus = pkgs.writeShellScript "waybar-mail-status" ''
    flag="''${XDG_RUNTIME_DIR:-/tmp}/thunderbird-new-mail"
    if ! hyprctl clients -j | ${jq} -e 'any(.[]; .class == "thunderbird")' >/dev/null; then
      rm -f "$flag"
      echo '{"text":"","class":"off","tooltip":"Thunderbird cerrado (clic para abrir)"}'
      exit 0
    fi
    if [ -e "$flag" ] && {
      hyprctl activewindow -j | ${jq} -e '.class == "thunderbird"' >/dev/null ||
      hyprctl monitors -j | ${jq} -e 'any(.[]; .specialWorkspace.name == "special:mail")' >/dev/null
    }; then
      rm -f "$flag"
    fi
    if [ -e "$flag" ]; then
      echo '{"text":"","class":"unread","tooltip":"Correo nuevo"}'
    else
      echo '{"text":"","class":"read","tooltip":"Thunderbird"}'
    fi
  '';

  # Clic: muestra/oculta el workspace "mail"; si Thunderbird no está abierto
  # lo lanza ahí; si su ventana está en un workspace normal, la enfoca.
  mailClick = pkgs.writeShellScript "waybar-mail-click" ''
    ws=$(hyprctl clients -j | ${jq} -r '[.[] | select(.class == "thunderbird") | .workspace.name]
      | if index("special:mail") then "special:mail" else (.[0] // "") end')
    if [ -z "$ws" ]; then
      hyprctl dispatch "hl.dsp.exec_cmd('thunderbird', { workspace = 'special:mail' })"
    elif [ "$ws" = "special:mail" ]; then
      hyprctl dispatch "hl.dsp.workspace.toggle_special('mail')"
    else
      hyprctl dispatch "hl.dsp.focus({ window = 'class:^(thunderbird)$' })"
    fi
    ${pkill} -RTMIN+9 waybar
  '';

  mailFlagSet = pkgs.writeShellScript "dunst-thunderbird-new-mail" ''
    touch "''${XDG_RUNTIME_DIR:-/tmp}/thunderbird-new-mail"
    ${pkill} -RTMIN+9 waybar
  '';
in
{
  imports = [
    ./hyprland/settings.nix
    ./updates
    ./calendar
    ./firefox
    ../modules/programs/git.nix
  ];

  home.username = "alexis";
  home.homeDirectory = "/home/alexis";
  # Claude Code: vía paquete de nixpkgs (claude-code en systemPackages) —
  # TANTO el instalador nativo (claude.ai/install.sh) COMO el paquete npm
  # traen binario dinámico genérico → NixOS los rechaza (stub-ld).
  home.sessionPath = [ "$HOME/.npm-global/bin" ];

  home.packages = with pkgs; [
    keepassxc
    pkgs.nerd-fonts.jetbrains-mono
  ];

  programs.waybar = {
    enable = true;
    # Write JSON config manually to avoid type issues
    settings = {};
    style = ''
      * { border: none; font-family: "JetBrainsMono Nerd Font"; font-size: 14px; }
      window#waybar { background: rgba(10,10,12,0.85); color: #e4e4e7; border-bottom: 1px solid #33333a; }
      #workspaces button { padding: 0 6px; color: #58585f; }
      #workspaces button.active { color: #ffffff; border-bottom: 2px solid #d71921; }
      #workspaces button.focused { color: #ffffff; }
      #workspaces button.urgent { color: #ff4444; }
      #clock, #pulseaudio, #network, #tray, #custom-updates, #custom-screenshot { padding: 0 10px; }
      #clock { color: #d71921; font-weight: bold; }
      #pulseaudio, #network, #custom-screenshot { color: #c8c8cc; }
      #custom-screenshot:hover { color: #d71921; }
      #custom-mail { padding: 0 10px 0 2px; color: #c8c8cc; }
      #custom-mail.unread { color: #d71921; }
      #custom-mail.off { color: #58585f; }
      #custom-updates.updates, #custom-updates.pending { color: #d71921; }
      #custom-updates.reboot { color: #e3b341; }
      #custom-updates.error { color: #58585f; }
      #tray { padding-right: 6px; }
    '';
  };

  home.file.".config/waybar/config.jsonc".text = builtins.toJSON {
    layer = "top";
    position = "top";
    height = 30;
    modules-left = [ "hyprland/workspaces" ];
    modules-center = [ "hyprland/window" ];
    modules-right = [ "custom/updates" "custom/screenshot" "pulseaudio" "network" "clock" "tray" "custom/mail" ];
    "hyprland/workspaces" = {
      disable-scroll = true;
      all-outputs = true;
      format = "{name}";
    };
    # Clic: pop-up de calendario con Google Calendar (home/calendar).
    clock = {
      format = "{:%H:%M}";
      tooltip = false;
      on-click = "gcal-popup";
    };
    # Alertas de actualizaciones (home/updates); oculto si todo está al día.
    "custom/updates" = {
      exec = "update-check waybar";
      return-type = "json";
      interval = 300;
      signal = 8; # update-check / update-apply envían SIGRTMIN+8 al cambiar
      on-click = "update-check apply";
      on-click-right = "systemctl --user start --no-block update-check.service";
    };
    # Thunderbird junto a la bandeja: color de resalto con correo nuevo.
    "custom/mail" = {
      exec = "${mailStatus}";
      return-type = "json";
      interval = 3;
      signal = 9; # mailClick / dunst envían SIGRTMIN+9
      on-click = "${mailClick}";
    };
    # Clic: captura con selección/edición; clic derecho: pantalla completa.
    "custom/screenshot" = {
      format = "";
      tooltip-format = "Captura (clic: selección · derecho: pantalla completa)";
      on-click = "flameshot gui";
      on-click-right = "flameshot full";
    };
  };

  # Dunst por defecto: clic izquierdo = cerrar → las peticiones de blueman
  # ("Pairing request for…", acciones Confirm/Deny) caducaban sin respuesta
  # y el dispositivo BT quedaba conectado sin cifrar (sin input).
  # Clic izquierdo abre el menú de acciones (rofi) y luego cierra.
  home.file.".config/dunst/dunstrc".text = ''
    [global]
    mouse_left_click = do_action, close_current
    mouse_middle_click = close_current
    mouse_right_click = close_all
    dmenu = ${pkgs.rofi}/bin/rofi -dmenu -p dunst

    # Correo nuevo de Thunderbird → icono de waybar en color de resalto.
    [thunderbird-new-mail]
    appname = Thunderbird
    script = ${mailFlagSet}
  '';

  programs.home-manager.enable = true;


  programs.zsh = {
    enable = true;
    enableCompletion = true;
    oh-my-zsh.enable = true;
    shellAliases = {
      rebuild = "sudo nixos-rebuild switch --flake ~/nixos-config#desktop";
    };
  };

  home.stateVersion = "24.11";
}

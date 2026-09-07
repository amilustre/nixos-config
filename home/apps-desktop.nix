{ config, pkgs, ... }:

{
  home.packages = with pkgs; [
    alacritty
    chromium
    discord
    obsidian
    rofi
    telegram-desktop
    thunar
    thunar-volman
    wlogout
    pkgs.hyprlock
    unzip
    wget
    grim
    swww
  ];

  programs.hyprlock = {
    enable = true;
    settings = {
      general = {
        no_fade_in = false;
        no_fade_out = false;
        ignore_empty_input = true;
        hide_cursor = true;
        grace = 5;
      };
      background = [{
        path = "~/Pictures/wallpapers/nothing-dots.png";
        blur_passes = 3;
        blur_size = 8;
        brightness = 0.5;
      }];
      input-field = [{
        monitor = "";
        size = "300, 50";
        outline_thickness = 2;
        dots_size = 0.2;
        dots_center = true;
        outer_color = "rgba(d71921ee)";
        inner_color = "rgba(10, 10, 12ee)";
        font_color = "rgba(e4e4e7ee)";
        fade_on_empty = true;
        placeholder_text = "<i>Password...</i>";
        hide_input = false;
        position = "0, -120";
        halign = "center";
        valign = "center";
      }];
      label = [
        {
          monitor = "";
          text = "<b>Locked</b>";
          font_size = 24;
          color = "rgba(e4e4e7ee)";
          position = "0, -60";
          halign = "center";
          valign = "center";
        }
        {
          monitor = "";
          text = "cmd[update:1000] echo \"$(date '+%H:%M')\"";
          font_size = 64;
          color = "rgba(e4e4e7ee)";
          position = "0, 60";
          halign = "center";
          valign = "center";
        }
      ];
    };
  };

  programs.wlogout = {
    enable = true;
    layout = [
      {
        label = "lock";
        action = "loginctl lock-session";
        text = " Lock";
        keybind = "l";
      }
      {
        label = "logout";
        action = "hyprctl dispatch exit";
        text = " Logout";
        keybind = "e";
      }
      {
        label = "reboot";
        action = "systemctl reboot";
        text = " Reboot";
        keybind = "r";
      }
      {
        label = "shutdown";
        action = "systemctl poweroff";
        text = " Shutdown";
        keybind = "s";
      }
    ];
    style = ''
      * {
        font-family: "JetBrainsMono Nerd Font", "Noto Sans", sans-serif;
      }
      window {
        background: rgba(10, 10, 12, 0.88);
      }
      button {
        margin: 10px;
        padding: 15px;
        border: 2px solid #33333a;
        background: rgba(10, 10, 12, 0.6);
        color: #e4e4e7;
        font-size: 18px;
      }
      button:hover {
        background: rgba(215, 25, 33, 0.28);
        border-color: #d71921;
      }
    '';
  };

  # Flameshot (Wayland): usa grim como adaptador de captura (wiki NixOS).
  # `enable` instala flameshot + configura ~/.config/flameshot/flameshot.ini.
  services.flameshot = {
    enable = true;
    settings = {
      General = {
        useGrimAdapter = true;       # Wayland: captura vía grim
        disabledGrimWarning = true;
        disabledTrayIcon = true;
        showStartupLaunchMessage = false;
        saveAsFileExtension = ".png";
        savePath = "/home/alexis/Pictures/screenshots";
      };
    };
  };

  # Asegura que el directorio de capturas exista (flameshot no lo crea).
  home.file."Pictures/screenshots/.keep" = { text = ""; };

  # Wallpaper Nothing OS (dot-matrix) — del repo 0xbbuddha/dotfiles_nothing_os.
  # 1920x1080; swww hace crop/cover en los 2560x1080.
  home.file."Pictures/wallpapers/nothing-dots.png" = {
    source = pkgs.fetchurl {
      url = "https://raw.githubusercontent.com/0xbbuddha/dotfiles_nothing_os/main/hypr/wallpapers/nothing-dots-16-9.png";
      sha256 = "sha256-Ja8Qv1eMCUnCr+VAEWNt0A3vTq/m2qmxpJlCdq1j7r8=";
    };
  };
}

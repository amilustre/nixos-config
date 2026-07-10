{ config, pkgs, inputs, ... }:

{
  imports = [
    ./hyprland/settings.nix
    ../modules/programs/git.nix
  ];

  home.username = "alexis";
  home.homeDirectory = "/home/alexis";

  home.packages = with pkgs; [
    alacritty
    firefox
    obsidian
    rofi-wayland
    telegram-desktop
    wlogout
    pkgs.hyprlock
    pkgs.nerd-fonts.jetbrains-mono
  ];

  programs.home-manager.enable = true;

  programs.waybar = {
    enable = true;
    settings = [{
      name = "main";
      jsonc = ./hyprland/waybar/config.jsonc;
    }];
    style = ./hyprland/waybar/style.css;
  };

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
        path = "~/Pictures/wallpapers/wallpaper.jpg";
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
        outer_color = "rgba(89b4faee)";
        inner_color = "rgba(30, 30, 46ee)";
        font_color = "rgba(cdd6f4ee)";
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
          color = "rgba(cdd6f4ee)";
          position = "0, -60";
          halign = "center";
          valign = "center";
        }
        {
          monitor = "";
          text = "cmd[update:1000] echo \"$(date '+%H:%M')\"";
          font_size = 64;
          color = "rgba(cdd6f4ee)";
          position = "0, 60";
          halign = "center";
          valign = "center";
        }
      ];
    };
  };

  programs.wlogout = {
    enable = true;
    # Basic layout - can be customized later
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
        background: rgba(30, 30, 46, 0.85);
      }
      button {
        margin: 10px;
        padding: 15px;
        border: 2px solid #585b70;
        background: rgba(30, 30, 46, 0.6);
        color: #cdd6f4;
        font-size: 18px;
      }
      button:hover {
        background: rgba(69, 71, 90, 0.8);
        border-color: #89b4fa;
      }
    '';
  };

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

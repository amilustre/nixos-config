{ config, pkgs, inputs, ... }:

{
  imports = [
    ./hyprland/settings.nix
    ../modules/programs/git.nix
  ];

  home.username = "alexis";
  home.homeDirectory = "/home/alexis";

  home.packages = with pkgs; [
    firefox
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
      #clock, #pulseaudio, #network, #tray { padding: 0 10px; }
      #clock { color: #d71921; font-weight: bold; }
      #pulseaudio, #network { color: #c8c8cc; }
      #tray { padding-right: 6px; }
    '';
  };

  home.file.".config/waybar/config.jsonc".text = builtins.toJSON {
    layer = "top";
    position = "top";
    height = 30;
    modules-left = [ "hyprland/workspaces" ];
    modules-center = [ "hyprland/window" ];
    modules-right = [ "pulseaudio" "network" "clock" "tray" ];
    "hyprland/workspaces" = {
      disable-scroll = true;
      all-outputs = true;
      format = "{name}";
    };
    clock = {
      format = "{:%H:%M}";
    };
  };

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

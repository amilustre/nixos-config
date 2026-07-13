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
      window#waybar { background: rgba(30,30,46,0.85); color: #cdd6f4; border-bottom: 2px solid #cba6f7; }
      #workspaces button { padding: 0 6px; color: #585b70; }
      #workspaces button.active { color: #cba6f7; }
      #workspaces button.focused { color: #cba6f7; }
      #workspaces button.urgent { color: #f38ba8; }
      #clock, #pulseaudio, #network, #tray { padding: 0 10px; }
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

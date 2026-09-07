{ config, pkgs, inputs, ... }:

{
  programs.hyprland = {
    enable = true;
    xwayland.enable = true;
  };

  services.xserver.enable = true;
  services.displayManager.sddm.enable = true;
  services.displayManager.defaultSession = "hyprland";

  environment.systemPackages = with pkgs; [
    waybar
    dunst
    wofi
    wl-clipboard
    pavucontrol
    brightnessctl
    networkmanagerapplet
    alacritty
    awww # fondo de escritorio (Nothing dot-matrix); en 26.05 swww se renombró a awww
  ];
}

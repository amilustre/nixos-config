{ config, pkgs, ... }:

{
  users.users.alexis = {
    isNormalUser = true;
    extraGroups = [ "wheel" "networkmanager" "video" ];
    shell = pkgs.zsh;
    openssh.authorizedKeys.keys = [
      "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHeKkigTlx2X/RVfjkM9y0J13DrVsUCREi6Tm9+b/x94 openclaw@pulpi"
    ];
  };
}

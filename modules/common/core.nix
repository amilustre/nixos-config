{ config, pkgs, ... }:

{
  nix.settings = {
    experimental-features = [ "nix-command" "flakes" ];
    auto-optimise-store = true;
    cores = 0;
    max-jobs = "auto";
  };

  services.openssh.enable = true;
  services.ntp.enable = true;

  environment.systemPackages = with pkgs; [
    neovim git htop wget curl
  ];

  networking.firewall.enable = true;
}

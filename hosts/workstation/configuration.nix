{ config, pkgs, inputs, ... }:

{
  imports = [
    ../../modules/common/core.nix
    ../../modules/common/users.nix
    # ../../modules/desktop/nvidia.nix   # Solo si tiene NVIDIA
    ../../modules/desktop/hyprland.nix
  ];

  networking.hostName = "workstation-pc";

  # Ajusta según el hardware de tu trabajo
  boot.initrd.availableKernelModules = [ "nvme" "xhci_pci" "ahci" "usb_storage" "sd_mod" ];
  boot.kernelModules = [ "kvm-amd" ];  # o intel

  users.users.alexis = {
    isNormalUser = true;
    extraGroups = [ "wheel" "networkmanager" "video" ];
    shell = pkgs.zsh;
  };

  system.stateVersion = "24.11";
}

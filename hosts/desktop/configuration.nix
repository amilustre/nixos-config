{ config, pkgs, inputs, ... }:

{
  imports = [
    ../../modules/common/core.nix
    ../../modules/common/users.nix
    ../../modules/desktop/nvidia.nix
    ../../modules/desktop/kde-temporary.nix
    ../../modules/desktop/hyprland.nix
  ];

  # ===== SISTEMA DE ARCHIVOS (CORREGIDO) =====
  fileSystems = {
    "/" = {
      device = "/dev/nvme0n1p2";
      fsType = "ext4";
      options = [ "defaults" ];
    };
    "/boot" = {
      device = "/dev/nvme0n1p1";
      fsType = "vfat";
    };
  };

  # ===== SWAP (CORREGIDO) =====
  swapDevices = [ { device = "/dev/nvme0n1p3"; } ];

  # ===== BOOTLOADER =====
  boot.loader = {
    systemd-boot.enable = true;
    efi.canTouchEfiVariables = true;
  };

  boot.kernelPackages = pkgs.linuxPackages_latest;

  # ===== HARDWARE =====
  boot.initrd.availableKernelModules = [ "nvme" "xhci_pci" "ahci" "usb_storage" "sd_mod" ];
  boot.initrd.kernelModules = [ "nvidia" "nvidia_modeset" "nvidia_uvm" "nvidia_drm" ];
  boot.kernelModules = [ "kvm-intel" ];
  boot.extraModulePackages = [ ];

  hardware.cpu.intel.updateMicrocode = true;

  # ===== RED =====
  networking.hostName = "nixtopus";
  networking.networkmanager.enable = true;

  # ===== USUARIO =====
  programs.zsh.enable = true;
  users.users.alexis = {
    isNormalUser = true;
    extraGroups = [ "wheel" "networkmanager" "video" ];
    shell = pkgs.zsh;
  };

  system.stateVersion = "24.11";
}

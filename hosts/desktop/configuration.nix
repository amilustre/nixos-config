{ config, pkgs, inputs, ... }:

{
  imports = [
    ../../modules/common/core.nix
    ../../modules/common/users.nix
    #../../modules/desktop/nvidia.nix
    ../../modules/desktop/hyprland.nix
  ];
  
  services.xserver.videoDrivers = [ "nvidia" ];
  hardware.nvidia = {
    modesetting.enable = true;
    powerManagement.enable = false;
    open = false;
    prime = {
      sync.enable = true;
      intelBusId = "PCI:0:2:0";
      nvidiaBusId = "PCI:1:0:0";
    };
  };
  hardware.graphics.enable = true;
  boot.kernelParams = [ "nvidia-drm.modeset=1" ];

  # ===== KEYBOARD LAYOUT (SPANISH) =====
  services.xserver.layout = "es";
  console.keyMap = "es";
  
  # ===== SISTEMA DE ARCHIVOS (CORREGIDO - BTRFS) =====
  fileSystems = {
    "/" = {
      device = "/dev/nvme0n1p2";
      fsType = "btrfs";
      options = [ "subvol=@" ];
    };
    "/home" = {
      device = "/dev/nvme0n1p2";
      fsType = "btrfs";
      options = [ "subvol=@home" ];
    };
    "/nix" = {
      device = "/dev/nvme0n1p2";
      fsType = "btrfs";
      options = [ "subvol=@nix" ];
    };
    "/var/log" = {
      device = "/dev/nvme0n1p2";
      fsType = "btrfs";
      options = [ "subvol=@log" ];
    };
    "/.snapshots" = {
      device = "/dev/nvme0n1p2";
      fsType = "btrfs";
      options = [ "subvol=@.snapshots" ];
    };
    "/boot" = {
      device = "/dev/nvme0n1p1";
      fsType = "vfat";
    };
  };

  boot.initrd.supportedFilesystems = [ "btrfs" ];

  # ===== SWAP (CORREGIDO) =====
  swapDevices = [ { device = "/dev/nvme0n1p3"; } ];

  # ===== BOOTLOADER =====
  boot.loader = {
    systemd-boot.enable = true;
    efi.canTouchEfiVariables = true;
  };

  boot.kernelPackages = pkgs.linuxPackages_7_1;
  
  nixpkgs.config.allowUnfree = true;

  # ===== HARDWARE =====
  boot.initrd.availableKernelModules = [ "nvme" "xhci_pci" "ahci" "usb_storage" "sd_mod" ];
  boot.initrd.kernelModules = [ "nvidia" "nvidia_modeset" "nvidia_uvm" "nvidia_drm" ];
  boot.kernelModules = [ "kvm-intel" ];
  boot.extraModulePackages = [ ];

  hardware.cpu.intel.updateMicrocode = true;

  # ===== BLUETOOTH =====
  hardware.bluetooth.enable = true;
  services.blueman.enable = true;

  # ===== RED =====
  networking.hostName = "nixtopus";
  networking.networkmanager.enable = true;

  # ===== USUARIO =====
  programs.zsh.enable = true;

  system.stateVersion = "26.05";
}

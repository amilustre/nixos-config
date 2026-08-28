{ config, pkgs, inputs, ... }:

{
  imports = [
    ../../modules/common/core.nix
    ../../modules/common/users.nix
    #../../modules/desktop/nvidia.nix
    ../../modules/desktop/hyprland.nix
    ../../modules/display/dashboard.nix
    ../../modules/keyboard/sofle.nix
  ];

  # Docker para el sandbox de trading-crypto (25-08-2026)
  virtualisation.docker.enable = true;

  time.timeZone = "Europe/Madrid";
  
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
  # ===== STEAM (2026-08-10) =====
  # enable32Bit obligatorio para juegos 32-bit con drivers NVIDIA
  programs.steam.enable = true;
  hardware.graphics.enable32Bit = true;
  boot.kernelParams = [ "nvidia-drm.modeset=1" "root=/dev/nvme0n1p2" ];

  hardware.enableRedistributableFirmware = true;

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
  boot.initrd.availableKernelModules = [ "nvme" "btrfs" "xhci_pci" "ahci" "usbhid" "sr_mod" ];
  boot.initrd.kernelModules = [ "nvme" "btrfs" ];
  boot.kernelModules = [ "kvm-intel" "iwlwifi" "btintel" "bluetooth" "i2c-dev" "i2c-i801" ];
  boot.extraModulePackages = [ ];

  hardware.cpu.intel.updateMicrocode = true;

  # ===== PLATFORMIO / ESP32 =====
  services.udev.packages = with pkgs; [ platformio-core.udev openrgb ];
  environment.systemPackages = with pkgs; [ platformio openrgb ];

  # ===== LOGITECH HID++ (MX Master 3 por Bluetooth, LogiTune) =====
  services.udev.extraRules = ''
    SUBSYSTEM=="hidraw", ATTRS{idVendor}=="046d", MODE="0660", GROUP="input"
    # OpenRGB: acceso a TODOS los buses i2c (la regla oficial i2c-[0-99]* no cubre i2c-10+)
    SUBSYSTEM=="i2c-dev", MODE="0660", GROUP="i2c"
  '';

  # ===== BLUETOOTH =====
  hardware.bluetooth = {
    enable = true;
    powerOnBoot = true;
    settings = {
      General = {
        Enable = "Source,Sink,Media,Socket";
        Experimental = true;
      };
    };
  };
  services.blueman.enable = true;

  # ===== SYNCTHING =====
  services.syncthing = {
    enable = true;
    user = "alexis";
    dataDir = "/home/alexis/.local/share/syncthing";
    configDir = "/home/alexis/.config/syncthing";
  };

  # ===== RED =====
  networking.hostName = "nixtopus";
  networking.networkmanager.enable = true;

  # Dashboard trading-crypto (8090) accesible desde la LAN (móvil de Alexis)
  networking.firewall.allowedTCPPorts = [ 8090 ];

  # ===== USUARIO =====
  programs.zsh.enable = true;

  system.stateVersion = "26.05";
}

{ config, pkgs, ... }:

{
  hardware.nvidia = {
    modesetting.enable = true;
    powerManagement.enable = false;
    open = false;
    nvidiaSettings = true;
    package = config.boot.kernelPackages.nvidiaPackages.beta;
  };

  # ===== NUEVO NOMBRE PARA 26.05 =====
  hardware.graphics = {
    enable = true;
    enable32Bit = true;
  };

  boot.kernelParams = [ "nvidia-drm.modeset=1" ];

  environment.sessionVariables = {
    WLR_NO_HARDWARE_CURSORS = "1";
    NIXOS_OZONE_WL = "1";
    __GLX_VENDOR_LIBRARY_NAME = "nvidia";
    GBM_BACKEND = "nvidia-drm";
    WLR_DRM_NO_MODIFIERS = "1";
    LIBVA_DRIVER_NAME = "nvidia";
    __GL_THREADED_OPTIMIZATIONS = "1";
    __GL_YIELD = "USLEEP";
  };

  environment.systemPackages = with pkgs; [
    nvidia-vaapi-driver
  ];
}

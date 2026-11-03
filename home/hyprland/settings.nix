{ ... }:

{
  wayland.windowManager.hyprland = {
    enable = true;
    systemd.enable = true;
    # Hyprland 0.57 eliminó el formato hyprlang (.conf): solo lee hyprland.lua.
    # HM genera hyprland.lua (hooks de systemd) y añade nuestra config al final.
    configType = "lua";
    extraConfig = builtins.readFile ./hyprland.lua;
  };
}

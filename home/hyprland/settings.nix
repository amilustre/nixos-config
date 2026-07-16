{ config, pkgs, ... }:

{
  wayland.windowManager.hyprland = {
    enable = true;
    systemd.enable = true;
    configType = "hyprlang";
    settings = {
      monitor = [
        "DP-3, 2560x1080@144, 0x-1080, 1"
        "HDMI-A-5, 2560x1080@144, 0x0, 1"
      ];

      xwayland = {
        enabled = true;
      };

      workspace = [
        "1, monitor:HDMI-A-5"
        "2, monitor:HDMI-A-5"
        "3, monitor:HDMI-A-5"
        "4, monitor:HDMI-A-5"
        "5, monitor:HDMI-A-5"
        "6, monitor:DP-3"
        "7, monitor:DP-3"
        "8, monitor:DP-3"
        "9, monitor:DP-3"
      ];

      general = {
        gaps_in = 5;
        gaps_out = 10;
        border_size = 2;
        "col.active_border" = "rgba(33ccffee) rgba(00ff99ee) 45deg";
        "col.inactive_border" = "rgba(595959aa)";
        layout = "dwindle";
      };

      decoration = {
        rounding = 10;
        blur = {
          enabled = true;
          size = 3;
          passes = 1;
        };
        shadow = {
          enabled = true;
          range = 4;
        };
      };

      exec-once = [
        "waybar"  # home-manager deploys config to ~/.config/waybar/main.jsonc (auto-discovered)
        "dunst"
        "[workspace 2 silent] firefox"
        "[workspace 1 silent] alacritty"
      ];

      bind = [
        "$mainMod, Return, exec, alacritty"
        "$mainMod, Q, killactive,"
        "$mainMod, F, fullscreen,"
        "$mainMod, V, togglefloating,"
        "$mainMod, D, exec, rofi -show drun"        # Rofi launcher
        "$mainMod, Escape, exec, wlogout"            # Wlogout menu
        "$mainMod, L, exec, hyprlock"                # Hyprlock (was loginctl, changed per task)
        ", Print, exec, grim -g \"$(slurp)\" ~/Pictures/screenshots/$(date +%Y-%m-%d_%H-%M-%S).png"
        "$mainMod, Print, exec, grim ~/Pictures/screenshots/$(date +%Y-%m-%d_%H-%M-%S).png"
        "$mainMod, 1, workspace, 1"
        "$mainMod, 2, workspace, 2"
        "$mainMod, 3, workspace, 3"
        "$mainMod, 4, workspace, 4"
        "$mainMod, 5, workspace, 5"
        "$mainMod, 6, workspace, 6"
        "$mainMod, 7, workspace, 7"
        "$mainMod, 8, workspace, 8"
        "$mainMod, 9, workspace, 9"
        "$mainMod, 0, workspace, 10"

        "$mainMod SHIFT, 1, movetoworkspace, 1"
        "$mainMod SHIFT, 2, movetoworkspace, 2"
        "$mainMod SHIFT, 3, movetoworkspace, 3"
        "$mainMod SHIFT, 4, movetoworkspace, 4"
        "$mainMod SHIFT, 5, movetoworkspace, 5"
        "$mainMod SHIFT, 6, movetoworkspace, 6"
        "$mainMod SHIFT, 7, movetoworkspace, 7"
        "$mainMod SHIFT, 8, movetoworkspace, 8"
        "$mainMod SHIFT, 9, movetoworkspace, 9"
        "$mainMod SHIFT, 0, movetoworkspace, 10"

        "$mainMod, H, movewindow, mon:HDMI-A-5"
        "$mainMod, period, movewindow, mon:DP-3"
        "$mainMod, left, focusmonitor, -1"
        "$mainMod, right, focusmonitor, +1"
      ];

      "$mainMod" = "SUPER";

      input = {
        kb_layout = "es";
      };

      animations = {
        enabled = true;
        bezier = "myBezier, 0.05, 0.9, 0.1, 1.05";
        animation = [
          "windows, 1, 7, myBezier"
          "windowsOut, 1, 7, default, popin 80%"
          "border, 1, 10, default"
          "borderangle, 1, 8, default"
          "fade, 1, 7, default"
          "workspaces, 1, 6, default"
        ];
      };

      cursor = {
        no_warps = false;
        no_hardware_cursors = false;
      };
    };
  };
}

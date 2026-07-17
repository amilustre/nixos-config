{ config, pkgs, lib, ... }:

let
  dashboardApiPy = ./dashboard_api.py;
in
{
  # Deploy the Python script to a known system path for reference
  environment.etc."dashboard-api/server.py".source = dashboardApiPy;

  # User systemd service via home-manager — depends on hyprland-session.target
  # so HYPRLAND_INSTANCE_SIGNATURE is available through the session env.
  home-manager.users.alexis = { pkgs, ... }: {
    home.file."dashboard-api/server.py".source = dashboardApiPy;

    systemd.user.services.dashboard-api = {
      Unit = {
        Description = "ESP32 Dashboard API for Hyprland";
        After = [ "hyprland-session.target" ];
      };
      Service = {
        ExecStart = "${pkgs.python3}/bin/python3 %h/dashboard-api/server.py";
        Restart = "on-failure";
        RestartSec = 5;
      };
      Install = {
        WantedBy = [ "hyprland-session.target" ];
      };
    };
  };
}

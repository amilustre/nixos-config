{ config, pkgs, ... }:

{
  programs.git = {
    enable = true;
    settings = {
      user = {
        name = "Alexis";
        email = "alexis.marin.ilustre@gmail.com";
      };
      init = {
        defaultBranch = "main";
      };
    };
  };
}

{
  description = "Configuración inmutable de NixOS con Hyprland";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
    home-manager = {
      url = "github:nix-community/home-manager/release-26.05";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    # OpenLogi — alternativa local-first a Logitech Options+ (HID++/uinput),
    # sustituye al LogiTune (mmaher88) que nunca llegó a funcionar.
    # NixOS module oficial: paquete + udev rules + agente (graphical-session).
    openlogi = {
      url = "github:AprilNEA/OpenLogi";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, home-manager, openlogi, ... }@inputs:
    let
      lib = nixpkgs.lib;
      system = "x86_64-linux";
      # Fix local (upstream package.nix solo parchea openlogi-desktop): el
      # helper del Actions Ring (openlogi-overlay) necesita el mismo RUNPATH
      # extra (libGL/wayland/vulkan-loader — dlopen de gpui) o paniquea con
      # NoWayLandLib. Verificado en nixtopus 07-09.
      openlogiPkg = let pkgs = nixpkgs.legacyPackages.${system}; in
        openlogi.packages.${system}.openlogi.overrideAttrs (o: {
          postFixup = (o.postFixup or "") + ''
            patchelf --add-rpath "${pkgs.lib.makeLibraryPath [ pkgs.libGL pkgs.wayland pkgs.vulkan-loader ]}" "$out/bin/openlogi-overlay"
          '';
        });
    in
    {
      nixosConfigurations.desktop = lib.nixosSystem {
        inherit system;
        specialArgs = { inherit inputs; };
        modules = [
          ./hosts/desktop/configuration.nix
          openlogi.nixosModules.default
          {
            programs.openlogi = {
              enable = true;
              launchAtLogin = true; # agente arranca con la sesión gráfica
              package = openlogiPkg;
            };
          }
          home-manager.nixosModules.home-manager
          {
            home-manager.useGlobalPkgs = true;
            home-manager.useUserPackages = true;
            home-manager.users.alexis = { pkgs, ... }: {
              imports = [
                ./home/home.nix
                ./home/apps-desktop.nix
              ];
            };
            home-manager.extraSpecialArgs = { inherit inputs; };
          }
        ];
      };

      nixosConfigurations.workstation = lib.nixosSystem {
        inherit system;
        specialArgs = { inherit inputs; };
        modules = [
          ./hosts/workstation/configuration.nix
          home-manager.nixosModules.home-manager
          {
            home-manager.useGlobalPkgs = true;
            home-manager.useUserPackages = true;
            home-manager.users.alexis = { pkgs, ... }: {
              imports = [
                ./home/home.nix
                ./home/apps-desktop.nix
              ];
            };
            home-manager.extraSpecialArgs = { inherit inputs; };
          }
        ];
      };
    };
}

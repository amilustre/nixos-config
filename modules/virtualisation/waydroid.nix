{ config, pkgs, ... }:

{
  virtualisation.waydroid.enable = true;

  # Fix: el kernel de nixtopus (7.1.2) no trae compilado ni cargable el
  # modulo legacy `ip_tables` (ni como builtin ni como .ko en
  # /run/booted-system/kernel-modules), solo soporta nf_tables/nftables.
  # El paquete `waydroid` por defecto de nixpkgs usa `iptables` (backend
  # legacy) en el wrapper de waydroid-net.sh, lo que provoca:
  #   modprobe: FATAL: Module ip_tables not found ...
  #   iptables v1.8.13 (legacy): can't initialize iptables table `filter'
  #   RuntimeError: Command failed: .../waydroid-net.sh start
  # nixpkgs ya expone `pkgs.waydroid-nftables` (waydroid.override {
  # withNftables = true; }), que envuelve el script con `nftables` en vez
  # de `iptables`, evitando la dependencia del modulo legacy. Usamos la
  # opcion oficial del modulo para seleccionarlo.
  virtualisation.waydroid.package = pkgs.waydroid-nftables;
}

# Terminal interactiva: nix flake update → nixos-rebuild switch → commit/push
# opcionales. Si el switch falla ofrece restaurar el flake.lock anterior.
flake="${UPDATE_CHECK_FLAKE:-$HOME/nixos-config}"
update_check="${UPDATE_CHECK_BIN:-update-check}"
host="$(</proc/sys/kernel/hostname)"

pause() { read -rp $'\nPulsa Enter para cerrar…' _ || true; }
fail() { printf '\n\e[1;31m✗ %s\e[0m\n' "$*"; pause; exit 1; }
ask() { local a; read -rp "$1 [s/N] " a || return 1; [[ $a == [sS]* ]]; }
refresh_waybar() { pkill -RTMIN+8 -x '\.?waybar(-wrapped)?' || true; }

cd "$flake" || fail "No existe $flake"
printf '\e[1m== Actualizaciones disponibles (%s) ==\e[0m\n' "$host"
"$update_check" report
echo
ask "¿Actualizar flake.lock y aplicar con nixos-rebuild switch (.#$host)?" || exit 0

backup="$(mktemp --suffix=.flake.lock)"
trap 'rm -f "$backup"' EXIT
cp flake.lock "$backup"

nix flake update || fail "nix flake update falló"

# "nixpkgs 3ec6363→abcdef1, home-manager …" (solo inputs directos que cambian)
summary="$(jq -rn --slurpfile a "$backup" --slurpfile b flake.lock '
  ($a[0].nodes) as $o | ($b[0].nodes) as $n
  | [ $n.root.inputs | to_entries[] | select(.value | type == "string")
      | .value as $k
      | select($o[$k].locked.rev != $n[$k].locked.rev)
      | "\(.key) \(($o[$k].locked.rev // "?")[0:7])→\(($n[$k].locked.rev // "?")[0:7])" ]
  | join(", ")')"
echo "Inputs: ${summary:-sin cambios}"

if ! /run/wrappers/bin/sudo /run/current-system/sw/bin/nixos-rebuild switch --flake ".#$host"; then
  if ask "El switch falló. ¿Restaurar el flake.lock anterior?"; then
    cp "$backup" flake.lock
  fi
  refresh_waybar
  fail "nixos-rebuild switch falló"
fi
refresh_waybar
printf '\n\e[1;32m✓ Sistema actualizado\e[0m\n'

if [[ "$(readlink -f /run/booted-system/kernel)" != "$(readlink -f /run/current-system/kernel)" ]]; then
  printf '\e[1;33m⚠ Kernel nuevo: reinicia para usarlo\e[0m\n'
fi

if ! git diff --quiet -- flake.lock && ask "¿Commit del flake.lock?"; then
  git commit -m "flake: actualizar inputs (${summary:-flake.lock}). Switch $host OK" -- flake.lock \
    || fail "git commit falló"
  if ask "¿git push?"; then
    git push || fail "git push falló"
  fi
fi
pause

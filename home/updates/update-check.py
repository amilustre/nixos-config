#!/usr/bin/env python3
"""Alertas de actualizaciones de NixOS: inputs del flake → sistema y aplicaciones.

Subcomandos:
  check   consulta GitHub, calcula qué paquetes cambiarían con los inputs
          nuevos, guarda el estado, refresca waybar y notifica si hay
          novedades que aún no se habían notificado (lo lanza el timer).
  waybar  JSON del módulo custom/updates (estado guardado + estado en vivo).
  report  resumen en texto plano (lo usa update-apply).
  notify  notificación con acción «Actualizar» (vía systemd-run).
  apply   abre la terminal de actualización (update-apply).
"""

import getpass
import html
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

FLAKE = Path(os.environ.get("UPDATE_CHECK_FLAKE", Path.home() / "nixos-config"))
HOST = os.environ.get("UPDATE_CHECK_HOST") or socket.gethostname()
STATE_FILE = (
    Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
    / "update-check"
    / "state.json"
)
SELF = os.environ.get("UPDATE_CHECK_BIN", "update-check")
APPLY = os.environ.get("UPDATE_APPLY_BIN", "update-apply")
WAYBAR_SIGNAL = 8
TOOLTIP_MAX = 20

KERNEL = "linux (kernel)"
NVIDIA = "nvidia (driver)"

# Lo que se percibe como «sistema» y «aplicaciones»: paquetes de sistema y de
# home-manager, más kernel y driver NVIDIA (no están en systemPackages).
VERSIONS_EXPR = r"""
c: let
  info = p: let r = builtins.tryEval (
      if p ? pname && p ? version then { n = p.pname; v = p.version; }
      else let d = builtins.parseDrvName (p.name or ""); in { n = d.name; v = d.version; });
    in if r.success then r.value else null;
  hm = c.home-manager.users or { };
  hmPkgs = if hm ? "@USER@" then hm."@USER@".home.packages else [ ];
  pkgs = builtins.filter (x: x != null && x.n != "" && x.v != "")
    (map info (c.environment.systemPackages ++ hmPkgs));
  # Mismo pname con varias versiones (fuse 2 y 3): "2.9.9 + 3.18.2".
  versions = xs: builtins.concatStringsSep " + "
    (builtins.attrNames (builtins.listToAttrs (map (x: { name = x.v; value = null; }) xs)));
  nvidia = builtins.elem "nvidia" c.services.xserver.videoDrivers;
in builtins.mapAttrs (_: versions) (builtins.groupBy (x: x.n) pkgs)
  // { "@KERNEL@" = c.boot.kernelPackages.kernel.version; }
  // (if nvidia then { "@NVIDIA@" = c.hardware.nvidia.package.version; } else { })
"""


def sh(cmd, timeout=120):
    try:
        return subprocess.run(
            cmd, check=True, capture_output=True, text=True, timeout=timeout
        ).stdout
    except subprocess.CalledProcessError as e:
        tail = (e.stderr or "").strip().splitlines()[-3:]
        raise RuntimeError(f"{cmd[0]} {cmd[1]}: " + " | ".join(tail)) from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"{cmd[0]} {cmd[1]}: timeout ({timeout}s)") from e


def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE_FILE)


def lock_inputs():
    """Inputs directos del flake: nombre → (locked, original)."""
    lock = json.loads((FLAKE / "flake.lock").read_text())
    nodes = lock["nodes"]
    result = {}
    for name, ref in nodes[lock.get("root", "root")].get("inputs", {}).items():
        if isinstance(ref, str):  # las listas son «follows»
            node = nodes[ref]
            result[name] = (node.get("locked", {}), node.get("original", {}))
    return result


def latest_rev(owner, repo, ref):
    out = sh(["git", "ls-remote", f"https://github.com/{owner}/{repo}", ref or "HEAD"], 60)
    refs = {}
    for line in out.splitlines():
        rev, name = line.split("\t", 1)
        refs[name] = rev
    candidates = (
        (f"refs/heads/{ref}", f"refs/tags/{ref}^{{}}", f"refs/tags/{ref}") if ref else ("HEAD",)
    )
    for cand in candidates:
        if cand in refs:
            return refs[cand]
    raise RuntimeError(f"{owner}/{repo}: no existe la ref {ref or 'HEAD'}")


def commits_behind(owner, repo, old, new):
    url = f"https://api.github.com/repos/{owner}/{repo}/compare/{old}...{new}?per_page=1"
    req = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json", "User-Agent": "update-check"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r).get("ahead_by")
    except (urllib.error.URLError, OSError, ValueError):
        return None  # dato decorativo: sin él la alerta sigue siendo válida


def flake_url(locked, rev):
    url = f"github:{locked['owner']}/{locked['repo']}/{rev}"
    if locked.get("dir"):
        url += f"?dir={locked['dir']}"
    return url


def eval_versions(overrides):
    expr = (
        VERSIONS_EXPR.replace("@USER@", getpass.getuser())
        .replace("@KERNEL@", KERNEL)
        .replace("@NVIDIA@", NVIDIA)
    )
    cmd = ["nix", "eval", "--json", "--no-write-lock-file"]
    for name, url in overrides:
        cmd += ["--override-input", name, url]
    cmd += [f"{FLAKE}#nixosConfigurations.{HOST}.config", "--apply", expr]
    # La primera vez descarga el nixpkgs nuevo (~50 MB) y evalúa NixOS.
    return json.loads(sh(cmd, timeout=1800))


def diff_versions(old, new):
    first = {KERNEL: 0, NVIDIA: 1}
    names = sorted(old.keys() | new.keys(), key=lambda n: (first.get(n, 2), n.lower()))
    return [
        {"name": n, "old": old.get(n), "new": new.get(n)}
        for n in names
        if old.get(n) != new.get(n)
    ]


def system_status(locked_revs):
    """Estado en vivo: switch pendiente (lock ≠ sistema) y reinicio pendiente."""
    try:
        running = json.loads(sh(["nixos-version", "--json"], 10)).get("nixpkgsRevision")
    except (RuntimeError, OSError, ValueError):
        running = None
    lock_rev = locked_revs.get("nixpkgs")
    booted = os.path.realpath("/run/booted-system/kernel")
    current = os.path.realpath("/run/current-system/kernel")
    return {
        "pending_switch": bool(running and lock_rev and running != lock_rev),
        "reboot": booted != current,
    }


def current_view(state):
    """Cruza el último check con el flake.lock actual: si el lock ya se ha
    actualizado (p. ej. `nix flake update` a mano), esa alerta desaparece."""
    try:
        locked = {n: lk.get("rev") for n, (lk, _) in lock_inputs().items()}
    except (OSError, ValueError, KeyError):
        locked = {}
    outdated = [
        i for i in state.get("inputs", [])
        if locked.get(i["name"]) not in (None, i["latest"])
    ]
    changes = state.get("changes") if outdated else []
    return outdated, changes, system_status(locked)


def refresh_waybar():
    subprocess.run(
        ["pkill", f"-RTMIN+{WAYBAR_SIGNAL}", "-x", r"\.?waybar(-wrapped)?"],
        check=False,
    )


def check():
    state = load_state()
    state["checked_at"] = time.time()
    try:
        inputs = []
        for name, (locked, orig) in lock_inputs().items():
            # Solo inputs de GitHub que siguen una rama (no los fijados a un rev).
            if locked.get("type") != "github" or "rev" in orig:
                continue
            latest = latest_rev(locked["owner"], locked["repo"], orig.get("ref"))
            entry = {
                "name": name,
                "locked": locked["rev"],
                "latest": latest,
                "locked_date": locked.get("lastModified"),
            }
            if latest != locked["rev"]:
                entry["behind"] = commits_behind(
                    locked["owner"], locked["repo"], locked["rev"], latest
                )
                entry["url"] = flake_url(locked, latest)
            inputs.append(entry)
    except (RuntimeError, OSError, ValueError, KeyError) as e:
        state["error"] = str(e)
        save_state(state)
        refresh_waybar()
        print(f"update-check: {e}", file=sys.stderr)
        return 1

    outdated = [i for i in inputs if i["locked"] != i["latest"]]
    signature = ",".join(f"{i['name']}:{i['locked']}>{i['latest']}" for i in outdated)
    state.pop("error", None)
    if not outdated:
        state["changes"] = []
    elif signature != state.get("signature") or state.get("changes") is None:
        try:
            old = eval_versions([])
            new = eval_versions([(i["name"], i["url"]) for i in outdated])
            state["changes"] = diff_versions(old, new)
        except (RuntimeError, OSError, ValueError) as e:
            state["changes"] = None
            state["error"] = f"no se pudo evaluar la configuración nueva: {e}"
    state["inputs"] = inputs
    state["signature"] = signature
    save_state(state)
    refresh_waybar()

    if outdated and state.get("notified") != signature:
        subprocess.run(
            ["systemd-run", "--user", "--collect", "--quiet",
             "--unit=update-check-notify", SELF, "notify"],
            check=False,
        )
        state["notified"] = signature
        save_state(state)
    print(f"update-check: {len(outdated)} inputs desactualizados, "
          f"{len(state['changes'] or [])} paquetes cambian")
    return 0


def short(rev):
    return (rev or "?")[:7]


def describe(state, markup):
    """(texto corto, clase, líneas de detalle)."""
    esc = html.escape if markup else (lambda s: s)
    bold = (lambda s: f"<b>{s}</b>") if markup else (lambda s: s)
    outdated, changes, st = current_view(state)
    lines = []
    if outdated:
        if changes:
            lines.append(bold(f"{len(changes)} paquetes con versión nueva"))
            for c in changes[:TOOLTIP_MAX]:
                lines.append(esc(f"  {c['name']}: {c['old'] or 'nuevo'} → {c['new'] or 'eliminado'}"))
            if len(changes) > TOOLTIP_MAX:
                lines.append(f"  … y {len(changes) - TOOLTIP_MAX} más")
        elif changes == []:
            lines.append(bold("Inputs nuevos (sin cambios de versión en paquetes)"))
        else:
            lines.append(bold("Inputs nuevos (cambios de paquetes desconocidos)"))
        lines.append("")
        for i in outdated:
            behind = f", {i['behind']} commits" if i.get("behind") else ""
            age = ""
            if i.get("locked_date"):
                days = int((time.time() - i["locked_date"]) // 86400)
                age = f", lock de hace {days} d"
            lines.append(esc(f"{i['name']}: {short(i['locked'])} → {short(i['latest'])}{behind}{age}"))
    if st["pending_switch"]:
        lines.append(esc("flake.lock más nuevo que el sistema: falta nixos-rebuild switch"))
    if st["reboot"]:
        lines.append(esc("Kernel actualizado: reinicia para usarlo"))
    if state.get("error"):
        lines.append(esc(f"Error en la última comprobación: {state['error']}"))

    if outdated:
        text, cls = f"󰚰 {len(changes)}" if changes else "󰚰", "updates"
    elif st["pending_switch"]:
        text, cls = "󰚰", "pending"
    elif st["reboot"]:
        text, cls = "󰜉", "reboot"
    elif state.get("error"):
        text, cls = "󰀦", "error"
    else:
        text, cls = "", "updated"
    return text, cls, lines


def waybar():
    state = load_state()
    text, cls, lines = describe(state, markup=True)
    checked = state.get("checked_at")
    when = time.strftime("%d/%m %H:%M", time.localtime(checked)) if checked else "nunca"
    footer = f"Comprobado: {when} · clic: actualizar · clic derecho: comprobar ya"
    tooltip = "\n".join(lines + ([""] if lines else []) + [footer])
    print(json.dumps({"text": text, "class": cls, "tooltip": tooltip}))
    return 0


def report():
    _, _, lines = describe(load_state(), markup=False)
    print("\n".join(lines) if lines else "Todo al día.")
    return 0


def notify():
    state = load_state()
    outdated, changes, _ = current_view(state)
    if not outdated:
        return 0
    if changes:
        body = "\n".join(
            f"{c['name']}: {c['old'] or 'nuevo'} → {c['new'] or 'eliminado'}"
            for c in changes[:8]
        )
        if len(changes) > 8:
            body += f"\n… y {len(changes) - 8} más"
        title = f"{len(changes)} actualizaciones disponibles"
    else:
        body = ", ".join(i["name"] for i in outdated)
        title = "Inputs del flake actualizables"
    # Acción «default»: el clic izquierdo de dunst (do_action) la ejecuta directamente.
    out = subprocess.run(
        ["notify-send", "--app-name=Actualizaciones", "--icon=system-software-update",
         "--action=default=Actualizar", "--wait", title, html.escape(body)],
        capture_output=True, text=True, check=False,
    ).stdout.strip()
    if out == "default":
        return apply()
    return 0


def apply():
    # Unidad transitoria propia: la terminal sobrevive a quien la lanza
    # (waybar o la unidad de la notificación) y no se abren dos a la vez.
    # systemd-run no hereda el entorno: se pasan las rutas explícitamente.
    subprocess.run(
        ["systemd-run", "--user", "--collect", "--quiet", "--unit=update-apply",
         f"--setenv=UPDATE_CHECK_BIN={SELF}", f"--setenv=UPDATE_CHECK_FLAKE={FLAKE}",
         "alacritty", "--class", "update-apply", "-T", "Actualizar NixOS", "-e", APPLY],
        check=False,
    )
    return 0


COMMANDS = {"check": check, "waybar": waybar, "report": report, "notify": notify, "apply": apply}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        print(f"uso: update-check {{{'|'.join(COMMANDS)}}}", file=sys.stderr)
        sys.exit(2)
    sys.exit(COMMANDS[sys.argv[1]]())

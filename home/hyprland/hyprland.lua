-- Configuración de Hyprland (Lua, Hyprland ≥ 0.57: los .conf ya no se leen).
-- home-manager la incrusta en ~/.config/hypr/hyprland.lua vía extraConfig,
-- tras sus propios hooks de systemd (hyprland-session.target).
-- API: https://wiki.hypr.land/configuring/ · stubs en <hyprland>/share/hypr/stubs

local mainMod = "SUPER"

------------------
---- MONITORS ----
------------------

hl.monitor({ output = "DP-3",     mode = "2560x1080@144", position = "0x-1080", scale = 1 })
hl.monitor({ output = "HDMI-A-5", mode = "2560x1080@144", position = "0x0",     scale = 1 })

-- Workspaces 1-5 en el monitor principal (HDMI-A-5), 6-9 en el de arriba (DP-3)
for i = 1, 9 do
    hl.workspace_rule({ workspace = tostring(i), monitor = i <= 5 and "HDMI-A-5" or "DP-3" })
end

-------------------
---- AUTOSTART ----
-------------------

hl.on("hyprland.start", function()
    -- Fondo Nothing OS: el daemon debe estar antes que la imagen
    -- (en nixpkgs 26.05 swww → awww)
    hl.exec_cmd("awww-daemon")
    hl.exec_cmd("awww img /home/alexis/Pictures/wallpapers/nothing-dots.png")
    hl.exec_cmd("waybar")
    hl.exec_cmd("dunst")
    hl.exec_cmd("firefox", { workspace = "2 silent" })
    hl.exec_cmd("alacritty", { workspace = "1 silent" })
    -- Thunderbird en segundo plano (workspace especial; clic en su icono de waybar)
    hl.exec_cmd("thunderbird", { workspace = "special:mail silent" })
end)

-----------------------
---- LOOK AND FEEL ----
-----------------------

hl.config({
    general = {
        gaps_in     = 5,
        gaps_out    = 10,
        border_size = 2,
        col = {
            active_border   = { colors = { "rgba(d71921ee)", "rgba(ffffff55)" }, angle = 45 },
            inactive_border = "rgba(33333aee)",
        },
        layout = "dwindle",
    },

    decoration = {
        rounding = 10,
        blur = {
            enabled = true,
            size    = 3,
            passes  = 1,
        },
        shadow = {
            enabled = true,
            range   = 4,
        },
    },

    animations = {
        enabled = true,
    },

    input = {
        kb_layout = "es",
    },

    cursor = {
        no_warps            = false,
        no_hardware_cursors = false,
    },

    xwayland = {
        enabled = true,
    },
})

hl.curve("myBezier", { type = "bezier", points = { { 0.05, 0.9 }, { 0.1, 1.05 } } })

hl.animation({ leaf = "windows",     enabled = true, speed = 7,  bezier = "myBezier" })
hl.animation({ leaf = "windowsOut",  enabled = true, speed = 7,  bezier = "default", style = "popin 80%" })
hl.animation({ leaf = "border",      enabled = true, speed = 10, bezier = "default" })
hl.animation({ leaf = "borderangle", enabled = true, speed = 8,  bezier = "default" })
hl.animation({ leaf = "fade",        enabled = true, speed = 7,  bezier = "default" })
hl.animation({ leaf = "workspaces",  enabled = true, speed = 6,  bezier = "default" })

-----------------------
---- WINDOW RULES -----
-----------------------

-- OpenLogi Actions Ring: overlay popup (gpui toplevel) — flotar sin
-- foco/borde/sombra/anim para que se comporte como overlay, no ventana.
hl.window_rule({
    name  = "openlogi-action-ring",
    match = { class = "^(openlogi-action-ring)$" },

    float            = true,
    no_initial_focus = true,
    no_focus         = true,
    decorate         = false,
    no_shadow        = true,
    no_anim          = true,
    no_dim           = true,
})

---------------------
---- KEYBINDINGS ----
---------------------

hl.bind(mainMod .. " + Return", hl.dsp.exec_cmd("alacritty"))
hl.bind(mainMod .. " + Q",      hl.dsp.window.close())
hl.bind(mainMod .. " + F",      hl.dsp.window.fullscreen())
hl.bind(mainMod .. " + V",      hl.dsp.window.float({ action = "toggle" }))
hl.bind(mainMod .. " + D",      hl.dsp.exec_cmd("rofi -show drun"))   -- Rofi launcher
hl.bind(mainMod .. " + Escape", hl.dsp.exec_cmd("wlogout"))           -- Wlogout menu
hl.bind(mainMod .. " + L",      hl.dsp.exec_cmd("hyprlock"))          -- Hyprlock
hl.bind("Print",                  hl.dsp.exec_cmd("flameshot gui"))   -- Captura con selección/edición
hl.bind(mainMod .. " + SHIFT + S", hl.dsp.exec_cmd("flameshot gui"))   -- Idem (atajo estilo Windows/GNOME)
hl.bind(mainMod .. " + Print",    hl.dsp.exec_cmd("flameshot full"))  -- Pantalla completa directa a ~/Pictures/screenshots

-- mainMod + [0-9] cambia de workspace; mainMod + SHIFT + [0-9] mueve la ventana
for i = 1, 10 do
    local key = i % 10 -- el 10 va en la tecla 0
    hl.bind(mainMod .. " + " .. key,         hl.dsp.focus({ workspace = i }))
    hl.bind(mainMod .. " + SHIFT + " .. key, hl.dsp.window.move({ workspace = i }))
end

hl.bind(mainMod .. " + H",      hl.dsp.window.move({ monitor = "HDMI-A-5" }))
hl.bind(mainMod .. " + period", hl.dsp.window.move({ monitor = "DP-3" }))
hl.bind(mainMod .. " + left",   hl.dsp.focus({ monitor = "-1" }))
hl.bind(mainMod .. " + right",  hl.dsp.focus({ monitor = "+1" }))
hl.bind(mainMod .. " + CTRL + left",  hl.dsp.focus({ workspace = "e-1" }))  -- Workspace anterior (encoder dcha en capa NIX del Sofle)
hl.bind(mainMod .. " + CTRL + right", hl.dsp.focus({ workspace = "e+1" }))  -- Workspace siguiente

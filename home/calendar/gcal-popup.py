#!/usr/bin/env python3
"""Pop-up de calendario para waybar con los eventos de Google Calendar.

Se abre/cierra con clic en el reloj (una segunda instancia cierra la primera).
Usa la API de Google Calendar (solo lectura) para que los calendarios visibles,
sus nombres y sus colores (y el color propio de cada evento) sean los de Google.

Configuración, una sola vez:
  1. ~/.config/gcal-popup/client_secret.json: cliente OAuth «App de escritorio»
     de un proyecto de Google Cloud con la Google Calendar API habilitada.
  2. `gcal-popup --login` (o el botón «Conectar con Google»): autoriza en el
     navegador y guarda ~/.config/gcal-popup/token.json (permisos 600).
Los eventos se cachean por mes en ~/.cache/gcal-popup/events.json y se
refrescan si tienen más de 15 min.
"""

import datetime as dt
import html
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("GLibUnix", "2.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, Gio, GLib, GLibUnix, Gtk, GtkLayerShell, Pango  # noqa: E402

import requests  # noqa: E402
from google.auth.exceptions import RefreshError, TransportError  # noqa: E402
from google.auth.transport.requests import AuthorizedSession, Request  # noqa: E402
from google.oauth2.credentials import Credentials  # noqa: E402
from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "gcal-popup"
CLIENT_SECRET = CONFIG_DIR / "client_secret.json"
TOKEN = CONFIG_DIR / "token.json"
CACHE_FILE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "gcal-popup" / "events.json"
PIDFILE = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "gcal-popup.pid"
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
API = "https://www.googleapis.com/calendar/v3"
MAX_AGE = 15 * 60
MAX_CACHED_MONTHS = 12
MAX_DAY_EVENTS = 8
FALLBACK_COLOR = "#8a8a93"

MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

CSS = b"""
* { font-family: "JetBrainsMono Nerd Font"; color: #e4e4e7; font-size: 13px;
    text-shadow: none; -gtk-icon-shadow: none; }
window { background: transparent; }
.popup { background: rgba(10,10,12,0.96); border: 1px solid #33333a; border-radius: 12px;
         padding: 12px; }
button { background: none; background-image: none; border: none; box-shadow: none;
         border-radius: 8px; padding: 2px 6px; min-height: 0; }
button:hover { background: #1c1c21; }
.title { font-weight: bold; letter-spacing: 1px; }
.weekday { color: #58585f; font-size: 11px; }
.day { min-width: 36px; min-height: 36px; padding: 0; }
.day.other label { color: #58585f; }
.day.today { background: #d71921; }
.day.today label { color: #ffffff; font-weight: bold; }
.day.selected { box-shadow: inset 0 0 0 1px #d71921; }
.heading { color: #d71921; font-weight: bold; margin-top: 4px; }
.muted { color: #8a8a93; font-size: 11px; }
separator { background: #33333a; min-height: 1px; margin: 8px 0; }
"""


class AuthNeeded(Exception):
    """Falta el cliente OAuth o hay que (re)conectar la cuenta."""


@dataclass
class Event:
    summary: str
    start: object  # date (todo el día) o datetime local
    end: object
    location: str
    color: str
    calendar: str

    @classmethod
    def from_dict(cls, d):
        return cls(d["summary"], parse_when(d["start"]), parse_when(d["end"]),
                   d["location"], d["color"], d["calendar"])

    @property
    def all_day(self):
        return not isinstance(self.start, dt.datetime)

    def days(self):
        """Días (date) que ocupa; el final es exclusivo."""
        if self.all_day:
            first, last = self.start, max(self.start, self.end - dt.timedelta(days=1))
        else:
            first = self.start.date()
            last = max(first, (self.end - dt.timedelta(seconds=1)).date())
        return first, last

    def sort_key(self):
        if self.all_day:  # primero los de todo el día
            return (0, dt.datetime.combine(self.start, dt.time.min).astimezone(), self.summary)
        return (1, self.start, self.summary)


def parse_when(value):
    if "T" in value:
        return dt.datetime.fromisoformat(value).astimezone()
    return dt.date.fromisoformat(value)


def tilde(path):
    return str(path).replace(str(Path.home()), "~", 1)


def write_private(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text)
    tmp.chmod(0o600)
    tmp.replace(path)


# ----- Google -----
def credentials():
    if not CLIENT_SECRET.exists():
        raise AuthNeeded(f"Falta {tilde(CLIENT_SECRET)} (cliente OAuth de Google Cloud)")
    if not TOKEN.exists():
        raise AuthNeeded("Cuenta de Google sin conectar")
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds.valid:
        if not creds.refresh_token:
            raise AuthNeeded("Sesión de Google caducada")
        try:
            creds.refresh(Request())
        except RefreshError as e:
            raise AuthNeeded("Sesión de Google caducada o revocada") from e
        write_private(TOKEN, creds.to_json())
    return creds


def login():
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    # prompt=consent: Google solo entrega refresh_token en el primer consentimiento.
    creds = flow.run_local_server(
        port=0, prompt="consent",
        success_message="gcal-popup ya está conectado con Google. Puedes cerrar esta pestaña.")
    write_private(TOKEN, creds.to_json())
    print(f"Conectado. Token guardado en {tilde(TOKEN)}")


def declined(event):
    return any(a.get("self") and a.get("responseStatus") == "declined"
               for a in event.get("attendees", []))


def fetch_range(first, last):
    """Calendarios marcados como visibles en Google y sus eventos en [first, last]."""
    creds = credentials()
    token_before = creds.token
    session = AuthorizedSession(creds)

    def get(path, **params):
        r = session.get(API + path, params=params, timeout=20)
        r.raise_for_status()
        return r.json()

    def items(path, **params):
        while True:
            data = get(path, **params)
            yield from data.get("items", [])
            if not data.get("nextPageToken"):
                return
            params["pageToken"] = data["nextPageToken"]

    event_colors = {k: v["background"] for k, v in get("/colors").get("event", {}).items()}
    time_min = dt.datetime.combine(first, dt.time.min).astimezone().isoformat()
    time_max = dt.datetime.combine(last + dt.timedelta(days=1), dt.time.min).astimezone().isoformat()
    calendars, events = [], []
    for cal in items("/users/me/calendarList"):
        if not cal.get("selected") or cal.get("hidden"):
            continue
        name = cal.get("summaryOverride") or cal.get("summary") or cal["id"]
        cal_color = cal.get("backgroundColor") or FALLBACK_COLOR
        calendars.append(name)
        path = f"/calendars/{urllib.parse.quote(cal['id'], safe='')}/events"
        for ev in items(path, timeMin=time_min, timeMax=time_max, singleEvents="true",
                        orderBy="startTime", maxResults=2500):
            if ev.get("status") == "cancelled" or declined(ev):
                continue
            events.append({
                "summary": ev.get("summary") or "(sin título)",
                "start": ev["start"].get("dateTime") or ev["start"]["date"],
                "end": ev["end"].get("dateTime") or ev["end"]["date"],
                "location": ev.get("location", ""),
                # Color propio del evento si lo tiene; si no, el del calendario.
                "color": event_colors.get(ev.get("colorId"), cal_color),
                "calendar": name,
            })
    if creds.token != token_before:
        write_private(TOKEN, creds.to_json())
    return {"calendars": calendars, "events": events}


# ----- caché -----
def load_cache():
    try:
        return json.loads(CACHE_FILE.read_text()).get("months", {})
    except (FileNotFoundError, ValueError):
        return {}


def save_cache(months):
    recent = sorted(months.items(), key=lambda kv: kv[1]["fetched"], reverse=True)
    write_private(CACHE_FILE, json.dumps({"months": dict(recent[:MAX_CACHED_MONTHS])}))


def toggle_existing():
    """Si ya hay un pop-up abierto, ciérralo y devuelve True."""
    try:
        pid = int(PIDFILE.read_text())
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
    except (FileNotFoundError, ValueError):
        return False
    if pid == os.getpid() or b"gcal-popup" not in cmdline:
        return False
    os.kill(pid, signal.SIGTERM)
    return True


class Popup(Gtk.Window):
    def __init__(self):
        super().__init__(title="gcal-popup")
        self.today = dt.date.today()
        self.selected = self.today
        self.year, self.month = self.today.year, self.today.month
        self.months = load_cache()  # "AAAA-MM" → {fetched, calendars, events}
        self.loading = set()
        self.error = None           # (tipo, mensaje) del último fallo
        self.month_events = []

        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_namespace(self, "gcal-popup")
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, 6)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, 10)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)
        self.connect("key-press-event", self.on_key)
        self.connect("destroy", Gtk.main_quit)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        root.get_style_context().add_class("popup")
        self.add(root)

        header = Gtk.Box(spacing=4)
        prev_btn = Gtk.Button(label="󰅁")
        prev_btn.connect("clicked", lambda *_: self.shift_month(-1))
        next_btn = Gtk.Button(label="󰅂")
        next_btn.connect("clicked", lambda *_: self.shift_month(1))
        self.title_btn = Gtk.Button()
        self.title_btn.set_tooltip_text("Ir a hoy")
        self.title_btn.connect("clicked", lambda *_: self.select(dt.date.today()))
        self.title_label = Gtk.Label()
        self.title_label.get_style_context().add_class("title")
        self.title_btn.add(self.title_label)
        refresh_btn = Gtk.Button(label="󰑐")
        refresh_btn.set_tooltip_text("Sincronizar ahora")
        refresh_btn.connect("clicked", lambda *_: self.ensure(force=True))
        close_btn = Gtk.Button(label="󰅖")
        close_btn.connect("clicked", lambda *_: self.destroy())
        header.pack_start(prev_btn, False, False, 0)
        header.pack_start(self.title_btn, True, True, 0)
        header.pack_start(next_btn, False, False, 0)
        header.pack_end(close_btn, False, False, 0)
        header.pack_end(refresh_btn, False, False, 0)
        root.pack_start(header, False, False, 0)

        grid = Gtk.Grid(column_homogeneous=True, row_spacing=2, column_spacing=2)
        for col, letter in enumerate("LMXJVSD"):
            label = Gtk.Label(label=letter)
            label.get_style_context().add_class("weekday")
            grid.attach(label, col, 0, 1, 1)
        self.day_buttons = []
        for i in range(42):
            btn = Gtk.Button()
            btn.get_style_context().add_class("day")
            label = Gtk.Label()
            label.set_justify(Gtk.Justification.CENTER)
            btn.add(label)
            btn.connect("clicked", self.on_day)
            grid.attach(btn, i % 7, 1 + i // 7, 1, 1)
            self.day_buttons.append((btn, label))
        root.pack_start(grid, False, False, 0)

        root.pack_start(Gtk.Separator(), False, False, 0)
        self.day_heading = Gtk.Label(xalign=0)
        self.day_heading.get_style_context().add_class("heading")
        root.pack_start(self.day_heading, False, False, 0)
        # Sin ScrolledWindow: con layer-shell no recalcula bien la altura;
        # se muestran como mucho MAX_DAY_EVENTS y un «… y N más».
        self.event_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        root.pack_start(self.event_box, False, False, 0)

        root.pack_start(Gtk.Separator(), False, False, 0)
        self.status = Gtk.Label(xalign=0)
        self.status.set_line_wrap(True)
        self.status.set_max_width_chars(40)
        self.status.get_style_context().add_class("muted")
        root.pack_start(self.status, False, False, 0)
        footer = Gtk.Box(spacing=4)
        footer.set_halign(Gtk.Align.END)
        self.connect_btn = Gtk.Button(label="Conectar con Google 󰊭")
        self.connect_btn.set_no_show_all(True)
        self.connect_btn.connect("clicked", self.on_connect)
        open_btn = Gtk.Button(label="Abrir en Google 󰏌")
        open_btn.connect("clicked", self.open_google)
        footer.pack_start(self.connect_btn, False, False, 0)
        footer.pack_start(open_btn, False, False, 0)
        root.pack_start(footer, False, False, 0)

        self.render()
        self.ensure()

    # ----- datos -----
    def key(self):
        return f"{self.year:04d}-{self.month:02d}"

    def grid_start(self):
        first = dt.date(self.year, self.month, 1)
        return first - dt.timedelta(days=first.weekday())  # lunes

    def ensure(self, force=False):
        """Descarga el mes visible si falta, está caducado o se fuerza."""
        key = self.key()
        entry = self.months.get(key)
        fresh = entry and time.time() - entry["fetched"] < MAX_AGE
        if key in self.loading or (fresh and not force):
            self.update_status()
            return
        self.loading.add(key)
        self.update_status()
        first = self.grid_start()
        threading.Thread(target=self._fetch_worker, args=(key, first, first + dt.timedelta(days=41)),
                         daemon=True).start()

    def _fetch_worker(self, key, first, last):
        data, error = None, None
        try:
            data = fetch_range(first, last)
        except AuthNeeded as e:
            error = ("auth", str(e))
        except (requests.RequestException, TransportError) as e:
            error = ("net", f"Error de red con Google: {e.__class__.__name__}")
        except (KeyError, ValueError) as e:
            error = ("net", f"Respuesta inesperada de Google: {e}")
        GLib.idle_add(self.on_fetched, key, data, error)

    def on_fetched(self, key, data, error):
        self.loading.discard(key)
        self.error = error
        if data is not None:
            self.months[key] = {"fetched": time.time(), **data}
            try:
                save_cache(self.months)
            except OSError as e:
                self.error = ("net", f"No se pudo guardar la caché: {e}")
        if key == self.key():
            self.render()
        else:
            self.update_status()
        return False

    def update_status(self):
        entry = self.months.get(self.key())
        auth = self.error is not None and self.error[0] == "auth"
        self.connect_btn.set_visible(auth and CLIENT_SECRET.exists())
        if self.key() in self.loading:
            text = "Sincronizando…"
        elif self.error:
            text = self.error[1]
        elif entry:
            age = time.time() - entry["fetched"]
            text = f"Sincronizado hace {int(age // 60)} min" if age >= 60 else "Sincronizado ahora"
        else:
            text = ""
        self.status.set_text(text)

    # ----- vista -----
    def render(self):
        self.title_label.set_text(f"{MONTHS[self.month - 1]} {self.year}")
        start = self.grid_start()
        end = start + dt.timedelta(days=41)
        entry = self.months.get(self.key(), {})
        try:
            self.month_events = sorted((Event.from_dict(d) for d in entry.get("events", [])),
                                       key=Event.sort_key)
        except (KeyError, ValueError):
            self.month_events = []  # caché de un formato anterior: se rehace al sincronizar
        self.multi_calendar = len(entry.get("calendars", [])) > 1
        colors_by_day = {}
        for ev in self.month_events:
            first, last = ev.days()
            day = max(first, start)
            while day <= min(last, end):
                colors = colors_by_day.setdefault(day, [])
                if ev.color not in colors:
                    colors.append(ev.color)
                day += dt.timedelta(days=1)
        for i, (btn, label) in enumerate(self.day_buttons):
            day = start + dt.timedelta(days=i)
            btn.day = day
            ctx = btn.get_style_context()
            for cls, on in (("other", day.month != self.month), ("today", day == self.today),
                            ("selected", day == self.selected and day != self.today)):
                (ctx.add_class if on else ctx.remove_class)(cls)
            dots = "".join(
                f"<span foreground='{'#ffffff' if day == self.today else c}'>•</span>"
                for c in colors_by_day.get(day, [])[:3]) or " "
            label.set_markup(f"{day.day}\n<span size='small'>{dots}</span>")
        self.render_day()
        self.update_status()

    def render_day(self):
        d = self.selected
        self.day_heading.set_text(f"{WEEKDAYS[d.weekday()]}, {d.day} de {MONTHS[d.month - 1]}")
        for child in self.event_box.get_children():
            child.destroy()
        events = [e for e in self.month_events if e.days()[0] <= d <= e.days()[1]]
        if not events:
            self.event_box.pack_start(self.line("Sin eventos", "muted"), False, False, 0)
        for ev in events[:MAX_DAY_EVENTS]:
            row = Gtk.Box(spacing=8)
            dot = Gtk.Label()
            dot.set_markup(f"<span foreground='{html.escape(ev.color)}'>●</span>")
            dot.set_valign(Gtk.Align.START)
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            title = self.line(None)
            title.set_markup(f"<span foreground='#c8c8cc'>{html.escape(self.time_range(ev, d))}</span>  "
                             f"{html.escape(ev.summary)}")
            text.pack_start(title, False, False, 0)
            if ev.location:
                text.pack_start(self.line(ev.location, "muted"), False, False, 0)
            if self.multi_calendar:
                text.pack_start(self.line(ev.calendar, "muted"), False, False, 0)
            row.pack_start(dot, False, False, 0)
            row.pack_start(text, True, True, 0)
            self.event_box.pack_start(row, False, False, 0)
        if len(events) > MAX_DAY_EVENTS:
            more = f"… y {len(events) - MAX_DAY_EVENTS} más (Abrir en Google)"
            self.event_box.pack_start(self.line(more, "muted"), False, False, 0)
        self.event_box.show_all()

    @staticmethod
    def line(text, css_class=None):
        label = Gtk.Label(label=text or "", xalign=0)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_max_width_chars(38)
        if css_class:
            label.get_style_context().add_class(css_class)
        return label

    @staticmethod
    def time_range(ev, day):
        if ev.all_day:
            return "Todo el día"
        start = ev.start.strftime("%H:%M") if ev.start.date() == day else "…"
        end_day = (ev.end - dt.timedelta(seconds=1)).date() if ev.end > ev.start else ev.start.date()
        end = ev.end.strftime("%H:%M") if end_day == day else "…"
        return start if ev.end == ev.start else f"{start}–{end}"

    # ----- acciones -----
    def shift_month(self, delta):
        month = self.month - 1 + delta
        self.year, self.month = self.year + month // 12, month % 12 + 1
        self.render()
        self.ensure()

    def select(self, day):
        changed = (day.year, day.month) != (self.year, self.month)
        self.selected = day
        self.year, self.month = day.year, day.month
        self.render()
        if changed:
            self.ensure()

    def on_day(self, btn):
        self.select(btn.day)

    def on_key(self, _widget, event):
        keys = {Gdk.KEY_Escape: self.destroy,
                Gdk.KEY_Left: lambda: self.select(self.selected - dt.timedelta(days=1)),
                Gdk.KEY_Right: lambda: self.select(self.selected + dt.timedelta(days=1)),
                Gdk.KEY_Up: lambda: self.select(self.selected - dt.timedelta(days=7)),
                Gdk.KEY_Down: lambda: self.select(self.selected + dt.timedelta(days=7))}
        action = keys.get(event.keyval)
        if action:
            action()
            return True
        return False

    def on_connect(self, *_):
        # El flujo OAuth abre el navegador y espera la redirección: proceso aparte.
        subprocess.Popen([sys.executable, sys.argv[0], "--login"], start_new_session=True)
        self.destroy()

    def open_google(self, *_):
        d = self.selected
        Gio.AppInfo.launch_default_for_uri(
            f"https://calendar.google.com/calendar/r/day/{d.year}/{d.month}/{d.day}", None)
        self.destroy()


def main():
    if sys.argv[1:] == ["--login"]:
        if not CLIENT_SECRET.exists():
            print(f"Falta {tilde(CLIENT_SECRET)}: descarga el cliente OAuth "
                  "(App de escritorio) de Google Cloud.", file=sys.stderr)
            return 1
        login()
        return 0
    if toggle_existing():
        return 0
    PIDFILE.write_text(str(os.getpid()))
    try:
        popup = Popup()
        popup.show_all()
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, Gtk.main_quit)
        Gtk.main()
    finally:
        try:
            if int(PIDFILE.read_text()) == os.getpid():
                PIDFILE.unlink()
        except (FileNotFoundError, ValueError):
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

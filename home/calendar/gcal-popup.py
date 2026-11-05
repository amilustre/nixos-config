#!/usr/bin/env python3
"""Pop-up de calendario para waybar con los eventos de Google Calendar.

Se abre/cierra con clic en el reloj (una segunda instancia cierra la primera).
Los eventos salen de la API de HomeHub (/calendar), que ya tiene la cuenta de
Google conectada: aquí no hay OAuth ni secretos. Si HomeHub pierde la sesión,
se reconecta abriendo https://homehub.ilustre.es/calendar/oauth/start.

Lo que da HomeHub y cómo se usa:
  - /calendar/calendars: id, nombre y si es el principal (sin colores: cada
    calendario toma uno fijo de la paleta de Google, el principal primero).
  - /calendar/events?calendar_id=…&days=N: eventos desde ahora hasta N días
    (máximo 365), como mucho 50 por calendario y con el colorId del evento.
    Si un calendario llega a 50, los días desde su último evento quedan sin
    datos. El pasado no se muestra.
Los eventos se cachean en ~/.cache/gcal-popup/events.json y se refrescan si
tienen más de 15 min.
"""

import datetime as dt
import html
import json
import os
import signal
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("GLibUnix", "2.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, Gio, GLib, GLibUnix, Gtk, GtkLayerShell, Pango  # noqa: E402

API = "https://homehub.ilustre.es/calendar"
DAYS = 365          # máximo que acepta HomeHub
EVENT_LIMIT = 50    # maxResults fijo de HomeHub por calendario
CACHE_FILE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "gcal-popup" / "events.json"
PIDFILE = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "gcal-popup.pid"
MAX_AGE = 15 * 60
MAX_DAY_EVENTS = 8

# Colores de evento de Google Calendar (colorId → color de la web).
EVENT_COLORS = {"1": "#7986cb", "2": "#33b679", "3": "#8e24aa", "4": "#e67c73",
                "5": "#f6bf26", "6": "#f4511e", "7": "#039be5", "8": "#616161",
                "9": "#3f51b5", "10": "#0b8043", "11": "#d50000"}
# Colores de calendario, en orden (principal primero): pavo real, albahaca,
# mandarina, uva, plátano, flamenco, grafito.
CALENDAR_COLORS = ["#039be5", "#0b8043", "#f4511e", "#8e24aa", "#f6bf26", "#e67c73", "#616161"]

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


def start_day(value):
    when = parse_when(value)
    return when.date() if isinstance(when, dt.datetime) else when


def write_private(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(text)
    tmp.chmod(0o600)
    tmp.replace(path)


# ----- HomeHub -----
def get(path, **params):
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.load(r)


def fetch_calendar(cal, color):
    """Eventos de un calendario y el último día con datos completos."""
    # HomeHub mete el ID tal cual en la ruta de Google: un «#» (festivos)
    # cortaría la URL, así que se le pasa ya codificado.
    events = get("/events", calendar_id=cal["id"].replace("#", "%23"), days=DAYS)
    until = dt.date.today() + dt.timedelta(days=DAYS - 1)
    if len(events) >= EVENT_LIMIT:
        # Recortado por el tope: vienen por orden de inicio, así que solo se
        # sabe que está todo hasta el día anterior al del último evento.
        until = min(until, start_day(events[-1]["start"]) - dt.timedelta(days=1))
    name = cal.get("summary") or cal["id"]
    return name, [{
        "summary": ev.get("summary") or "(sin título)",
        "start": ev["start"],
        "end": ev["end"],
        "location": ev.get("location") or "",
        # Color propio del evento si lo tiene; si no, el del calendario.
        "color": EVENT_COLORS.get(ev.get("colorId"), color),
        "calendar": name,
    } for ev in events], until


def fetch_all():
    """Calendarios de HomeHub y sus eventos; los que fallan se listan aparte."""
    calendars = sorted(get("/calendars"), key=lambda c: not c.get("primary"))
    jobs = [(cal, CALENDAR_COLORS[i % len(CALENDAR_COLORS)]) for i, cal in enumerate(calendars)]
    names, events, failed = [], [], []
    until = dt.date.today() + dt.timedelta(days=DAYS - 1)
    with ThreadPoolExecutor(max_workers=len(jobs) or 1) as pool:
        futures = [pool.submit(fetch_calendar, *job) for job in jobs]
        for (cal, _), future in zip(jobs, futures):
            try:
                name, cal_events, cal_until = future.result()
            except (OSError, ValueError, KeyError):
                failed.append(cal.get("summary") or cal["id"])
                continue
            names.append(name)
            events.extend(cal_events)
            until = min(until, cal_until)
    if not names and failed:
        raise OSError("ningún calendario respondió")
    # Más allá de «until» algún calendario está incompleto: no se enseña nada.
    events = [e for e in events if start_day(e["start"]) <= until]
    return {"calendars": names, "events": events, "until": until.isoformat(), "failed": failed}


# ----- caché -----
def load_cache():
    try:
        data = json.loads(CACHE_FILE.read_text())
        return data if {"fetched", "events", "until"} <= data.keys() else None
    except (FileNotFoundError, ValueError, AttributeError):
        return None


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
        self.data = load_cache()  # {fetched, calendars, events, until, failed}
        self.events = []
        self.loading = False
        self.error = None         # mensaje del último fallo

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
        open_btn = Gtk.Button(label="Abrir en Google 󰏌")
        open_btn.connect("clicked", self.open_google)
        footer.pack_start(open_btn, False, False, 0)
        root.pack_start(footer, False, False, 0)

        self.load_events()
        self.render()
        self.ensure()

    # ----- datos -----
    def grid_start(self):
        first = dt.date(self.year, self.month, 1)
        return first - dt.timedelta(days=first.weekday())  # lunes

    def until(self):
        return dt.date.fromisoformat(self.data["until"]) if self.data else None

    def load_events(self):
        try:
            self.events = sorted((Event.from_dict(d) for d in (self.data or {}).get("events", [])),
                                 key=Event.sort_key)
        except (KeyError, ValueError):
            self.data, self.events = None, []  # caché de otro formato: se rehace al sincronizar

    def ensure(self, force=False):
        """Descarga los eventos si faltan, están caducados o se fuerza."""
        fresh = self.data and time.time() - self.data["fetched"] < MAX_AGE
        if not self.loading and (force or not fresh):
            self.loading = True
            threading.Thread(target=self._fetch_worker, daemon=True).start()
        self.update_status()

    def _fetch_worker(self):
        data, error = None, None
        try:
            data = fetch_all()
        except urllib.error.HTTPError as e:
            error = f"HomeHub respondió {e.code}"
        except (OSError, ValueError, KeyError) as e:
            error = f"Error con HomeHub: {getattr(e, 'reason', None) or e}"
        GLib.idle_add(self.on_fetched, data, error)

    def on_fetched(self, data, error):
        self.loading = False
        self.error = error
        if data is not None:
            self.data = {"fetched": time.time(), **data}
            try:
                write_private(CACHE_FILE, json.dumps(self.data))
            except OSError as e:
                self.error = f"No se pudo guardar la caché: {e}"
            self.load_events()
        self.render()
        return False

    def update_status(self):
        if self.loading:
            text = "Sincronizando…"
        elif self.error:
            text = self.error
        elif self.data:
            age = time.time() - self.data["fetched"]
            text = f"Sincronizado hace {int(age // 60)} min" if age >= 60 else "Sincronizado ahora"
            if self.data.get("failed"):
                text += " · sin leer: " + ", ".join(self.data["failed"])
        else:
            text = ""
        self.status.set_text(text)

    # ----- vista -----
    def render(self):
        self.title_label.set_text(f"{MONTHS[self.month - 1]} {self.year}")
        start = self.grid_start()
        end = start + dt.timedelta(days=41)
        self.multi_calendar = len((self.data or {}).get("calendars", [])) > 1
        colors_by_day = {}
        for ev in self.events:
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
        events = [e for e in self.events if e.days()[0] <= d <= e.days()[1]]
        until = self.until()
        if not events:
            if d < self.today:
                empty = "HomeHub solo da eventos desde hoy"
            elif until and d > until:
                empty = f"HomeHub solo llega al {until.day} de {MONTHS[until.month - 1]}"
            else:
                empty = "Sin eventos"
            self.event_box.pack_start(self.line(empty, "muted"), False, False, 0)
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

    def select(self, day):
        self.selected = day
        self.year, self.month = day.year, day.month
        self.render()

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

    def open_google(self, *_):
        d = self.selected
        Gio.AppInfo.launch_default_for_uri(
            f"https://calendar.google.com/calendar/r/day/{d.year}/{d.month}/{d.day}", None)
        self.destroy()


def main():
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

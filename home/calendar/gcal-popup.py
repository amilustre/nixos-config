#!/usr/bin/env python3
"""Pop-up de calendario para waybar con eventos de Google Calendar.

Se abre/cierra con clic en el reloj (una segunda instancia cierra la primera).
Lee la «dirección secreta en formato iCal» de cada calendario desde
~/.config/gcal-popup/calendars (una por línea, opcional «Nombre | URL»),
cachea el .ics en ~/.cache/gcal-popup y lo refresca si tiene más de 15 min.
Solo lectura: «Abrir en Google» lleva al día seleccionado en el navegador.
"""

import datetime as dt
import hashlib
import html
import os
import signal
import sys
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("GLibUnix", "2.0")
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, Gio, GLib, GLibUnix, Gtk, GtkLayerShell, Pango  # noqa: E402

import icalendar  # noqa: E402
import recurring_ical_events  # noqa: E402

CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "gcal-popup" / "calendars"
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "gcal-popup"
PIDFILE = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "gcal-popup.pid"
MAX_AGE = 15 * 60
MAX_DAY_EVENTS = 8

MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
COLORS = ["#d71921", "#5b8def", "#3fb950", "#d29922", "#a371f7", "#e4e4e7"]

TEMPLATE = """\
# Google Calendar → Configuración → (tu calendario) → Integrar el calendario →
# «Dirección secreta en formato iCal». Una URL por línea, opcional «Nombre | URL».
# Es un secreto: este fichero no va al repo (permisos 600).
"""

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
class Source:
    name: str
    url: str
    color: str


@dataclass
class Event:
    summary: str
    start: object  # date (todo el día) o datetime local
    end: object
    location: str
    source: Source

    @property
    def all_day(self):
        return not isinstance(self.start, dt.datetime)

    def days(self):
        """Días (date) que ocupa; DTEND es exclusivo."""
        if self.all_day:
            first, last = self.start, max(self.start, self.end - dt.timedelta(days=1))
        else:
            first = self.start.date()
            last = max(first, (self.end - dt.timedelta(seconds=1)).date())
        return first, last


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


def read_sources():
    if not CONFIG.exists():
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(TEMPLATE)
        CONFIG.chmod(0o600)
    sources = []
    for line in CONFIG.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, url = line.rpartition("|")
        color = COLORS[len(sources) % len(COLORS)]
        sources.append(Source(name.strip() or f"Calendario {len(sources) + 1}", url.strip(), color))
    return sources


def cache_path(url):
    return CACHE / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".ics")


def cache_age(url):
    try:
        return dt.datetime.now().timestamp() - cache_path(url).stat().st_mtime
    except FileNotFoundError:
        return None


def fetch(source):
    req = urllib.request.Request(source.url, headers={"User-Agent": "gcal-popup"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read()
    icalendar.Calendar.from_ical(data)  # no machacar la caché con basura
    CACHE.mkdir(parents=True, exist_ok=True)
    path = cache_path(source.url)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.chmod(0o600)
    tmp.replace(path)


def to_local(value):
    if isinstance(value, dt.datetime):
        return value.astimezone()  # las horas «flotantes» se toman como locales
    return value


def expand(parsed, first, last):
    """Eventos (con recurrencias) que tocan [first, last]."""
    events = []
    for source, cal in parsed:
        for comp in recurring_ical_events.of(cal).between(first, last + dt.timedelta(days=1)):
            start = to_local(comp.decoded("DTSTART"))
            if "DTEND" in comp:
                end = to_local(comp.decoded("DTEND"))
            elif "DURATION" in comp:
                end = start + comp.decoded("DURATION")
            else:
                end = start if isinstance(start, dt.datetime) else start + dt.timedelta(days=1)
            if isinstance(start, dt.datetime) != isinstance(end, dt.datetime):
                end = start
            events.append(Event(str(comp.get("SUMMARY", "(sin título)")), start, end,
                                str(comp.get("LOCATION", "")), source))
    # Primero los de todo el día, luego por hora de inicio.
    events.sort(key=lambda e: (not e.all_day, sort_key(e), e.summary))
    return events


def sort_key(event):
    if event.all_day:
        return dt.datetime.combine(event.start, dt.time.min).astimezone()
    return event.start


class Popup(Gtk.Window):
    def __init__(self):
        super().__init__(title="gcal-popup")
        self.today = dt.date.today()
        self.selected = self.today
        self.year, self.month = self.today.year, self.today.month
        self.parsed = []      # [(Source, icalendar.Calendar)]
        self.month_events = []
        self.status_text = "Cargando…"
        self.no_sources = False

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
        refresh_btn.connect("clicked", lambda *_: self.load(force=True))
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
        open_btn = Gtk.Button(label="Abrir en Google 󰏌")
        open_btn.set_halign(Gtk.Align.END)
        open_btn.connect("clicked", self.open_google)
        root.pack_start(open_btn, False, False, 0)

        self.render()
        self.load()

    # ----- datos -----
    def load(self, force=False):
        self.set_status("Sincronizando…")
        threading.Thread(target=self._load_worker, args=(force,), daemon=True).start()

    def _parse(self, sources, errors):
        parsed = []
        for s in sources:
            path = cache_path(s.url)
            if path.exists():
                try:
                    parsed.append((s, icalendar.Calendar.from_ical(path.read_bytes())))
                except ValueError as e:
                    errors.append(f"{s.name}: caché ilegible ({e})")
        return parsed

    def _load_worker(self, force):
        sources = read_sources()
        if not sources:
            GLib.idle_add(self.apply_data, [], [], True)
            return
        errors = []
        if not force:  # pinta primero lo que haya en caché
            GLib.idle_add(self.apply_data, self._parse(sources, errors), [], False)
        for s in sources:
            age = cache_age(s.url)
            if force or age is None or age > MAX_AGE:
                try:
                    fetch(s)
                except (urllib.error.URLError, OSError, ValueError) as e:
                    errors.append(f"{s.name}: {getattr(e, 'reason', e)}")
        GLib.idle_add(self.apply_data, self._parse(sources, errors), errors, False)

    def apply_data(self, parsed, errors, no_sources):
        self.parsed = parsed
        self.no_sources = no_sources
        if no_sources:
            status = "Sin calendarios: pega tu dirección iCal secreta en " + str(CONFIG).replace(
                str(Path.home()), "~", 1)
        elif errors:
            status = "Error: " + "; ".join(errors)
        else:
            ages = [cache_age(s.url) for s, _ in parsed]
            oldest = max((a for a in ages if a is not None), default=None)
            status = "Sincronizado" if oldest is None else (
                f"Sincronizado hace {int(oldest // 60)} min" if oldest >= 60 else "Sincronizado ahora")
        self.set_status(status)
        self.render()
        return False

    def set_status(self, text):
        self.status.set_text(text)
        return False

    # ----- vista -----
    def grid_start(self):
        first = dt.date(self.year, self.month, 1)
        return first - dt.timedelta(days=first.weekday())  # lunes

    def render(self):
        self.title_label.set_text(f"{MONTHS[self.month - 1]} {self.year}")
        start = self.grid_start()
        end = start + dt.timedelta(days=41)
        try:
            self.month_events = expand(self.parsed, start, end)
        except (ValueError, TypeError) as e:
            self.month_events = []
            self.set_status(f"Error al expandir eventos: {e}")
        colors_by_day = {}
        for ev in self.month_events:
            first, last = ev.days()
            day = max(first, start)
            while day <= min(last, end):
                colors_by_day.setdefault(day, [])
                if ev.source.color not in colors_by_day[day]:
                    colors_by_day[day].append(ev.source.color)
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

    def render_day(self):
        d = self.selected
        self.day_heading.set_text(f"{WEEKDAYS[d.weekday()]}, {d.day} de {MONTHS[d.month - 1]}")
        for child in self.event_box.get_children():
            child.destroy()
        events = [e for e in self.month_events if e.days()[0] <= d <= e.days()[1]]
        if not events:
            self.event_box.pack_start(self.line("Sin eventos", "muted"), False, False, 0)
        multi = len({s.name for s, _ in self.parsed}) > 1
        for ev in events[:MAX_DAY_EVENTS]:
            row = Gtk.Box(spacing=8)
            dot = Gtk.Label()
            dot.set_markup(f"<span foreground='{ev.source.color}'>●</span>")
            dot.set_valign(Gtk.Align.START)
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            title = self.line(None)
            title.set_markup(f"<span foreground='#c8c8cc'>{html.escape(self.time_range(ev, d))}</span>  "
                             f"{html.escape(ev.summary)}")
            text.pack_start(title, False, False, 0)
            if ev.location:
                text.pack_start(self.line(ev.location, "muted"), False, False, 0)
            if multi:
                text.pack_start(self.line(ev.source.name, "muted"), False, False, 0)
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

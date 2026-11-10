"""TurboDM teması: Windows'un açık/koyu moduna kendiliğinden uyan, TurboDM mavisi vurgulu tasarım.

  * apply(app, mode)  → mode: "auto" (Windows ile aynı) | "light" | "dark"
  * icon(name)        → temaya göre renklenen çizgi simgeler (araç çubuğu, kategoriler, durumlar)
  * T                 → geçerli renkler (ör. T["accent"])
  * notifier.changed  → tema değişince yayınlanır (simgeler yeniden çizilir)
Windows ayarlardan açık/koyu değiştirildiğinde program açıkken de anında uyum sağlar.
"""
import math
from string import Template

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPalette, QPen, QPixmap

DARK = {
    "dark": True,
    "bg": "#0c1016", "side": "#10151d", "surface": "#151b24", "surface2": "#1b2330", "alt": "#18202a", "input": "#111720",
    "border": "#232c3a", "border_soft": "#1b2330", "hover": "#1c2533",
    "text": "#e9edf4", "muted": "#94a0b2", "track": "#242e3d", "scroll": "#334055",
    "accent": "#3b8cf0", "accent2": "#5aa6ff", "accent_hover": "#5199f3",
    "accent_soft": "#1d3a63", "accent_text": "#9cc8ff",
    "ok": "#3ccf7e", "warn": "#f0b44a", "bad": "#ff6b63",
    "caption": "#10151d",
}
LIGHT = {
    "dark": False,
    "bg": "#f3f5f9", "side": "#fafbfd", "surface": "#ffffff", "surface2": "#eef2f7", "alt": "#f8fafd", "input": "#ffffff",
    "border": "#dfe5ee", "border_soft": "#edf0f5", "hover": "#f1f5fa",
    "text": "#17202c", "muted": "#5a6779", "track": "#e3e9f2", "scroll": "#c3cddb",
    "accent": "#1f6fe0", "accent2": "#3b8cf0", "accent_hover": "#1a62c8",
    "accent_soft": "#d9e8fd", "accent_text": "#0f4fa8",
    "ok": "#1f9d57", "warn": "#c98a12", "bad": "#d93a32",
    "caption": "#fafbfd",
}

T = dict(DARK)
_mode = "auto"
_applying = False


class _Notifier(QObject):
    changed = Signal()


notifier = _Notifier()

QSS = Template("""
QMainWindow, QDialog { background: $bg; }
QWidget { color: $text; }
QToolTip { background: $surface2; color: $text; border: 1px solid $border; padding: 5px 8px; border-radius: 6px; }

QMenuBar { background: $side; border-bottom: 1px solid $border; padding: 3px 8px; }
QMenuBar::item { padding: 5px 10px; border-radius: 6px; background: transparent; }
QMenuBar::item:selected { background: $hover; }
QMenu { background: $surface; border: 1px solid $border; border-radius: 10px; padding: 6px; }
QMenu::item { padding: 7px 26px 7px 30px; border-radius: 6px; }
QMenu::icon { padding-left: 10px; }
QMenu::item:selected { background: $accent_soft; color: $accent_text; }
QMenu::item:disabled { color: $muted; }
QMenu::separator { height: 1px; background: $border; margin: 5px 8px; }

QFrame#sidebar { background: $side; border: none; }
QFrame#sideLine { background: $border; border: none; }
QToolButton#newDownload, QToolButton#newDownloadMenu { background: $accent; color: #ffffff; border: none; border-radius: 9px;
    font-size: 14px; font-weight: 600; padding: 9px 8px; }
QToolButton#newDownload:hover, QToolButton#newDownloadMenu:hover { background: $accent_hover; }
QToolButton#newDownloadMenu::menu-indicator, QToolButton#headMenu::menu-indicator { image: none; }
QToolButton#sideButton { background: transparent; border: none; border-radius: 8px; padding: 8px 6px; color: $text; }
QToolButton#sideButton:hover { background: $hover; color: $text; }
QFrame#sideSep { background: $border_soft; border: none; }
QToolButton#headButton, QToolButton#headMenu { background: $surface; border: 1px solid $border; border-radius: 8px;
    padding: 7px 12px; color: $text; }
QToolButton#headButton:hover, QToolButton#headMenu:hover { background: $hover; }
QToolButton#headButton:pressed, QToolButton#headMenu:pressed { background: $accent_soft; }
QToolButton#headButton:disabled { color: $muted; }
QLabel#pageTitle { font-size: 21px; font-weight: 600; }
QLabel#pageSub { color: $muted; }
QFrame#searchBox { background: $surface; border: 1px solid $border; border-radius: 8px; }
QFrame#searchBox[focus="true"] { border: 1px solid $accent; }
QLineEdit#searchEdit, QLineEdit#searchEdit:focus { background: transparent; border: none; padding: 0; }
QLabel#kbd { color: $muted; border: 1px solid $border; border-radius: 5px; padding: 0 5px; font-size: 11px; }
QFrame#speedPanel { background: $surface; border: 1px solid $border; border-radius: 12px; }
QFrame#queueCard { background: $surface2; border: none; border-radius: 10px; }
QLabel#panelCap { color: $muted; font-size: 12px; }
QLabel#panelBig { font-size: 26px; font-weight: 600; }
QLabel#panelUnit { color: $muted; font-size: 13px; }
QLabel#panelVal { font-size: 16px; font-weight: 600; }
QLabel#queueState { font-weight: 600; }
QLabel#queueWait { color: $muted; }
QPushButton#miniButton { padding: 4px 10px; min-height: 16px; min-width: 0; }
QFrame#listFrame { background: $surface; border: 1px solid $border; border-bottom: none;
    border-top-left-radius: 12px; border-top-right-radius: 12px; }

QTreeWidget#nav { background: transparent; border: none; padding: 0; outline: 0; }
QTreeWidget#nav::item { padding: 7px 6px; border-radius: 8px; margin: 1px 0; border: none; }
QTreeWidget#nav::item:hover { background: $hover; }
QTreeWidget#nav::item:selected { background: $accent_soft; color: $text; }

QTableWidget#list { background: $surface; alternate-background-color: $alt; border: none; gridline-color: transparent;
    selection-background-color: $accent_soft; selection-color: $text; outline: 0; }
QTableWidget#list::item { border: none; border-bottom: 1px solid $border_soft; padding: 0 6px; }
QTableWidget#list::item:selected { background: $accent_soft; color: $text; }
QHeaderView { background: $surface; }
QHeaderView::section { background: $surface; color: $muted; border: none; border-bottom: 1px solid $border;
    padding: 7px 12px; font-weight: 600; }
QTableCornerButton::section { background: $surface; border: none; }

QStatusBar { background: $side; color: $muted; border-top: 1px solid $border; }
QStatusBar QLabel { color: $muted; padding: 2px 8px; }
QStatusBar::item { border: none; }

QPushButton { background: $surface2; color: $text; border: 1px solid $border; border-radius: 8px; padding: 6px 16px; min-height: 18px; }
QPushButton:hover { border-color: $accent; background: $hover; }
QPushButton:pressed { background: $accent_soft; }
QPushButton:default { background: $accent; color: #ffffff; border: 1px solid $accent; font-weight: 600; }
QPushButton:default:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton:disabled { color: $muted; background: $surface; border-color: $border_soft; }
QPushButton:checked { background: $accent_soft; border-color: $accent; }
QPushButton#browse { padding: 4px 0; min-width: 0; font-weight: 700; }

QLineEdit { background: $input; color: $text; border: 1px solid $border; border-radius: 7px; padding: 5px 8px;
    selection-background-color: $accent; selection-color: #ffffff; }
QLineEdit:focus { border: 1px solid $accent; }
QLineEdit:read-only { background: $surface2; }

QProgressBar { background: $track; border: none; border-radius: 7px; text-align: center; color: $text; min-height: 16px; font-weight: 600; }
QProgressBar::chunk { border-radius: 7px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 $accent, stop:1 $accent2); }

QTabWidget::pane { border: 1px solid $border; border-radius: 10px; background: $surface; top: -1px; }
QTabBar::tab { background: transparent; color: $muted; padding: 8px 16px; border: none; border-bottom: 2px solid transparent; margin-right: 2px; }
QTabBar::tab:selected { color: $text; border-bottom: 2px solid $accent; font-weight: 600; }
QTabBar::tab:hover:!selected { color: $text; }

QGroupBox { border: 1px solid $border; border-radius: 10px; margin-top: 16px; padding: 12px 10px 10px 10px; background: $surface; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; color: $muted; font-weight: 600; }

QTreeWidget, QListWidget, QTextBrowser, QTableWidget { background: $surface; border: 1px solid $border; border-radius: 8px; }
QTextBrowser { padding: 6px; }

QScrollBar:vertical { background: transparent; width: 11px; margin: 2px; }
QScrollBar::handle:vertical { background: $scroll; border-radius: 4px; min-height: 30px; }
QScrollBar:horizontal { background: transparent; height: 11px; margin: 2px; }
QScrollBar::handle:horizontal { background: $scroll; border-radius: 4px; min-width: 30px; }
QScrollBar::handle:hover { background: $muted; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
""")


# ------------------------------------------------------------------ uygulama
def _is_system_dark(app):
    try:
        return app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:  # eski Qt: pencere renginden anla
        return app.palette().color(QPalette.Window).lightness() < 128


def _palette(t):
    p = QPalette()
    c = lambda k: QColor(t[k])  # noqa: E731
    for group in (QPalette.Active, QPalette.Inactive, QPalette.Disabled):
        p.setColor(group, QPalette.Window, c("bg"))
        p.setColor(group, QPalette.WindowText, c("text"))
        p.setColor(group, QPalette.Base, c("input"))
        p.setColor(group, QPalette.AlternateBase, c("alt"))
        p.setColor(group, QPalette.Text, c("text"))
        p.setColor(group, QPalette.Button, c("surface2"))
        p.setColor(group, QPalette.ButtonText, c("text"))
        p.setColor(group, QPalette.ToolTipBase, c("surface2"))
        p.setColor(group, QPalette.ToolTipText, c("text"))
        p.setColor(group, QPalette.PlaceholderText, c("muted"))
        p.setColor(group, QPalette.Highlight, c("accent"))
        p.setColor(group, QPalette.HighlightedText, QColor("#ffffff"))
        p.setColor(group, QPalette.Link, c("accent"))
        p.setColor(group, QPalette.BrightText, c("bad"))
        p.setColor(group, QPalette.Light, c("border") if t["dark"] else QColor("#ffffff"))
        p.setColor(group, QPalette.Midlight, c("border_soft"))
        p.setColor(group, QPalette.Mid, c("border"))
        p.setColor(group, QPalette.Dark, c("bg") if t["dark"] else c("border"))
        p.setColor(group, QPalette.Shadow, QColor("#000000"))
        if hasattr(QPalette, "Accent"):
            p.setColor(group, QPalette.Accent, c("accent"))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, c("muted"))
    p.setColor(QPalette.Disabled, QPalette.Highlight, c("border"))
    return p


def apply(app, mode=None):
    """Temayı uygula. mode=None: son seçilen mod. Windows modu değişince kendiliğinden yeniden çağrılır."""
    global _mode, _applying
    if _applying:
        return
    _applying = True
    try:
        if mode:
            _mode = mode
        hints = app.styleHints()
        if hasattr(hints, "setColorScheme"):  # Qt 6.8+: pencere başlıkları da aynı moda geçer
            want = {"light": Qt.ColorScheme.Light, "dark": Qt.ColorScheme.Dark}.get(_mode, Qt.ColorScheme.Unknown)
            hints.setColorScheme(want)
        dark = _is_system_dark(app) if _mode == "auto" else _mode == "dark"
        T.clear()
        T.update(DARK if dark else LIGHT)
        app.setPalette(_palette(T))
        app.setStyleSheet(QSS.substitute({k: v for k, v in T.items() if isinstance(v, str)}))
        _icon_cache.clear()
        for w in app.topLevelWidgets():
            if w.isWindow() and w.isVisible():
                style_titlebar(w)
    finally:
        _applying = False
    notifier.changed.emit()


def install(app, mode="auto"):
    """Uygulama başlarken bir kez: temayı uygula, Windows modu değişince izle, pencere başlıklarını renklendir."""
    if mode != _mode or not getattr(app, "_tdm_title_filter", None):
        apply(app, mode)
    if not getattr(app, "_tdm_scheme_watch", False):
        app._tdm_scheme_watch = True
        try:
            app.styleHints().colorSchemeChanged.connect(lambda *_: _mode == "auto" and apply(app))
        except AttributeError:
            pass
    if not getattr(app, "_tdm_title_filter", None):
        app._tdm_title_filter = _TitleBarFilter(app)
        app.installEventFilter(app._tdm_title_filter)


def mode():
    return _mode


# ------------------------------------------------------------------ Windows başlık çubuğu
def _colorref(hex_color):
    c = QColor(hex_color)
    return c.red() | (c.green() << 8) | (c.blue() << 16)


def style_titlebar(w):
    """Windows 11: pencere başlığı temanın zemin rengini alır (ayrık duran gri/siyah başlık yerine bütünlük).
    Windows 10'da yalnızca koyu/açık başlık; desteklenmezse sessizce geçilir."""
    try:
        import ctypes
        from ctypes import wintypes
        hwnd = wintypes.HWND(int(w.winId()))
        dwm = ctypes.windll.dwmapi
        on = ctypes.c_int(1 if T["dark"] else 0)
        dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(on), ctypes.sizeof(on))   # koyu mod başlık
        cap = ctypes.c_uint(_colorref(T["caption"]))
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(cap), ctypes.sizeof(cap))  # başlık rengi (Win11)
        txt = ctypes.c_uint(_colorref(T["text"]))
        dwm.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(txt), ctypes.sizeof(txt))  # başlık yazısı (Win11)
    except Exception:  # noqa: BLE001 (Windows dışı ya da eski sürüm)
        pass


def center_on_screen(w):
    """Pencereyi farenin bulunduğu ekranın tam ortasına koy (görev çubuğu hariç alan)."""
    from PySide6.QtGui import QCursor, QGuiApplication
    scr = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
    if not scr:
        return
    g = scr.availableGeometry()
    caption = 32  # Windows başlık çubuğu: pencere çerçevesiyle birlikte ortalansın
    x = g.x() + (g.width() - w.width()) // 2
    y = g.y() + (g.height() - w.height() - caption) // 2 + caption
    w.move(max(g.x(), x), max(g.y() + caption, y))


class _TitleBarFilter(QObject):
    """Her pencere açılırken: başlık çubuğunu temaya göre renklendir; yeni açılan pencereleri (indirme,
    seçenekler, uyarılar…) ilk açılışta ekranın ortasına al."""

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Show and getattr(obj, "isWindow", None) and obj.isWindow():
            style_titlebar(obj)
            from PySide6.QtWidgets import QDialog
            if isinstance(obj, QDialog) and not obj.property("tdm_centered"):
                obj.setProperty("tdm_centered", True)
                center_on_screen(obj)
        return False


# ------------------------------------------------------------------ simgeler
_icon_cache = {}


def _pen(p, color, w=5.0):
    pen = QPen(QColor(color), w)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)


def _poly(p, pts, close=False):
    path = QPainterPath(QPointF(*pts[0]))
    for x, y in pts[1:]:
        path.lineTo(x, y)
    if close:
        path.closeSubpath()
    p.drawPath(path)


def _fill(p, color):
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))


def _draw(name, p, fg, ac):
    """64x64 ızgarada çizgi simgeler. fg: ana renk, ac: vurgu rengi."""
    if name == "plus":  # tek renk artı (dolu düğme üstünde)
        _pen(p, ac, 7)
        p.drawLine(32, 12, 32, 52)
        p.drawLine(12, 32, 52, 32)
    elif name == "folder":
        _pen(p, fg)
        path = QPainterPath(QPointF(8, 16))
        path.lineTo(26, 16)
        path.lineTo(32, 23)
        path.lineTo(56, 23)
        path.lineTo(56, 52)
        path.lineTo(8, 52)
        path.closeSubpath()
        p.drawPath(path)
    elif name == "search":  # büyüteç (tek renk: vurgu rengi)
        _pen(p, ac, 6)
        p.drawEllipse(QPointF(27, 27), 16, 16)
        p.drawLine(39, 39, 54, 54)
    elif name == "more":  # üç nokta
        _fill(p, fg)
        for x in (14, 32, 50):
            p.drawEllipse(QPointF(x, 32), 5, 5)
    elif name == "chevron":  # açılır menü oku
        _pen(p, ac, 7)
        _poly(p, [(14, 24), (32, 42), (50, 24)])
    elif name == "add":  # bağlantı + artı
        _pen(p, fg)
        p.drawRoundedRect(QRectF(8, 8, 48, 48), 14, 14)
        _pen(p, ac, 6)
        p.drawLine(32, 20, 32, 44)
        p.drawLine(20, 32, 44, 32)
    elif name == "torrent":  # sayfa + aşağı ok
        _pen(p, fg)
        _poly(p, [(14, 6), (38, 6), (52, 20), (52, 58), (14, 58)], close=True)
        _poly(p, [(38, 6), (38, 20), (52, 20)])
        _pen(p, ac, 5.5)
        p.drawLine(33, 26, 33, 48)
        _poly(p, [(24, 40), (33, 49), (42, 40)])
    elif name == "magnet":
        _pen(p, fg, 9)
        path = QPainterPath(QPointF(16, 8))
        path.lineTo(16, 34)
        path.arcTo(QRectF(16, 18, 32, 32), 180, 180)
        path.lineTo(48, 8)
        p.drawPath(path)
        _pen(p, ac, 9)
        p.drawLine(16, 8, 16, 16)
        p.drawLine(48, 8, 48, 16)
    elif name == "play":  # içi boş üçgen
        _pen(p, ac, 6)
        _poly(p, [(21, 13), (51, 32), (21, 51)], close=True)
    elif name == "pause":  # iki ince dikey çizgi
        _pen(p, fg, 6.5)
        p.drawLine(23, 14, 23, 50)
        p.drawLine(41, 14, 41, 50)
    elif name == "stop":  # içi boş yuvarlak köşeli kare
        _pen(p, fg, 6)
        p.drawRoundedRect(QRectF(14, 14, 36, 36), 8, 8)
    elif name in ("trash", "trash_done"):
        _pen(p, T["bad"] if name == "trash" else fg)
        p.drawLine(10, 16, 54, 16)
        _poly(p, [(24, 16), (26, 8), (38, 8), (40, 16)])
        _poly(p, [(15, 16), (18, 56), (46, 56), (49, 16)])
        if name == "trash":
            p.drawLine(27, 26, 27, 46)
            p.drawLine(37, 26, 37, 46)
        else:
            _pen(p, ac, 5.5)
            _poly(p, [(23, 36), (30, 43), (42, 28)])
    elif name == "settings":
        _pen(p, fg, 5)
        p.drawEllipse(QPointF(32, 32), 9, 9)
        for i in range(8):
            a = math.radians(i * 45)
            p.drawLine(QPointF(32 + 15 * math.cos(a), 32 + 15 * math.sin(a)),
                       QPointF(32 + 24 * math.cos(a), 32 + 24 * math.sin(a)))
        p.drawEllipse(QPointF(32, 32), 18, 18)
    elif name == "clock":
        _pen(p, fg)
        p.drawEllipse(QPointF(32, 32), 24, 24)
        _pen(p, ac, 5.5)
        _poly(p, [(32, 18), (32, 32), (42, 38)])
    elif name in ("queue_start", "queue_stop", "queue", "st_queue", "list"):
        _pen(p, fg)
        for y in (16, 30, 44):
            p.drawLine(8, y, 56 if name == "list" else 30, y)
        if name in ("queue", "st_queue"):  # çizgiler + küçük içi boş oynat üçgeni
            _pen(p, fg, 5)
            _poly(p, [(38, 24), (56, 36), (38, 48)], close=True)
        elif name == "queue_start":
            _fill(p, ac)
            path = QPainterPath(QPointF(38, 24))
            path.lineTo(58, 36)
            path.lineTo(38, 48)
            path.closeSubpath()
            p.drawPath(path)
        elif name == "queue_stop":
            _fill(p, ac)
            p.drawRoundedRect(QRectF(38, 26, 20, 20), 4, 4)
    elif name == "quit":
        _pen(p, fg)
        p.drawArc(QRectF(10, 12, 44, 44), 120 * 16, -300 * 16)
        _pen(p, ac, 5.5)
        p.drawLine(32, 6, 32, 30)
    elif name == "refresh":
        _pen(p, fg)
        p.drawArc(QRectF(12, 12, 40, 40), 60 * 16, 270 * 16)
        _pen(p, ac)
        _poly(p, [(44, 6), (46, 18), (34, 20)])
    # ---- kategoriler
    elif name == "all":  # liste: üç yatay çizgi
        _pen(p, fg, 5.5)
        for y in (18, 32, 46):
            p.drawLine(10, y, 54, y)
    elif name == "compressed":
        _pen(p, fg)
        p.drawRoundedRect(QRectF(10, 8, 44, 48), 7, 7)
        _pen(p, ac, 5)
        for y in (14, 22, 30):
            p.drawLine(28, y, 36, y + 4)
        p.drawRoundedRect(QRectF(26, 38, 12, 10), 2, 2)
    elif name in ("document", "general"):
        _pen(p, fg)
        _poly(p, [(14, 6), (38, 6), (52, 20), (52, 58), (14, 58)], close=True)
        _poly(p, [(38, 6), (38, 20), (52, 20)])
        if name == "document":
            _pen(p, ac, 4.5)
            for y in (30, 39, 48):
                p.drawLine(22, y, 44, y)
    elif name == "music":
        _pen(p, fg)
        _poly(p, [(26, 46), (26, 12), (52, 6), (52, 40)])
        _fill(p, ac)
        p.drawEllipse(QPointF(19, 47), 8, 7)
        p.drawEllipse(QPointF(45, 41), 8, 7)
    elif name == "program":
        _pen(p, fg)
        p.drawRoundedRect(QRectF(6, 10, 52, 44), 7, 7)
        p.drawLine(6, 22, 58, 22)
        _fill(p, ac)
        for x in (13, 21, 29):
            p.drawEllipse(QPointF(x, 16), 2.6, 2.6)
    elif name == "video":
        _pen(p, fg)
        p.drawRoundedRect(QRectF(6, 12, 52, 40), 8, 8)
        _fill(p, ac)
        path = QPainterPath(QPointF(26, 22))
        path.lineTo(42, 32)
        path.lineTo(26, 42)
        path.closeSubpath()
        p.drawPath(path)
    elif name == "unfinished":
        _pen(p, fg)
        p.drawArc(QRectF(8, 8, 48, 48), 90 * 16, -270 * 16)
        _pen(p, ac)
        p.drawArc(QRectF(8, 8, 48, 48), 90 * 16, 90 * 16)
        _pen(p, fg)
        _poly(p, [(32, 20), (32, 32), (40, 38)])
    elif name == "finished":
        _pen(p, fg)
        p.drawEllipse(QPointF(32, 32), 24, 24)
        _pen(p, ac, 6)
        _poly(p, [(20, 33), (28, 41), (44, 23)])
    # ---- durumlar (tek renk, dolu)
    elif name == "st_down":
        _fill(p, ac)
        p.drawEllipse(QPointF(32, 32), 26, 26)
        _pen(p, "#ffffff", 6)
        p.drawLine(32, 18, 32, 44)
        _poly(p, [(21, 34), (32, 45), (43, 34)])
    elif name == "st_up":
        _fill(p, ac)
        p.drawEllipse(QPointF(32, 32), 26, 26)
        _pen(p, "#ffffff", 6)
        p.drawLine(32, 20, 32, 46)
        _poly(p, [(21, 30), (32, 19), (43, 30)])
    elif name == "st_done":  # içi boş daire + onay işareti
        _pen(p, ac, 5.5)
        p.drawEllipse(QPointF(32, 32), 24, 24)
        _poly(p, [(20, 33), (28, 41), (44, 24)])
    elif name == "st_error":  # içi boş daire + ünlem
        _pen(p, ac, 5.5)
        p.drawEllipse(QPointF(32, 32), 24, 24)
        p.drawLine(32, 19, 32, 35)
        _fill(p, ac)
        p.drawEllipse(QPointF(32, 44), 3.4, 3.4)
    elif name == "st_pause":
        _pen(p, fg, 5)
        p.drawEllipse(QPointF(32, 32), 24, 24)
        _fill(p, fg)
        p.drawRoundedRect(QRectF(23, 21, 6, 22), 2, 2)
        p.drawRoundedRect(QRectF(35, 21, 6, 22), 2, 2)
    elif name == "st_wait":
        _pen(p, fg, 5)
        p.drawEllipse(QPointF(32, 32), 24, 24)
        _pen(p, ac, 5.5)
        p.drawArc(QRectF(8, 8, 48, 48), 90 * 16, -110 * 16)


STATUS_ICON = {"downloading": ("st_down", "accent"), "connecting": ("st_wait", "accent"),
               "completed": ("st_done", "ok"), "error": ("st_error", "bad"), "seeding": ("st_up", "ok"),
               "queued": ("st_queue", "muted"), "stopped": ("st_pause", "accent"),
               "converting": ("st_wait", "accent")}


def icon(name, accent="accent"):
    """Temaya göre renklenmiş simge (önbellekli; tema değişince yeniden çizilir)."""
    key = (name, accent)
    if key in _icon_cache:
        return _icon_cache[key]
    ic = QIcon()
    fg = T["muted"] if name.startswith("st_") else T["text"]
    for px in (16, 20, 24, 32, 48, 64):
        pm = QPixmap(px, px)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.scale(px / 64.0, px / 64.0)
        _draw(name, p, fg, T.get(accent, accent))
        p.end()
        ic.addPixmap(pm)
    _icon_cache[key] = ic
    return ic


def status_icon(status):
    name, acc = STATUS_ICON.get(status, ("st_pause", "accent"))
    return icon(name, acc)

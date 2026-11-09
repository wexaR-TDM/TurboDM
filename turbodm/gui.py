"""PySide6 arayüzü: IDM tarzı ana pencere, indirme durumu penceresi, ayarlar, zamanlayıcı."""
import os
import re
import subprocess
import threading
import time
import urllib.parse
import uuid
from datetime import datetime

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRect, QRectF, QSize, QTime, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QDesktopServices, QFont, QFontMetrics, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
    QLineEdit, QMainWindow, QMenu, QMenuBar, QMessageBox, QPlainTextEdit, QPushButton, QSizePolicy, QSpinBox, QStyle,
    QSystemTrayIcon, QTableWidget, QTableWidgetItem, QTabWidget, QTimeEdit, QToolButton, QToolTip,
    QGroupBox, QProgressBar, QTextBrowser, QStyledItemDelegate, QStyleOptionViewItem,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from . import convert
from . import engine
from . import power
from . import hls
from . import server
from . import theme
from . import updater
from . import ytdlp
from .appinfo import UPDATE_REPO, VERSION
from . import torrent as tmod
from . import winassoc
from .engine import fetch_torrent, filename_from_url, looks_like_torrent, probe, sanitize_filename
from .manager import CATCH_EXTS, CATEGORIES, TORRENT_DIR, Manager, category_for
from . import i18n
from .i18n import _t

APP_NAME = "TurboDM"

STATUS_TEXT = {}


@i18n.on_change
def _status_texts():
    STATUS_TEXT.update({
    "stopped": _t("Durduruldu"), "queued": _t("Kuyrukta"), "connecting": _t("Bağlanıyor…"),
    "downloading": _t("İndiriliyor"), "completed": _t("Tamamlandı"), "error": _t("Hata"),
    "seeding": _t("Paylaşılıyor"), "converting": _t("Dönüştürülüyor…"),
    })


# ------------------------------------------------------------------ biçimlendirme
def fmt_size(n):
    if n is None:
        return _t("Bilinmiyor")
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.2f} {unit}"
        n /= 1024


def fmt_pct(value, decimals=1):
    """Yüzde: Türkçede "%62", diğer dillerde "62%" (kalıp çeviriden gelir)."""
    return _t("%{0}").format(f"{value:.{decimals}f}")


def fmt_speed(b):
    return fmt_size(b) + "/s" if b and b > 0 else ""


def fmt_time(s):
    if s is None:
        return ""
    s = int(s)
    if s >= 86400:
        return _t("{0}g {1}sa").format(s // 86400, s % 86400 // 3600)
    if s >= 3600:
        return _t("{0}sa {1}dk").format(s // 3600, s % 3600 // 60)
    if s >= 60:
        return _t("{0}dk {1}sn").format(s // 60, s % 60)
    return _t("{0}sn").format(s)


def make_icon(color="#1e6fd9"):
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    p.drawEllipse(2, 2, 60, 60)
    p.setBrush(QColor("white"))
    path = QPainterPath()
    path.moveTo(25, 12); path.lineTo(39, 12); path.lineTo(39, 32); path.lineTo(49, 32)
    path.lineTo(32, 50); path.lineTo(15, 32); path.lineTo(25, 32); path.closeSubpath()
    p.drawPath(path)
    p.end()
    return QIcon(pm)


def load_icon():
    """Kurulu sürümde exe'nin yanındaki, geliştirmede installer/ klasöründeki simge."""
    from .appinfo import install_dir
    for p in (os.path.join(install_dir(), "turbodm.ico"),
              os.path.join(install_dir(), "installer", "turbodm.ico")):
        if os.path.isfile(p):
            return QIcon(p)
    return make_icon()


def apply_theme(app, mode="auto"):
    """TurboDM teması (theme.py): Windows'un açık/koyu moduna kendiliğinden uyar; vurgu her zaman TurboDM
    mavisi (aksi hâlde Qt, Windows'un vurgu rengini, ör. kırmızıyı alırdı)."""
    theme.install(app, mode)


def bring_to_front(w):
    """Pencereyi ekranın önüne getir. Windows, arka plandaki bir programın (TurboDM tarayıcıdan tetiklenince
    arka plandadır) pencereyi öne almasını engeller ("odak çalma" koruması); yalnızca görev çubuğunda
    yanıp söner. Ön plandaki iş parçacığına geçici olarak bağlanmak ve pencereyi kısa süre 'her zaman üstte'
    yapmak bu korumayı yasal yoldan aşar."""
    w.show()
    w.setWindowState((w.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
    w.raise_()
    w.activateWindow()
    if os.name != "nt":
        return
    try:
        import ctypes
        u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
        hwnd = int(w.winId())
        fg = u32.GetForegroundWindow()
        fg_tid = u32.GetWindowThreadProcessId(fg, None)
        me = k32.GetCurrentThreadId()
        attached = fg_tid and fg_tid != me and u32.AttachThreadInput(me, fg_tid, True)
        try:
            HWND_TOPMOST, HWND_NOTOPMOST, FLAGS = -1, -2, 0x0001 | 0x0002 | 0x0040  # NOSIZE|NOMOVE|SHOWWINDOW
            u32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, FLAGS)
            u32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, FLAGS)
            u32.BringWindowToTop(hwnd)
            u32.SetForegroundWindow(hwnd)
        finally:
            if attached:
                u32.AttachThreadInput(me, fg_tid, False)
    except Exception:  # noqa: BLE001
        pass


def standalone_window(w):
    """Pencereyi bağımsız uygulama penceresi gibi yap: başlıkta küçült / ekranı kapla / kapat düğmeleri,
    görev çubuğunda kendi düğmesi (küçültülünce oraya iner, oradan geri açılır)."""
    w.setWindowFlags(Qt.Window | Qt.WindowTitleHint | Qt.WindowSystemMenuHint
                     | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
    if os.name != "nt":
        return
    try:
        import ctypes
        u32 = ctypes.windll.user32
        hwnd = int(w.winId())  # yerel pencere gösterilmeden önce oluşturulur
        GWL_EXSTYLE, WS_EX_APPWINDOW = -20, 0x00040000
        u32.SetWindowLongW(hwnd, GWL_EXSTYLE, u32.GetWindowLongW(hwnd, GWL_EXSTYLE) | WS_EX_APPWINDOW)
    except Exception:  # noqa: BLE001
        pass


def open_path(path):
    if os.path.exists(path):
        os.startfile(path)  # noqa: S606 (Windows)


def open_folder(path):
    if os.path.isfile(path):
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    else:
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        if os.path.isdir(folder):
            os.startfile(folder)


def is_dash(url, content_type=""):
    """DASH (MPEG-DASH, .mpd) video akışı mı?"""
    return ((content_type or "").split(";")[0].strip().lower() == "application/dash+xml"
            or urllib.parse.urlparse(url).path.lower().endswith(".mpd"))


def is_magnet(text):
    return text.strip().lower().startswith("magnet:?")


# ------------------------------------------------------------------ segment çubuğu
class SegmentBar(QWidget):
    """IDM'nin ünlü parçalı ilerleme çubuğu: her bağlantının indirdiği bölge ayrı görünür."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(24)
        self.size = 0
        self.segs = []

    def set_data(self, size, segs):
        self.size, self.segs = size or 0, segs
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        clip = QPainterPath()
        clip.addRoundedRect(r, 6, 6)
        p.setClipPath(clip)
        p.fillRect(r, QColor(theme.T["track"]))   # koyu/açık temaya uyumlu zemin
        if self.size:
            w = r.width()
            for a, b, pos in self.segs:
                x0 = r.x() + a / self.size * w
                x1 = r.x() + min(pos, b + 1) / self.size * w
                if x1 > x0:
                    p.fillRect(QRectF(x0, r.y(), max(1.0, x1 - x0), r.height()), QColor(theme.T["accent"]))
            p.setPen(QPen(QColor(theme.T["surface"]), 1.5))   # bağlantılar arası ince ayraç
            for a, b, pos in self.segs:
                if a > 0:
                    x = r.x() + a / self.size * w
                    p.drawLine(QPointF(x, r.y()), QPointF(x, r.bottom()))
        p.setClipping(False)
        p.setPen(QColor(theme.T["border"]))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, 6, 6)


class Bridge(QObject):
    probed = Signal(object, object)
    hls = Signal(object, object)
    video = Signal(object, object)
    done = Signal(object, object)       # genel arka plan işi sonucu
    progress = Signal(int, int)


class TorrentFilesTree(QTreeWidget):
    """Torrent içindeki dosyalar: klasör ağacı + onay kutuları (indirilecekleri seç)."""
    changed = Signal()

    def __init__(self, with_progress=False, parent=None):
        super().__init__(parent)
        self.setHeaderLabels([_t("Dosya"), _t("Boyut")] + ([_t("İlerleme")] if with_progress else []))
        self.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.header().setStretchLastSection(False)
        self.leaves = []
        self._building = False
        self.itemChanged.connect(lambda *_: None if self._building else self.changed.emit())

    def populate(self, files, priorities=None):
        """files: [(yol, boyut, dolgu_mu), ...]  priorities: [0..7] (0 = indirme)"""
        self._building = True
        self.clear()
        self.leaves, self.pads, folders = [], [], {}
        for i, (path, size, pad) in enumerate(files):
            self.pads.append(pad)
            if pad:
                continue
            parts = path.replace("\\", "/").split("/")
            parent = self.invisibleRootItem()
            for d in range(len(parts) - 1):
                key = "/".join(parts[:d + 1])
                if key not in folders:
                    f = QTreeWidgetItem([parts[d], ""])
                    f.setFlags(f.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
                    f.setCheckState(0, Qt.Checked)
                    f.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
                    parent.addChild(f)
                    folders[key] = f
                parent = folders[key]
            leaf = QTreeWidgetItem([parts[-1], fmt_size(size)])
            leaf.setFlags(leaf.flags() | Qt.ItemIsUserCheckable)
            on = priorities is None or i >= len(priorities) or priorities[i] > 0
            leaf.setCheckState(0, Qt.Checked if on else Qt.Unchecked)
            parent.addChild(leaf)
            self.leaves.append((leaf, size))
        self.expandAll()
        self._building = False

    def priorities(self):
        """Tüm dosya indeksleri için öncelik listesi (dolgu dosyaları dahil)."""
        it = iter(self.leaves)
        return [4 if pad or next(it)[0].checkState(0) == Qt.Checked else 0 for pad in self.pads]

    def any_selected(self):
        return any(leaf.checkState(0) == Qt.Checked for leaf, _ in self.leaves)

    def selected_size(self):
        return sum(s for leaf, s in self.leaves if leaf.checkState(0) == Qt.Checked)

    def set_all(self, on):
        self._building = True
        for leaf, _ in self.leaves:
            leaf.setCheckState(0, Qt.Checked if on else Qt.Unchecked)
        self._building = False
        self.changed.emit()

    def set_progress(self, done_list):
        done_list = [d for d, pad in zip(done_list, self.pads) if not pad]
        for (leaf, size), done in zip(self.leaves, done_list):
            txt = fmt_pct((done / size * 100) if size else 100, 1)
            if leaf.text(2) != txt:
                leaf.setText(2, txt)


# ------------------------------------------------------------------ dosya bilgisi
class FileInfoDialog(QDialog):
    """IDM'deki 'İndirme Dosyası Bilgisi' penceresi."""

    def __init__(self, win, url, headers=None, suggested=None, cookies=None, video_info=None, preselect=None):
        """video_info/preselect: tarayıcıdaki kalite menüsünden gelindiyse hazır bilgi ve seçilen biçim
        (yeniden sorgulanmaz; kalite ve uzantı seçili gelir, kullanıcı yalnızca yeri onaylar)."""
        super().__init__(win)
        self.win, self.mgr = win, win.mgr
        self.url, self.headers = url, headers or {}
        self.cookies = cookies or []     # tarayıcı eklentisinden (YouTube oturumu vb.)
        self.video_info = None           # yt-dlp ile bulunan site videosu
        self.info = {"size": None, "resumable": True}
        self.user_edited = False
        self.setWindowTitle(_t("İndirme Dosyası Bilgisi"))
        self.setMinimumWidth(560)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.url_edit = QLineEdit(url)
        self.cat = QComboBox()
        for key, (disp, _, _) in CATEGORIES.items():
            if key != "torrent":
                self.cat.addItem(disp, key)
        self.path_edit = QLineEdit()
        browse = QPushButton("…")
        browse.setObjectName("browse")
        browse.setFixedWidth(32)
        browse.clicked.connect(self._browse)
        prow = QHBoxLayout()
        prow.addWidget(self.path_edit)
        prow.addWidget(browse)
        self.desc = QLineEdit()
        self.size_lbl = QLabel(_t("Sorgulanıyor…"))
        self.size_lbl.setWordWrap(True)
        self.quality = QComboBox()   # yalnızca HLS videolarda görünür
        self.hls_info = None
        self.fmt = QComboBox()       # indirme bitince dönüştürme (video/ses)
        for key, (text, _) in convert.FORMATS.items():
            self.fmt.addItem(text, key)

        form = QFormLayout()
        self.form = form
        form.addRow(_t("Adres (URL):"), self.url_edit)
        form.addRow(_t("Kalite:"), self.quality)
        form.addRow(_t("Biçim:"), self.fmt)
        form.addRow(_t("Kategori:"), self.cat)
        form.addRow(_t("Kayıt klasörü:"), prow)
        form.addRow(_t("Açıklama:"), self.desc)
        form.addRow(_t("Boyut:"), self.size_lbl)
        form.setRowVisible(self.quality, False)
        form.setRowVisible(self.fmt, False)

        b_start = QPushButton(_t("İndirmeyi Başlat"))
        b_start.setDefault(True)
        b_later = QPushButton(_t("Sonra İndir (kuyruğa ekle)"))
        b_cancel = QPushButton(_t("İptal"))
        b_start.clicked.connect(lambda: self._go(True))
        b_later.clicked.connect(lambda: self._go(False))
        b_cancel.clicked.connect(self.reject)
        self.go_buttons = (b_later, b_start)
        brow = QHBoxLayout()
        brow.addStretch()
        for b in (b_later, b_start, b_cancel):
            brow.addWidget(b)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addLayout(brow)

        name = sanitize_filename(suggested) if suggested else (filename_from_url(url) or "download")
        self._set_name(name)
        self.path_edit.textEdited.connect(lambda _: setattr(self, "user_edited", True))
        self.cat.currentIndexChanged.connect(self._cat_changed)

        self.bridge = Bridge()
        self.bridge.probed.connect(self._on_probe)
        self.bridge.hls.connect(self._on_hls)
        self.bridge.video.connect(self._on_video)
        self.quality.currentIndexChanged.connect(self._quality_changed)
        if video_info:
            self._on_video(video_info, None)
            i = next((i for i in range(self.quality.count())
                      if self.quality.itemData(i).get("format") == preselect), -1)
            if i >= 0:
                self.quality.setCurrentIndex(i)
        elif ytdlp.is_youtube(url):
            self._start_video()
        elif hls.is_hls(url):
            self._start_hls()
        elif is_dash(url):
            self._start_video()  # DASH (.mpd): yt-dlp akışı indirip birleştirir
        else:
            threading.Thread(target=self._probe, daemon=True).start()

    # ---- Site videosu (YouTube vb.) — yt-dlp
    def _start_video(self, fallback_info=None):
        if not ytdlp.available():
            self.size_lbl.setText(_t("Site videoları için gereken yt-dlp bulunamadı."))
            return
        self._fallback = fallback_info
        self.size_lbl.setText(_t("Video inceleniyor…") if ytdlp.is_youtube(self.url)
                              else _t("Sayfadaki video aranıyor…"))
        # inceleme bitene kadar indirme başlatılamaz: yoksa video yerine sitenin web sayfası iner
        for b in self.go_buttons:
            b.setEnabled(False)

        def work():
            try:
                self.bridge.video.emit(ytdlp.inspect(self.url, self.mgr.ffmpeg(), self.cookies, self.headers), None)
            except Exception as e:  # noqa: BLE001
                self.bridge.video.emit(None, str(e))
        threading.Thread(target=work, daemon=True).start()

    def _on_video(self, info, err):
        if err or not info or not info["choices"]:
            fb = getattr(self, "_fallback", None)
            if fb:  # video yok: normal sayfa/dosya olarak indir
                self._apply_probe(fb)
                for b in self.go_buttons:
                    b.setEnabled(True)
            else:  # video sitesi/akışı ama video alınamadı: sayfanın kendisi indirilmesin, düğmeler kapalı kalır
                self.size_lbl.setText(_t("Video bilgisi alınamadı: {0}").format(err or _t('indirilebilir biçim yok')))
            return
        for b in self.go_buttons:
            b.setEnabled(True)
        self.video_info = info
        self._update_format_row()
        self.quality.blockSignals(True)
        self.quality.clear()
        default = 0
        for i, c in enumerate(info["choices"]):
            self.quality.addItem(c["label"], c)
            if c.get("height") and c["height"] <= 1080 and default == 0 and info["choices"][0]["height"] > 1080:
                default = i  # varsayılan: 1080p ya da altındaki en iyi kalite (her oynatıcıda açılır)
        pre = getattr(self, "_preselect", None)  # tarayıcı menüsünde seçilen kalite
        if pre:
            default = next((i for i, c in enumerate(info["choices"]) if c["format"] == pre), default)
        self.quality.setCurrentIndex(default)
        self.quality.blockSignals(False)
        self.form.setRowVisible(self.quality, True)
        self._quality_changed()

    def _quality_changed(self):
        if not self.video_info:
            return
        c = self.quality.currentData()
        text = _t("Video  ·  {0}").format(self.video_info['title'])
        if self.video_info.get("duration"):
            text += _t("  ·  süre {0}").format(fmt_time(self.video_info['duration']))
        if c.get("size"):
            text += f"  ·  ≈ {fmt_size(c['size'])}"
        self.size_lbl.setText(text)
        self._set_name(sanitize_filename(self.video_info["title"]) + "." + c.get("ext", "mp4"))

    # ---- HLS (m3u8) video akışı
    def _start_hls(self):
        self.size_lbl.setText(_t("Video akışı inceleniyor…"))

        def work():
            try:
                self.bridge.hls.emit(hls.inspect(self.url, self.headers), None)
            except Exception as e:  # noqa: BLE001
                self.bridge.hls.emit(None, str(e))
        threading.Thread(target=work, daemon=True).start()

    def _on_hls(self, info, err):
        if err:
            self.size_lbl.setText(_t("Video akışı okunamadı: {0}").format(err))
            return
        if info.get("live"):
            self.size_lbl.setText(_t("Bu bir canlı yayın; canlı yayınlar desteklenmiyor."))
            return
        self.hls_info = info
        self._update_format_row()
        self.quality.clear()
        for v in info["variants"]:
            self.quality.addItem(hls.variant_label(v), v)
        self.form.setRowVisible(self.quality, len(info["variants"]) > 1)
        text = _t("HLS video akışı")
        if info.get("duration"):
            text += _t("  ·  süre {0}").format(fmt_time(info['duration']))
        if not self.mgr.ffmpeg():
            text += _t("  ·  ffmpeg bulunamadı: .ts olarak kaydedilir (Seçenekler → Video)")
        self.size_lbl.setText(text)
        stem = os.path.splitext(getattr(self, "name", "") or "")[0]
        if not stem or stem.lower() in ("index", "master", "playlist", "chunklist", "download"):
            stem = "video"
        self._set_name(stem + ".mp4")

    def _update_format_row(self):
        cat = self.cat.currentData()
        show = bool(self.video_info or self.hls_info or cat in ("video", "music"))
        self.form.setRowVisible(self.fmt, show)

    def _set_name(self, name):
        """Dosya adı arka planda tutulur (videonun başlığı / sunucunun verdiği ad); alanda yalnızca klasör görünür.
        Klasör, kullanıcı elle seçmediyse kategoriye göre belirlenir."""
        self.name = name
        cat = category_for(name)
        self.cat.blockSignals(True)
        self.cat.setCurrentIndex(max(0, self.cat.findData(cat)))
        self.cat.blockSignals(False)
        if not self.user_edited:
            self.path_edit.setText(self.mgr.category_dir(cat))
        self.path_edit.setToolTip(name)
        if hasattr(self, "form"):
            self._update_format_row()

    def _cat_changed(self):
        self.path_edit.setText(self.mgr.category_dir(self.cat.currentData()))
        self.user_edited = False

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, _t("Kayıt klasörü"), self.path_edit.text())
        if d:
            self.path_edit.setText(os.path.normpath(d))
            self.user_edited = True

    def _probe(self):
        try:
            self.bridge.probed.emit(probe(self.url, self.headers), None)
        except Exception as e:  # noqa: BLE001
            self.bridge.probed.emit(None, str(e))

    def _on_probe(self, info, err):
        if err:
            self.size_lbl.setText(_t("Sorgulanamadı: {0}").format(err))
            return
        if looks_like_torrent(self.url, info):
            self._start_torrent(info["final_url"])
            return
        if hls.is_hls(info["final_url"], info["content_type"]):
            self.url = info["final_url"]
            self._start_hls()
            return
        if is_dash(info["final_url"], info["content_type"]) and ytdlp.available():
            self.url = info["final_url"]
            self._start_video()
            return
        if (info.get("content_type") or "").startswith("text/html") and ytdlp.available():
            # Bir web sayfası: içinde indirilebilir video var mı? (IDM'deki gibi)
            self._start_video(fallback_info=info)
            return
        self._apply_probe(info)

    # ---- .torrent bağlantısı: dosya olarak kaydetmek yerine torrent olarak aç (dosya seçimi penceresi)
    def _start_torrent(self, url):
        self.size_lbl.setText(_t("Torrent dosyası alınıyor…"))
        for b in self.go_buttons:
            b.setEnabled(False)
        self.bridge.done.connect(self._on_torrent)

        def work():
            try:
                data = fetch_torrent(url, self.headers)
                import hashlib
                folder = os.path.join(TORRENT_DIR, "gelen")
                os.makedirs(folder, exist_ok=True)
                path = os.path.join(folder, hashlib.sha1(data).hexdigest() + ".torrent")
                with open(path, "wb") as f:
                    f.write(data)
                self.bridge.done.emit(path, None)
            except Exception as e:  # noqa: BLE001
                self.bridge.done.emit(None, str(e))
        threading.Thread(target=work, daemon=True).start()

    def _on_torrent(self, path, err):
        if err:
            self.size_lbl.setText(err)
            return
        self.accept()
        self.win.add_source(path)

    def _apply_probe(self, info):
        self.info = info
        res = _t("Evet") if info["resumable"] else _t("Hayır")
        self.size_lbl.setText(_t("{0}   ·   Devam ettirme desteği: {1}").format(fmt_size(info['size']), res))
        self._set_name(info["filename"])

    def _go(self, start):
        folder = self.path_edit.text().strip()
        if not folder:
            return
        path = os.path.join(folder, getattr(self, "name", "") or "download")
        fmt = self.fmt.currentData() if self.form.isRowVisible(self.fmt) else ""
        it = self._create(path, start)
        h = getattr(self.win, "_handoffs", {}).get(getattr(self, "handoff", None))
        if h is not None:
            h["iid"] = it.id
            it.extra["handoff"] = self.handoff  # TurboDM yeniden başlasa da eklentinin sorusu yanıtlanabilsin
        if fmt:
            it.extra["convert"] = fmt  # indirme bitince ffmpeg ile dönüştürülür
        if start:
            self.win.show_progress(it.id)
        self.win.refresh(force=True)
        self.accept()

    def _create(self, path, start):
        if self.video_info:
            return self.mgr.add_ytdlp(self.url_edit.text().strip(), path, self.quality.currentData(),
                                      self.video_info["title"], self.headers, self.cookies,
                                      self.desc.text(), start)
        if self.hls_info:
            v = self.quality.currentData()
            return self.mgr.add_hls(self.url_edit.text().strip(), v["url"], v.get("audio_url"), path,
                                    self.headers, self.desc.text(), start)
        return self.mgr.add_http(self.url_edit.text().strip(), path, self.cat.currentData(),
                                 self.headers, self.desc.text(), start,
                                 self.info.get("size"), self.info.get("resumable", True))


# ------------------------------------------------------------------ torrent ekleme
class TorrentAddDialog(QDialog):
    """Torrent ekleme: dosya listesi (onay kutulu ağaç) ile hangi dosyaların ineceği seçilir.
    Magnet'lerde önce meta veri (dosya listesi) eşlerden alınır; bu sırada hiçbir dosya inmez."""

    def __init__(self, win, source):
        super().__init__(win)
        self.win, self.mgr, self.source = win, win.mgr, source
        self.ti, self.probe_key = None, None
        self.setWindowTitle(_t("Torrent Ekle"))
        self.resize(640, 520)
        self.setAttribute(Qt.WA_DeleteOnClose)

        form = QFormLayout()
        src = QLabel(source if len(source) < 90 else source[:87] + "…")
        src.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow(_t("Kaynak:"), src)
        self.name_lbl = QLabel()
        self.size_lbl = QLabel()
        form.addRow(_t("Ad:"), self.name_lbl)
        form.addRow(_t("Seçilen boyut:"), self.size_lbl)
        self.dir_edit = QLineEdit(self.mgr.category_dir("torrent"))
        browse = QPushButton("…")
        browse.setObjectName("browse")
        browse.setFixedWidth(32)
        browse.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.addWidget(self.dir_edit)
        row.addWidget(browse)
        form.addRow(_t("Kayıt klasörü:"), row)
        self.desc = QLineEdit()
        form.addRow(_t("Açıklama:"), self.desc)

        self.files = TorrentFilesTree()
        self.files.changed.connect(self._update_size)
        sel = QHBoxLayout()
        for text, on in ((_t("Tümünü seç"), True), (_t("Hiçbirini seçme"), False)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, v=on: self.files.set_all(v))
            sel.addWidget(b)
        sel.addStretch()

        brow = QHBoxLayout()
        brow.addStretch()
        self.buttons = []
        for text, start in ((_t("Sonra İndir"), False), (_t("İndirmeyi Başlat"), True)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, s=start: self._go(s))
            brow.addWidget(b)
            self.buttons.append(b)
        self.buttons[1].setDefault(True)
        c = QPushButton(_t("İptal"))
        c.clicked.connect(self.reject)
        brow.addWidget(c)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(QLabel(_t("İndirilecek dosyalar:")))
        lay.addWidget(self.files, 1)
        lay.addLayout(sel)
        lay.addLayout(brow)

        if is_magnet(source):
            dn = urllib.parse.parse_qs(urllib.parse.urlparse(source).query).get("dn")
            self.name_lbl.setText((dn[0] + " — " if dn else "") + _t("dosya listesi eşlerden alınıyor…"))
            try:
                self.probe_key = self.mgr.torrents.probe_start(source, self.dir_edit.text())
            except Exception as e:  # noqa: BLE001
                self.name_lbl.setText(_t("Hata: {0}").format(e))
                for b in self.buttons:
                    b.setEnabled(False)
                return
            self.poll = QTimer(self, interval=500, timeout=self._poll)
            self.poll.start()
        else:
            try:
                self._set_ti(tmod.lt.torrent_info(source))
            except Exception as e:  # noqa: BLE001
                self.name_lbl.setText(_t("Torrent dosyası okunamadı: {0}").format(e))
                for b in self.buttons:
                    b.setEnabled(False)

    def _poll(self):
        ti = self.mgr.torrents.probe_info(self.probe_key) if self.probe_key else None
        if ti:
            self.poll.stop()
            self._set_ti(ti)

    def _set_ti(self, ti):
        self.ti = ti
        files = tmod.file_list(ti)
        self.name_lbl.setText(_t("{0}   ({1} dosya)").format(ti.name(), sum(1 for f in files if not f[2])))
        self.files.populate(files)
        self._update_size()

    def _update_size(self):
        if self.ti:
            self.size_lbl.setText(f"{fmt_size(self.files.selected_size())} / {fmt_size(self.ti.total_size())}")

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, _t("Kayıt klasörü"), self.dir_edit.text())
        if d:
            self.dir_edit.setText(os.path.normpath(d))

    def _go(self, start):
        pr = self.files.priorities() if self.ti else None
        if pr is not None and not self.files.any_selected():
            QMessageBox.warning(self, APP_NAME, _t("En az bir dosya seçmelisiniz."))
            return
        if pr is not None and all(leaf.checkState(0) == Qt.Checked for leaf, _ in self.files.leaves):
            pr = None
        try:
            os.makedirs(self.dir_edit.text(), exist_ok=True)
            it = self.mgr.add_torrent(self.source, self.dir_edit.text(), start, self.desc.text(),
                                      priorities=pr, probe_key=self.probe_key)
            self.probe_key = None  # oturum indirmeye devredildi
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, APP_NAME, _t("Torrent eklenemedi:\n{0}").format(e))
            return
        if start:
            self.win.show_progress(it.id)
        self.win.refresh(force=True)
        self.accept()

    def done(self, r):
        if self.probe_key:
            self.mgr.torrents.probe_cancel(self.probe_key)
            self.probe_key = None
        super().done(r)


# ------------------------------------------------------------------ indirme durumu
class SmoothProgress:
    """İndirilen miktar ve hız için akıcı gösterim (yalnızca görüntü; indirmeyi etkilemez).
    Gerçek değer parça parça (ör. video indirmede birkaç MB'lık sıçramalarla) ve yarım saniyede bir gelir.
    Gösterilen miktar, son gerçek değerden o anki hızla öngörülen noktaya yumuşakça yaklaşır: geri gitmez,
    sıçramaz, gerçek değerin en fazla ~1 saniyelik hız kadar önüne geçer. Hız da yumuşatılır (dalgalanmasın)."""

    LOOKAHEAD = 1.0   # gerçek değerin en fazla bu kadar saniyelik hız kadar önüne geçilir
    FOLLOW = 6.0      # yaklaşma hızı (1/sn): büyük → gerçek değere daha çabuk yetişir
    SPEED_FOLLOW = 2.5

    def __init__(self):
        self.shown = None
        self.speed = 0.0
        self.actual = None
        self.actual_t = 0.0
        self.t = None
        self.est = 0.0  # hız verilmezse (bağlantı başına) gerçek değerin artışından tahmin

    def step(self, actual, speed, size=None, running=True, now=None):
        """speed=None: hız, gerçek değerin artış hızından tahmin edilir (bağlantı satırları, bağlantı çubuğu)."""
        now = time.monotonic() if now is None else now
        dt = 0.0 if self.t is None else max(0.0, min(now - self.t, 0.5))
        self.t = now
        if actual != self.actual:
            if speed is None and self.actual is not None and actual > self.actual:
                inst = (actual - self.actual) / max(now - self.actual_t, 0.05)
                self.est = inst if not self.est else self.est + (inst - self.est) * 0.3
            self.actual, self.actual_t = actual, now
        elif speed is None and now - self.actual_t > 2.0:
            self.est = 0.0  # bir süredir artmıyor: bekleyen bağlantı
        speed = max(0.0, self.est if speed is None else (speed or 0.0))
        if self.shown is None or not running or actual < self.shown - max(speed, 1) * self.LOOKAHEAD * 2:
            # ilk değer, duraklatma/bitiş ya da geri sarma (yeniden başlatılan indirme): doğrudan gerçek değer
            self.shown, self.speed = float(actual), (speed if running else 0.0)
            return actual, self.speed
        self.speed += (speed - self.speed) * min(1.0, dt * self.SPEED_FOLLOW)
        ahead = min(now - self.actual_t, self.LOOKAHEAD) * speed
        target = actual + ahead
        if size:
            target = min(target, size)
        if target > self.shown:
            self.shown += (target - self.shown) * min(1.0, dt * self.FOLLOW)
        return int(self.shown), self.speed


class ProgressDialog(QDialog):
    """IDM'deki indirme penceresi:
    üstte sekmeler (İndirme durumu · Hız sınırlayıcı · Bitince yapılacaklar), ortada düğmeler,
    altta (ayrıntılar) bağlantıların başlangıç noktaları ve ilerlemesi + bağlantı tablosu."""

    ON_COMPLETE_KEYS = (("show_dialog", _t("İndirme bitince 'Tamamlandı' penceresini göster")),
                        ("exit", _t("İndirme bitince TurboDM'den çık")),
                        ("sleep", _t("İndirme bitince bilgisayarı uyku moduna al")),
                        ("shutdown", _t("İndirme bitince bilgisayarı kapat")),
                        ("force", _t("Kapatırken açık programları zorla kapat")))

    def __init__(self, win, iid):
        # Sahipsiz (bağımsız) pencere: Windows'ta sahibi olan pencere, ana pencere simge durumuna
        # küçültülünce onunla birlikte iner. İndirme penceresi kendi başına açık kalsın.
        super().__init__(None)
        self.win, self.mgr, self.iid = win, win.mgr, iid
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMinimumWidth(640)
        standalone_window(self)  # küçült / tam ekran / kapat + görev çubuğu düğmesi
        it = self.mgr.items[iid]
        self.kind = it.kind
        self.is_torrent = it.kind == "torrent"
        if not hasattr(it, "on_complete"):
            it.on_complete = {"show_dialog": self.mgr.settings["show_complete_dialog"]}

        # ---- sekme 1: İndirme durumu
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        self.lbl = {}
        rows = [("url", _t("Adres")), ("status", _t("Durum")), ("size", _t("Dosya boyutu")),
                ("done", _t("İndirilen")), ("speed", _t("Aktarım hızı")), ("eta", _t("Kalan süre"))]
        if self.is_torrent:
            rows += [("peers", _t("Eşler / Seed")), ("upload", _t("Yükleme"))]
        elif it.kind == "hls":
            rows += [("parts", _t("Video parçaları"))]
        else:
            rows += [("resume", _t("Devam ettirme"))]
        for r, (k, t) in enumerate(rows):
            grid.addWidget(QLabel(t), r, 0)
            self.lbl[k] = QLabel()
            self.lbl[k].setTextInteractionFlags(Qt.TextSelectableByMouse)
            grid.addWidget(self.lbl[k], r, 1)
        grid.setColumnStretch(1, 1)
        self.pbar = QProgressBar()
        self.pbar.setRange(0, 1000)
        self.pbar.setTextVisible(True)
        self.pbar.setMinimumHeight(22)
        t1 = QWidget()
        l1 = QVBoxLayout(t1)
        l1.addLayout(grid)
        l1.addWidget(self.pbar)

        # ---- sekme 2: Hız sınırlayıcı
        t2 = QWidget()
        f2 = QFormLayout(t2)
        cur = int(it.extra.get("speed_limit_kb") or 0)
        self.lim_on = QCheckBox(_t("Bu indirme için hız sınırı kullan"))
        self.lim_on.setChecked(cur > 0)
        self.lim_kb = QSpinBox(minimum=1, maximum=10_000_000, value=cur or 1024, suffix=" KB/s")
        self.lim_kb.setEnabled(cur > 0)
        f2.addRow(self.lim_on)
        f2.addRow(_t("En fazla:"), self.lim_kb)
        note = QLabel(_t("Genel hız sınırı (Seçenekler → Bağlantı) bundan bağımsız olarak tüm indirmelere uygulanır."))
        note.setWordWrap(True)
        note.setStyleSheet("color: palette(mid);")
        f2.addRow(note)
        self.lim_on.toggled.connect(self._limit_changed)
        self.lim_kb.valueChanged.connect(self._limit_changed)

        # ---- sekme 3: Bitince yapılacaklar
        t3 = QWidget()
        l3 = QVBoxLayout(t3)
        self.oc = {}
        for key, text in self.ON_COMPLETE_KEYS:
            cb = QCheckBox(text)
            cb.setChecked(bool(it.on_complete.get(key)))
            cb.toggled.connect(lambda v, k=key: self._on_complete_changed(k, v))
            self.oc[key] = cb
            l3.addWidget(cb)
        self.oc["force"].setEnabled(bool(it.on_complete.get("shutdown")))
        l3.addStretch()

        tabs = QTabWidget()
        tabs.addTab(t1, _t("İndirme durumu"))
        if not self.is_torrent:
            tabs.addTab(t2, _t("Hız sınırlayıcı"))
        tabs.addTab(t3, _t("Bitince yapılacaklar"))

        # ---- düğmeler
        self.btn_details = QPushButton(_t("<< Ayrıntıları gizle"))
        self.btn_details.setAutoDefault(False)  # birincil (mavi) düğme Devam/Duraklat olsun
        self.btn_details.clicked.connect(self._toggle_details)
        self.btn_toggle = QPushButton()
        self.btn_toggle.setMinimumWidth(110)
        self.btn_toggle.setDefault(True)
        self.btn_toggle.clicked.connect(self._toggle)
        b_cancel = QPushButton(_t("İptal"))
        b_cancel.setAutoDefault(False)
        b_cancel.clicked.connect(self._cancel)
        brow = QHBoxLayout()
        brow.addWidget(self.btn_details)
        brow.addStretch()
        brow.addWidget(self.btn_toggle)
        brow.addWidget(b_cancel)

        # ---- ayrıntılar: bağlantılar (IDM'deki alt bölüm)
        self.details = QWidget()
        ld = QVBoxLayout(self.details)
        ld.setContentsMargins(0, 4, 0, 0)
        cap = QLabel(_t("Dosyalar ve indirme ilerlemesi") if self.is_torrent
                     else _t("Bağlantılara göre başlangıç noktaları ve indirme ilerlemesi"))
        cap.setStyleSheet("font-weight: 600;")
        ld.addWidget(cap)
        self.bar = SegmentBar()
        self.bar.setMinimumHeight(26)
        ld.addWidget(self.bar)
        if self.is_torrent:
            self.table = TorrentFilesTree(with_progress=True)
            self.table.changed.connect(self._priorities_changed)
            self._files_built = False
        else:
            self.table = QTableWidget(0, 3)
            self.table.setHorizontalHeaderLabels([_t("N."), _t("İndirilen"), _t("Bilgi")])
            hh = self.table.horizontalHeader()
            hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
            hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
            hh.setSectionResizeMode(2, QHeaderView.Stretch)
            self.table.verticalHeader().hide()
            self.table.verticalHeader().setDefaultSectionSize(22)
            self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.table.setSelectionMode(QAbstractItemView.NoSelection)
            self.table.setAlternatingRowColors(True)
            self.table.setShowGrid(False)
        self.table.setMinimumHeight(170)
        ld.addWidget(self.table, 1)

        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        lay.addLayout(brow)
        lay.addWidget(self.details, 1)
        self.resize(680, 600)

        self.smooth = SmoothProgress()
        self._detail_smooth = {}  # ayrıntılar: ("s", parça başı) / ("c", bağlantı no) -> SmoothProgress
        self.timer = QTimer(self, interval=500, timeout=self.update_view)
        self.timer.start()
        # yüzde, indirilen ve hız saniyede ~30 kez çizilir: sıçramadan, akıcı ilerler
        self.anim = QTimer(self, interval=33, timeout=self._animate)
        self.anim.start()
        self.update_view()

    def _animate(self):
        it = self.mgr.items.get(self.iid)
        if not it:
            return
        running = it.status in ("downloading", "connecting")
        done, speed = self.smooth.step(it.done_bytes, it.speed, it.size, running)
        pct = 100.0 if it.status == "completed" else min(100.0, (done / it.size * 100) if it.size else 0)
        self.lbl["speed"].setText(fmt_speed(speed) or "—")
        if running and not it.size:  # sunucu boyut bildirmedi: yüzde yok, kayan çubuk
            self.setWindowTitle(f"{fmt_size(done)} {it.filename}")
            self.lbl["done"].setText(fmt_size(done))
            if self.pbar.maximum():
                self.pbar.setRange(0, 0)
        else:
            if not self.pbar.maximum():
                self.pbar.setRange(0, 1000)
            self.setWindowTitle(f"{fmt_pct(pct, 0)} {it.filename}")
            self.lbl["done"].setText(f"{fmt_size(done)}  ({fmt_pct(pct, 2)})")
            self.pbar.setValue(int(pct * 10))
            self.pbar.setFormat(fmt_pct(pct, 1))
        if not self.is_torrent and self.details.isVisible():
            self._update_details(it)

    def _update_details(self, it):
        """Ayrıntılar: bağlantı çubuğu ve bağlantı listesi. İnerken saniyede ~30 kez, akıcı (SmoothProgress)."""
        running = it.status in ("downloading", "connecting")
        live = set()
        if it.task:
            total, segs = it.task.bar_data()
            if running:  # her parçanın ilerlemesi (başlangıç noktasına göre) yumuşatılır
                smooth = []
                for a, b, pos in segs:
                    live.add(("s", a))
                    sm = self._detail_smooth.setdefault(("s", a), SmoothProgress())
                    smooth.append([a, b, min(b + 1, sm.step(pos, None, b + 1, True)[0])])
                segs = smooth
        elif it.status == "completed":
            total, segs = 1, [[0, 0, 1]]
        elif it.kind == "hls":
            total, segs = 1, [[0, 0, (it.done_bytes / it.size) if it.size else 0]]
        else:
            total, segs = it.size, [list(s) for s in it.segments]
        self.bar.set_data(total, segs)
        conns = it.task.connections_snapshot() if it.task else []
        if running:  # bağlantı başına indirilen miktar da akıcı
            smooth = []
            for n, done, ctotal, info in conns:
                live.add(("c", n))
                sm = self._detail_smooth.setdefault(("c", n), SmoothProgress())
                shown = sm.step(done, None, ctotal or None, True)[0]
                smooth.append((n, shown, ctotal, info))
            conns = smooth
        for k in [k for k in self._detail_smooth if k not in live]:  # biten/bölünen parçalar
            del self._detail_smooth[k]
        self.table.setRowCount(len(conns))
        for r, (n, done, total, info) in enumerate(conns):
            amount = f"{fmt_size(done)} / {fmt_size(total)}" if total else fmt_size(done)
            for c, v in enumerate((str(n), amount, info)):
                cell = self.table.item(r, c)
                if cell is None:
                    cell = QTableWidgetItem()
                    self.table.setItem(r, c, cell)
                if cell.text() != v:
                    cell.setText(v)
            ok = _t("Veri alınıyor") in info  # dil ne olursa olsun; video bağlantılarında "Görüntü · " ile başlar
            bad = (_t("Yeniden deneniyor ({0}/{1}): {2}").split("{")[0] in info
                   or _t("Hata: {0}").split("{")[0] in info)
            color = QColor(theme.T["ok"]) if ok else QColor(theme.T["bad"]) if bad else QColor()
            self.table.item(r, 2).setForeground(color if color.isValid() else self.palette().text().color())

    # ---- olaylar
    def _toggle_details(self):
        show = not self.details.isVisible()
        self.details.setVisible(show)
        self.btn_details.setText(_t("<< Ayrıntıları gizle") if show else _t("Ayrıntıları göster >>"))
        self.adjustSize()

    def _limit_changed(self):
        self.lim_kb.setEnabled(self.lim_on.isChecked())
        self.mgr.set_item_limit(self.iid, self.lim_kb.value() if self.lim_on.isChecked() else 0)

    def _on_complete_changed(self, key, value):
        it = self.mgr.items.get(self.iid)
        if not it:
            return
        it.on_complete[key] = value
        if key in ("shutdown", "sleep") and value:  # ikisi birden olmaz
            other = "sleep" if key == "shutdown" else "shutdown"
            self.oc[other].setChecked(False)
        if key == "shutdown":
            self.oc["force"].setEnabled(value)

    def _toggle(self):
        it = self.mgr.items.get(self.iid)
        if not it:
            return
        if it.status in ("downloading", "connecting", "seeding"):
            self.mgr.stop(self.iid)
        else:
            self.mgr.start(self.iid)

    def _cancel(self):
        self.mgr.stop(self.iid)
        self.close()

    def _priorities_changed(self):
        pr = self.table.priorities()
        if self.table.any_selected():
            self.mgr.set_torrent_priorities(self.iid, pr)

    # ---- güncelleme
    def update_view(self):
        it = self.mgr.items.get(self.iid)
        if not it:
            self.close()
            return
        self.lbl["url"].setText(it.url if len(it.url) < 80 else it.url[:77] + "…")
        st = STATUS_TEXT.get(it.status, it.status)
        if it.error:
            st += f" — {it.error}"
        self.lbl["status"].setText(st)
        approx = "≈ " if it.kind in ("hls", "ytdlp") and it.status != "completed" and it.size else ""
        self.lbl["size"].setText(approx + fmt_size(it.size))
        self.lbl["eta"].setText(fmt_time(it.eta()) or "—")
        self._animate()  # yüzde, indirilen, hız: akıcı gösterim
        running = it.status in ("downloading", "connecting", "seeding")
        self.btn_toggle.setText(_t("Duraklat") if running else _t("Devam Et"))

        if self.is_torrent:
            self.lbl["peers"].setText(f"{it.peers} / {it.seeds}")
            self.lbl["upload"].setText(fmt_speed(it.ul_speed) or "—")
            self.bar.set_data(it.size, [[0, (it.size or 1) - 1, it.done_bytes]])
            files = self.mgr.torrents.files(it.id) if self.mgr.torrents else []
            if files and not self._files_built:
                self.table.populate([(p, s, pad) for p, s, pad, _ in files], it.extra.get("priorities"))
                self._files_built = True
            if files:
                self.table.set_progress([d for *_, d in files])
            return

        self._update_details(it)
        if it.kind == "hls":
            n_done, n_total = len(it.extra.get("done", [])), it.extra.get("total")
            self.lbl["parts"].setText(f"{n_done} / {n_total}" if n_total else "—")
        else:
            txt = _t("Evet") if it.resumable else _t("Hayır")
            lim = it.extra.get("server_conn_limit") if isinstance(it.extra, dict) else None
            if lim and lim < it.connections:
                txt += _t("   ·   Sunucu en fazla {0} bağlantıya izin veriyor").format(lim)
            self.lbl["resume"].setText(txt)
        if it.status == "completed":
            self.close()


# ------------------------------------------------------------------ bitince yapılacaklar
POWER_ACTIONS = {}


@i18n.on_change
def _power_texts():
    POWER_ACTIONS.update({"shutdown": _t("Bilgisayar kapatılacak"), "sleep": _t("Bilgisayar uyku moduna alınacak"),
                          "exit": _t("TurboDM kapatılacak")})


class PowerActionDialog(QDialog):
    """İndirme / kuyruk bitince yapılacak işlem: geri sayım, 'Şimdi' ve 'İptal' (IDM gibi)."""

    def __init__(self, win, action, force=False, seconds=30, reason=_t("İndirme tamamlandı.")):
        super().__init__(win)
        self.win, self.action, self.force, self.left = win, action, force, seconds
        self.setWindowTitle(APP_NAME)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMinimumWidth(420)
        self.msg = QLabel()
        self.msg.setWordWrap(True)
        self.reason = reason
        b_now = QPushButton(_t("Şimdi"))
        b_now.clicked.connect(self._do)
        b_cancel = QPushButton(_t("İptal"))
        b_cancel.setDefault(True)
        b_cancel.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(b_now)
        row.addWidget(b_cancel)
        lay = QVBoxLayout(self)
        lay.addWidget(self.msg)
        lay.addLayout(row)
        self.timer = QTimer(self, interval=1000, timeout=self._tick)
        self.timer.start()
        self._tick(first=True)

    def _tick(self, first=False):
        if not first:
            self.left -= 1
        if self.left <= 0:
            self._do()
            return
        self.msg.setText(_t("<b>{0}</b><br><br>{1}: <b>{2}</b> saniye.<br>Vazgeçmek için İptal'e basın.").format(self.reason, POWER_ACTIONS[self.action], self.left))

    def _do(self):
        self.timer.stop()
        self.accept()
        self.win.perform_power_action(self.action, self.force)


# ------------------------------------------------------------------ ayarlar
class OptionsDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.mgr = win.mgr
        s = self.mgr.settings
        self.setWindowTitle(_t("Seçenekler"))
        self.setMinimumWidth(560)
        tabs = QTabWidget()

        g = QWidget()
        f = QFormLayout(g)
        self.root = QLineEdit(s["download_root"])
        row = self._with_browse(self.root, lambda: QFileDialog.getExistingDirectory(
            self, _t("Ana indirme klasörü"), self.root.text()))
        f.addRow(_t("Ana indirme klasörü:"), row)
        self.clip = QCheckBox(_t("Panoya kopyalanan indirme adreslerini yakala"))
        self.clip.setChecked(s["clipboard_monitor"])
        f.addRow(self.clip)
        self.complete = QCheckBox(_t("İndirme bitince 'Tamamlandı' penceresini göster"))
        self.complete.setChecked(s["show_complete_dialog"])
        f.addRow(self.complete)
        self.autostart = QCheckBox(_t("Windows açılışında başlat (sistem tepsisinde)"))
        self.autostart.setChecked(winassoc.autostart_enabled())
        f.addRow(self.autostart)
        self.autoupd = QCheckBox(_t("Açılışta güncellemeleri denetle (günde bir kez)"))
        self.autoupd.setChecked(s.get("auto_update_check", True))
        f.addRow(self.autoupd)
        self.awake = QCheckBox(_t("İndirme sürerken bilgisayarın uyku moduna geçmesini engelle"))
        self.awake.setChecked(s.get("keep_awake", True))
        f.addRow(self.awake)
        self.confirm = QCheckBox(_t("İnmekte olan dosya varken çıkışta onay sor"))
        self.confirm.setChecked(s.get("confirm_exit", True))
        f.addRow(self.confirm)
        self.retry = QCheckBox(_t("Bağlantı sorunuyla duran indirmeyi otomatik yeniden dene"))
        self.retry.setChecked(s.get("auto_retry", True))
        self.retry_n = QSpinBox(minimum=1, maximum=20, value=s.get("auto_retry_count", 3))
        self.retry_d = QSpinBox(minimum=5, maximum=3600, value=s.get("auto_retry_delay", 30), suffix=_t(" sn"))
        f.addRow(self.retry)
        rrow = QHBoxLayout()
        rrow.setContentsMargins(24, 0, 0, 0)  # seçeneğin altında, girintili
        rrow.addWidget(QLabel(_t("En fazla:")))
        rrow.addWidget(self.retry_n)
        rrow.addSpacing(12)
        rrow.addWidget(QLabel(_t("Bekleme:")))
        rrow.addWidget(self.retry_d)
        rrow.addStretch()
        f.addRow(rrow)
        for w in (self.retry_n, self.retry_d):
            w.setEnabled(self.retry.isChecked())
            self.retry.toggled.connect(w.setEnabled)
        self.theme = QComboBox()
        for text, key in ((_t("Windows ile aynı (otomatik)"), "auto"), (_t("Açık"), "light"), (_t("Koyu"), "dark")):
            self.theme.addItem(text, key)
        self.theme.setCurrentIndex(max(0, self.theme.findData(s.get("theme", "auto"))))
        self.theme.currentIndexChanged.connect(  # seçince hemen önizleme
            lambda: theme.apply(QApplication.instance(), self.theme.currentData()))
        self._theme_before = s.get("theme", "auto")
        self.rejected.connect(lambda: theme.apply(QApplication.instance(), self._theme_before))
        f.addRow(_t("Tema:"), self.theme)
        self.lang = QComboBox()
        self.lang.addItem(_t("Sistem dili (otomatik)"), "auto")
        for code, name in i18n.LANGUAGES.items():
            self.lang.addItem(name, code)
        self.lang.setCurrentIndex(max(0, self.lang.findData(s.get("language", "auto"))))
        f.addRow(_t("Dil / Language:"), self.lang)
        self.port = QSpinBox(maximum=65535, minimum=1024, value=s["server_port"])
        f.addRow(_t("Tarayıcı entegrasyon portu:"), self.port)
        tabs.addTab(g, _t("Genel"))

        c = QWidget()
        f = QFormLayout(c)
        self.conns = QSpinBox(minimum=1, maximum=32, value=s["connections"])
        f.addRow(_t("İndirme başına bağlantı:"), self.conns)
        self.maxc = QSpinBox(minimum=1, maximum=20, value=s["max_concurrent"])
        f.addRow(_t("Kuyrukta aynı anda indirme:"), self.maxc)
        self.limit = QSpinBox(minimum=0, maximum=10_000_000, value=s["speed_limit_kb"], suffix=" KB/s")
        self.limit.setSpecialValueText(_t("Sınırsız"))
        f.addRow(_t("Hız sınırı (toplam):"), self.limit)
        self.limit_active = QCheckBox(_t("Hız sınırını yalnızca bilgisayar kullanılırken uygula (boştayken tam hız)"))
        self.limit_active.setChecked(s.get("speed_limit_when_active", False))
        f.addRow(self.limit_active)
        # vekil sunucu (proxy)
        self.proxy_mode = QComboBox()
        for key, text in (("system", _t("Windows ayarını kullan")), ("none", _t("Kullanma")),
                          ("manual", _t("Elle (HTTP vekil sunucu)"))):
            self.proxy_mode.addItem(text, key)
        self.proxy_mode.setCurrentIndex(max(0, self.proxy_mode.findData(s.get("proxy_mode", "system"))))
        self.proxy_url = QLineEdit(s.get("proxy_url", ""))
        self.proxy_url.setPlaceholderText("http://sunucu:8080")
        self.proxy_mode.currentIndexChanged.connect(
            lambda: self.proxy_url.setEnabled(self.proxy_mode.currentData() == "manual"))
        self.proxy_url.setEnabled(self.proxy_mode.currentData() == "manual")
        f.addRow(_t("Vekil sunucu (proxy):"), self.proxy_mode)
        f.addRow(_t("Vekil sunucu adresi:"), self.proxy_url)
        note = QLabel(_t("Vekil sunucu HTTP/HTTPS ve video indirmelerinde kullanılır; torrent ve FTP bağlantıları doğrudan kurulur."))
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {theme.T['muted']};")
        f.addRow(note)
        self.ua = QLineEdit(s.get("user_agent", ""))
        self.ua.setPlaceholderText(_t("Varsayılan (tarayıcı gibi)"))
        f.addRow(_t("Tarayıcı kimliği (User-Agent):"), self.ua)
        # site girişleri (parolalar Windows'un şifrelemesiyle saklanır)
        self.logins = [dict(x) for x in s.get("site_logins", [])]
        self.login_table = QTableWidget(0, 2)
        self.login_table.setHorizontalHeaderLabels([_t("Site"), _t("Kullanıcı adı")])
        self.login_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.login_table.verticalHeader().hide()
        self.login_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.login_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.login_table.setMaximumHeight(110)
        lrow = QHBoxLayout()
        for text, fn in ((_t("Ekle…"), self._add_login), (_t("Kaldır"), self._remove_login)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            lrow.addWidget(b)
        lrow.addStretch()
        f.addRow(_t("Site girişleri:"), self.login_table)
        f.addRow("", lrow)
        self._fill_logins()
        tabs.addTab(c, _t("Bağlantı"))

        v = QWidget()
        f = QFormLayout(v)
        self.ffmpeg = QLineEdit(s.get("ffmpeg_path", ""))
        self.ffmpeg.setPlaceholderText(_t("Boş bırakılırsa PATH'te aranır"))
        f.addRow(_t("ffmpeg.exe:"), self._with_browse(self.ffmpeg, lambda: QFileDialog.getOpenFileName(
            self, "ffmpeg.exe", "", _t("ffmpeg (ffmpeg.exe)"))[0]))
        self.ff_status = QLabel()
        self.ff_status.setWordWrap(True)
        f.addRow(self.ff_status)
        self.ffmpeg.textChanged.connect(self._ff_status)
        self._ff_status()
        yt = QLabel(_t("Video motoru: ") + (_t("hazır") if ytdlp.version() else _t("bulunamadı"))
                    + ("" if ytdlp.deno_path() else _t("  ·  ⚠ bazı sitelerde kısıtlı çalışır")))
        yt.setWordWrap(True)
        f.addRow(yt)
        b = QPushButton(_t("Video motorunu güncelle…"))
        b.clicked.connect(lambda: (self.accept(), self.parent().check_updates()))
        f.addRow(b)
        tabs.addTab(v, _t("Video"))

        t = QWidget()
        f = QFormLayout(t)
        self.tport = QSpinBox(minimum=1024, maximum=65535, value=s["torrent_port"])
        f.addRow(_t("Dinleme portu:"), self.tport)
        self.ul = QSpinBox(minimum=0, maximum=10_000_000, value=s["torrent_upload_kb"], suffix=" KB/s")
        self.ul.setSpecialValueText(_t("Sınırsız / otomatik"))
        f.addRow(_t("Yükleme sınırı:"), self.ul)
        self.ulauto = QCheckBox(_t("İndirirken yükleme hızını otomatik sınırla (önerilen: indirme hızlanır)"))
        self.ulauto.setToolTip(_t("Yükleme hattı dolunca indirme de yavaşlar. Açıkken, torrent inerken yükleme hızı\nindirme hızına göre ayarlanır (150 KB/s – 2 MB/s). Elle bir sınır girerseniz o geçerlidir."))
        self.ulauto.setChecked(s["torrent_upload_auto"])
        f.addRow(self.ulauto)
        self.seed = QCheckBox(_t("İndirme bitince paylaşmaya (seed) devam et"))
        self.seed.setChecked(s["seed_after_complete"])
        f.addRow(self.seed)
        f.addRow(QLabel(_t("Torrent motoru: ") + (_t("hazır (libtorrent ") + tmod.lt.__version__ + ")"
                                              if self.mgr.torrents else _t("yok — {0}").format(self.mgr.torrent_error))))
        self.assoc_lbl = QLabel()
        self.assoc_lbl.setWordWrap(True)
        f.addRow(self.assoc_lbl)
        arow = QHBoxLayout()
        for text, fn in ((_t("Magnet ve .torrent'i TurboDM ile aç"), self._register),
                         (_t("İlişkilendirmeyi kaldır"), self._unregister),
                         (_t("Varsayılan uygulamalar…"), winassoc.open_default_apps)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            arow.addWidget(b)
        f.addRow(arow)
        self._assoc_status()
        tabs.addTab(t, _t("Torrent"))

        # kendi kategorileriniz: uzantılarına göre kendi klasörlerine iner (yerleşik kategorilerden önce denenir)
        k = QWidget()
        kl = QVBoxLayout(k)
        kinfo = QLabel(_t("Kendi kategorilerinizi ekleyin: belirttiğiniz uzantılardaki dosyalar kendi klasörüne iner. Kendi kategorileriniz yerleşik kategorilerden önce denenir."))
        kinfo.setWordWrap(True)
        kl.addWidget(kinfo)
        self.cats = [dict(x) for x in s.get("custom_categories", [])]
        self.cat_table = QTableWidget(0, 3)
        self.cat_table.setHorizontalHeaderLabels([_t("Ad"), _t("Klasör"), _t("Uzantılar")])
        self.cat_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.cat_table.verticalHeader().hide()
        self.cat_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.cat_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.cat_table.doubleClicked.connect(lambda *_: self._edit_cat())
        kl.addWidget(self.cat_table, 1)
        krow = QHBoxLayout()
        for text, fn in ((_t("Ekle…"), self._add_cat), (_t("Düzenle…"), self._edit_cat), (_t("Kaldır"), self._remove_cat)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            krow.addWidget(b)
        krow.addStretch()
        kl.addLayout(krow)
        self._fill_cats()
        tabs.addTab(k, _t("Kategoriler"))

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._save)
        bb.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        lay.addWidget(bb)

    def _with_browse(self, edit, picker):
        b = QPushButton("…")
        b.setObjectName("browse")
        b.setFixedWidth(32)

        def pick():
            p = picker()
            if p:
                edit.setText(os.path.normpath(p))
        b.clicked.connect(pick)
        row = QHBoxLayout()
        row.addWidget(edit)
        row.addWidget(b)
        return row

    def _fill_logins(self):
        self.login_table.setRowCount(len(self.logins))
        for r, x in enumerate(self.logins):
            self.login_table.setItem(r, 0, QTableWidgetItem(x.get("site", "")))
            self.login_table.setItem(r, 1, QTableWidgetItem(x.get("user", "")))

    def _add_login(self):
        from . import secure
        v = ask_fields(self, _t("Site girişi"), [(_t("Site (ör. dosya.example.com):"), "", False),
                                                  (_t("Kullanıcı adı:"), "", False), (_t("Parola:"), "", True)])
        if v and v[0]:
            site = re.sub(r"^\w+://", "", v[0]).split("/")[0].lower()
            self.logins = [x for x in self.logins if x.get("site") != site]
            self.logins.append({"site": site, "user": v[1], "password": secure.protect(v[2])})
            self._fill_logins()

    def _remove_login(self):
        rows = sorted({i.row() for i in self.login_table.selectedIndexes()}, reverse=True)
        for r in rows:
            del self.logins[r]
        self._fill_logins()

    def _fill_cats(self):
        self.cat_table.setRowCount(len(self.cats))
        for r, c in enumerate(self.cats):
            for col, v in enumerate((c.get("name", ""), c.get("folder", ""), " ".join(c.get("exts", [])))):
                self.cat_table.setItem(r, col, QTableWidgetItem(v))

    def _cat_dialog(self, c=None):
        c = c or {}
        v = ask_fields(self, _t("Kategori"), [(_t("Ad:"), c.get("name", ""), False),
                                              (_t("Klasör adı:"), c.get("folder", ""), False),
                                              (_t("Uzantılar (boşlukla ayırın, ör. iso img):"), " ".join(c.get("exts", [])), False)])
        if not v or not v[0]:
            return None
        exts = [e.lower().lstrip(".") for e in re.split(r"[\s,;]+", v[2]) if e.strip(" .")]
        return {"key": c.get("key") or "c_" + uuid.uuid4().hex[:8], "name": v[0],
                "folder": engine.sanitize_filename(v[1] or v[0]), "exts": exts}

    def _add_cat(self):
        c = self._cat_dialog()
        if c:
            self.cats.append(c)
            self._fill_cats()

    def _edit_cat(self):
        rows = sorted({i.row() for i in self.cat_table.selectedIndexes()})
        if rows:
            c = self._cat_dialog(self.cats[rows[0]])
            if c:
                self.cats[rows[0]] = c
                self._fill_cats()

    def _remove_cat(self):
        for r in sorted({i.row() for i in self.cat_table.selectedIndexes()}, reverse=True):
            del self.cats[r]
        self._fill_cats()

    def _ff_status(self):
        ff = hls.find_ffmpeg(self.ffmpeg.text().strip())
        self.ff_status.setText(
            _t("✔ ffmpeg bulundu: {0}\nHLS videoları .mp4 olarak kaydedilir, ayrı ses kanalı birleştirilir.").format(ff) if ff else
            _t("✖ ffmpeg bulunamadı. HLS videoları yine iner ama .ts olarak kaydedilir; ayrı ses kanalı varsa ayrı dosyaya yazılır.\nKurmak için: winget install Gyan.FFmpeg"))

    def _assoc_status(self):
        if winassoc.is_registered():
            txt = _t("✔ magnet bağlantıları ve .torrent dosyaları TurboDM ile açılıyor.")
            other = winassoc.user_choice_overrides()
            if other:
                txt = (_t("⚠ Kayıt yapıldı ama Windows'ta varsayılan magnet uygulaması hâlâ '{0}'. 'Varsayılan uygulamalar…' ile TurboDM'i seçin.").format(other))
        else:
            txt = _t("magnet bağlantıları ve .torrent dosyaları henüz TurboDM ile ilişkilendirilmedi.")
        self.assoc_lbl.setText(txt)

    def _register(self):
        try:
            winassoc.register()
        except OSError as e:
            QMessageBox.critical(self, APP_NAME, _t("Kayıt yapılamadı: {0}").format(e))
        self._assoc_status()

    def _unregister(self):
        winassoc.unregister()
        self._assoc_status()

    def _save(self):
        s = self.mgr.settings
        restart = s["server_port"] != self.port.value() or s["torrent_port"] != self.tport.value()
        s.update(download_root=self.root.text(), clipboard_monitor=self.clip.isChecked(),
                 show_complete_dialog=self.complete.isChecked(), server_port=self.port.value(),
                 connections=self.conns.value(), max_concurrent=self.maxc.value(),
                 speed_limit_kb=self.limit.value(), torrent_port=self.tport.value(),
                 torrent_upload_kb=self.ul.value(), seed_after_complete=self.seed.isChecked(),
                 torrent_upload_auto=self.ulauto.isChecked(), theme=self.theme.currentData(),
                 ffmpeg_path=self.ffmpeg.text().strip(), auto_update_check=self.autoupd.isChecked(),
                 keep_awake=self.awake.isChecked(), confirm_exit=self.confirm.isChecked(),
                 auto_retry=self.retry.isChecked(), auto_retry_count=self.retry_n.value(),
                 auto_retry_delay=self.retry_d.value(), speed_limit_when_active=self.limit_active.isChecked(),
                 proxy_mode=self.proxy_mode.currentData(), proxy_url=self.proxy_url.text().strip(),
                 user_agent=self.ua.text().strip(), site_logins=self.logins)
        cats_changed = s.get("custom_categories", []) != self.cats
        s["custom_categories"] = self.cats
        self.mgr.apply_settings()
        if cats_changed:  # kenar çubuğundaki kategoriler yenilensin
            QTimer.singleShot(0, self.parent()._retranslate)
        if self.autostart.isChecked() != winassoc.autostart_enabled():
            winassoc.set_autostart(self.autostart.isChecked())
        if restart:
            QMessageBox.information(self, APP_NAME, _t("Port değişiklikleri program yeniden başlatılınca geçerli olur."))
        self.accept()
        if self.lang.currentData() != s.get("language", "auto"):  # anında, yeniden başlatmadan
            self.parent().set_language(self.lang.currentData())


class SchedulerDialog(QDialog):
    """Kuyruklar ve zamanlayıcı: her kuyruğun aynı anda indirme sayısı ve başlama/durma saati.
    "Ana kuyruk" eski tek kuyruktur; yeni kuyruklar eklenebilir, silinince içindekiler Ana kuyruğa geçer."""

    def __init__(self, win, qid="main"):
        super().__init__(win)
        self.win, self.mgr = win, win.mgr
        self.changed = False  # kuyruk eklendi/silindi/adı değişti → kenar çubuğu yeniden kurulur
        self._cur = None
        self.setWindowTitle(_t("Kuyruklar ve zamanlayıcı"))
        self.setMinimumWidth(480)
        self.qsel = QComboBox()
        top = QHBoxLayout()
        top.addWidget(QLabel(_t("Kuyruk:")))
        top.addWidget(self.qsel, 1)
        b_add = QPushButton(_t("Yeni kuyruk…"))
        b_add.clicked.connect(self._add)
        self.b_ren = QPushButton(_t("Yeniden adlandır…"))
        self.b_ren.clicked.connect(self._rename)
        self.b_del = QPushButton(_t("Sil"))
        self.b_del.clicked.connect(self._delete)
        for b in (b_add, self.b_ren, self.b_del):
            top.addWidget(b)
        f = QFormLayout()
        self.enabled = QCheckBox(_t("Kuyruğu belirtilen saatte otomatik başlat/durdur"))
        f.addRow(self.enabled)
        self.start = QTimeEdit()
        self.stop = QTimeEdit()
        for w in (self.start, self.stop):
            w.setDisplayFormat("HH:mm")
        f.addRow(_t("Başlama saati:"), self.start)
        f.addRow(_t("Durma saati:"), self.stop)
        self.maxc = QSpinBox(minimum=1, maximum=20)
        f.addRow(_t("Aynı anda indirme:"), self.maxc)
        s = self.mgr.settings
        self.qdone = QComboBox()
        for key, text in (("none", _t("Hiçbir şey yapma")), ("shutdown", _t("Bilgisayarı kapat")),
                          ("sleep", _t("Bilgisayarı uyku moduna al")), ("exit", _t("TurboDM'den çık"))):
            self.qdone.addItem(text, key)
        self.qdone.setCurrentIndex(max(0, self.qdone.findData(s.get("queue_done_action", "none"))))
        f.addRow(_t("Kuyruk bitince:"), self.qdone)
        self.qforce = QCheckBox(_t("Kapatırken açık programları zorla kapat"))
        self.qforce.setChecked(s.get("queue_done_force", False))
        f.addRow(self.qforce)
        self.count_lbl = QLabel()
        f.addRow(self.count_lbl)
        b_now = QPushButton(_t("Kuyruğu Şimdi Başlat"))
        b_now.clicked.connect(lambda: (self._save(), self.mgr.start_queue(self._cur), self.accept()))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(lambda: (self._save(), self.accept()))
        bb.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addLayout(f)
        row = QHBoxLayout()
        row.addWidget(b_now)
        row.addStretch()
        row.addWidget(bb)
        lay.addLayout(row)
        self.finished.connect(lambda *_: self.changed and self.win._retranslate())
        self._fill(qid)
        self.qsel.currentIndexChanged.connect(self._switch)

    def _fill(self, select):
        self.qsel.blockSignals(True)
        self.qsel.clear()
        for q in self.mgr.queues():
            self.qsel.addItem(q["name"], q["id"])
        self.qsel.setCurrentIndex(max(0, self.qsel.findData(select)))
        self.qsel.blockSignals(False)
        self._load()

    def _load(self):
        self._cur = self.qsel.currentData() or "main"
        q = self.mgr.queue_conf(self._cur)
        self.enabled.setChecked(bool(q.get("schedule_enabled")))
        self.start.setTime(QTime.fromString(q.get("schedule_start", "02:00"), "HH:mm"))
        self.stop.setTime(QTime.fromString(q.get("schedule_stop", "07:00"), "HH:mm"))
        self.maxc.setValue(int(q.get("max_concurrent") or 1))
        main = self._cur == "main"
        for w in (self.qdone, self.qforce):  # bitince kapat/uyut yalnızca Ana kuyrukta
            w.setEnabled(main)
        self.b_ren.setEnabled(not main)
        self.b_del.setEnabled(not main)
        n = sum(1 for i in self.mgr.items.values() if i.in_queue and self.mgr.queue_of(i) == self._cur)
        self.count_lbl.setText(_t("Kuyruktaki dosya sayısı: {0}").format(n))

    def _store(self):
        if self._cur:
            self.mgr.update_queue(self._cur, schedule_enabled=self.enabled.isChecked(),
                                  schedule_start=self.start.time().toString("HH:mm"),
                                  schedule_stop=self.stop.time().toString("HH:mm"), max_concurrent=self.maxc.value())

    def _switch(self):
        self._store()
        self._load()

    def _add(self):
        name, ok = QInputDialog.getText(self, _t("Yeni kuyruk"), _t("Kuyruk adı:"))
        if ok and name.strip():
            self._store()
            q = self.mgr.add_queue(name)
            self.changed = True
            self._fill(q["id"])

    def _rename(self):
        q = self.mgr.queue_conf(self._cur)
        name, ok = QInputDialog.getText(self, _t("Yeniden adlandır"), _t("Kuyruk adı:"), text=q["name"])
        if ok and name.strip():
            self.mgr.update_queue(self._cur, name=name.strip())
            self.changed = True
            self._fill(self._cur)

    def _delete(self):
        q = self.mgr.queue_conf(self._cur)
        if QMessageBox.question(self, APP_NAME, _t("'{0}' kuyruğu silinsin mi? İçindeki indirmeler Ana kuyruğa geçer.").format(q["name"])) == QMessageBox.Yes:
            self.mgr.remove_queue(self._cur)
            self._cur = None
            self.changed = True
            self._fill("main")

    def _save(self):
        self._store()
        self.mgr.settings.update(queue_done_action=self.qdone.currentData(), queue_done_force=self.qforce.isChecked())
        self.mgr.apply_settings()


URL_RE = re.compile(r"(?:https?|ftp)://[^\s\"'<>]+", re.I)


def extract_urls(text):
    """Metindeki http(s)/ftp bağlantıları (sırası korunur, tekrarlar atılır, sondaki noktalama temizlenir)."""
    out = []
    for u in URL_RE.findall(text or ""):
        u = u.rstrip(".,;:!?)]}")
        if u not in out:
            out.append(u)
    return out


class BatchAddDialog(QDialog):
    """Toplu indirme: yapıştırılan metindeki tüm bağlantılar. Her bağlantı arka planda sorgulanır (gerçek dosya adı,
    boyut); işaretlenenler hemen başlatılır ya da seçilen kuyruğa eklenir."""

    COLS = ("", "name", "size", "url")

    def __init__(self, win, text=""):
        super().__init__(win)
        self.win, self.mgr = win, win.mgr
        self.setWindowTitle(_t("Toplu indirme ekle"))
        self.resize(760, 520)
        self.info = {}  # adres -> (ad, boyut) ya da hata
        self.bridge = Bridge()
        self.bridge.done.connect(self._probed)
        info = QLabel(_t("Bağlantıları yapıştırın: her satıra bir adres ya da içinde bağlantılar geçen herhangi bir metin."))
        info.setWordWrap(True)
        self.edit = QPlainTextEdit(text)
        self.edit.setMaximumHeight(130)
        self.edit.textChanged.connect(self._parse)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["", _t("Dosya Adı"), _t("Boyut"), _t("Adres")])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 30)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 240)
        self.count_lbl = QLabel()
        self.folder = QLineEdit()
        self.folder.setPlaceholderText(_t("Otomatik (dosya türüne göre kategori klasörü)"))
        b = QPushButton("…")
        b.setObjectName("browse")
        b.setFixedWidth(32)
        b.clicked.connect(self._pick_folder)
        frow = QHBoxLayout()
        frow.addWidget(self.folder)
        frow.addWidget(b)
        self.mode = QComboBox()
        self.mode.addItem(_t("Hemen başlat"), "now")
        for q in self.mgr.queues():
            self.mode.addItem(_t("Kuyruğa ekle: {0}").format(q["name"]), q["id"])
        f = QFormLayout()
        f.addRow(_t("Kayıt klasörü:"), frow)
        f.addRow(_t("Ekledikten sonra:"), self.mode)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.ok = bb.button(QDialogButtonBox.Ok)
        self.ok.setText(_t("Ekle"))
        bb.accepted.connect(self._add)
        bb.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(info)
        lay.addWidget(self.edit)
        lay.addWidget(self.table, 1)
        lay.addWidget(self.count_lbl)
        lay.addLayout(f)
        lay.addWidget(bb)
        self._parse()

    def _pick_folder(self):
        p = QFileDialog.getExistingDirectory(self, _t("Kayıt klasörü"), self.folder.text() or self.mgr.settings["download_root"])
        if p:
            self.folder.setText(os.path.normpath(p))

    def urls(self):
        return extract_urls(self.edit.toPlainText())

    def _parse(self):
        urls = self.urls()
        old = {self.table.item(r, 3).text(): self.table.item(r, 0).checkState()
               for r in range(self.table.rowCount()) if self.table.item(r, 3)}
        self.table.setRowCount(len(urls))
        for r, u in enumerate(urls):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            chk.setCheckState(old.get(u, Qt.Checked))
            self.table.setItem(r, 0, chk)
            self.table.setItem(r, 3, QTableWidgetItem(u))
            self._show(r, u)
            if u not in self.info:
                self.info[u] = None  # sorgulanıyor
                threading.Thread(target=self._probe, args=(u,), daemon=True).start()
        self.count_lbl.setText(_t("{0} bağlantı bulundu").format(len(urls)))
        self.ok.setEnabled(bool(urls))

    def _probe(self, url):
        try:
            p = engine.probe(url)
            self.bridge.done.emit((url, (p.get("filename") or engine.filename_from_url(url), p.get("size"))), None)
        except Exception as e:  # noqa: BLE001
            self.bridge.done.emit((url, None), str(e))

    def _probed(self, res, err):
        url, info = res
        self.info[url] = info if info else ("!", err)
        for r in range(self.table.rowCount()):
            if self.table.item(r, 3) and self.table.item(r, 3).text() == url:
                self._show(r, url)

    def _show(self, r, url):
        info = self.info.get(url)
        if info is None:
            name, size = engine.filename_from_url(url) or "download", _t("denetleniyor…")
        elif info[0] == "!":
            name, size = engine.filename_from_url(url) or "download", _t("bilinmiyor")
            self.table.setItem(r, 1, QTableWidgetItem(name))
            self.table.item(r, 1).setToolTip(info[1] or "")
            self.table.setItem(r, 2, QTableWidgetItem(size))
            return
        else:
            name, size = info[0] or "download", fmt_size(info[1]) if info[1] else _t("bilinmiyor")
        self.table.setItem(r, 1, QTableWidgetItem(name))
        self.table.setItem(r, 2, QTableWidgetItem(size))

    def _add(self):
        mode = self.mode.currentData()
        n = 0
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).checkState() != Qt.Checked:
                continue
            url = self.table.item(r, 3).text()
            info = self.info.get(url)
            name = engine.sanitize_filename(info[0] if info and info[0] != "!" else
                                            engine.filename_from_url(url) or "download")
            folder = self.folder.text().strip() or self.mgr.category_dir(category_for(name))
            os.makedirs(folder, exist_ok=True)
            size = info[1] if info and info[0] != "!" else None
            it = self.mgr.add_http(url, os.path.join(folder, name), start=mode == "now", size=size)
            if mode != "now":
                self.mgr.set_queue(it.id, True, mode)
            n += 1
        self.mgr.save()
        self.win.statusBar().showMessage(_t("{0} indirme eklendi").format(n), 5000)
        self.accept()


class ChecksumDialog(QDialog):
    """İndirilen dosyanın MD5 / SHA-1 / SHA-256 özetini hesaplar; sitenin verdiği değerle karşılaştırır."""

    ALGOS = ("md5", "sha1", "sha256")

    def __init__(self, win, path):
        super().__init__(win)
        self.path = path
        self.setWindowTitle(_t("Dosya doğrulama"))
        self.setMinimumWidth(640)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.bridge = Bridge()
        self.bridge.done.connect(self._done)
        self.bridge.progress.connect(lambda a, b: self.bar.setValue(a))
        f = QFormLayout()
        name = QLabel(os.path.basename(path))
        name.setTextInteractionFlags(Qt.TextSelectableByMouse)
        f.addRow(_t("Dosya:"), name)
        self.out = {}
        for a in self.ALGOS:
            e = QLineEdit()
            e.setReadOnly(True)
            self.out[a] = e
            f.addRow(a.upper().replace("SHA", "SHA-") + ":", e)
        self.expected = QLineEdit()
        self.expected.setPlaceholderText(_t("Sitenin verdiği özeti buraya yapıştırın (MD5, SHA-1 ya da SHA-256)"))
        self.expected.textChanged.connect(self._compare)
        f.addRow(_t("Beklenen:"), self.expected)
        self.result = QLabel()
        self.result.setWordWrap(True)
        f.addRow(self.result)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.close)
        lay = QVBoxLayout(self)
        lay.addLayout(f)
        lay.addWidget(self.bar)
        lay.addWidget(close)
        self._cancel = False
        self.finished.connect(lambda *_: setattr(self, "_cancel", True))
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self):
        import hashlib
        hs = {a: hashlib.new(a) for a in self.ALGOS}
        try:
            total, done = os.path.getsize(self.path), 0
            with open(self.path, "rb") as fh:
                while not self._cancel:
                    chunk = fh.read(4 * 1024 * 1024)
                    if not chunk:
                        break
                    for h in hs.values():
                        h.update(chunk)
                    done += len(chunk)
                    self.bridge.progress.emit(int(done * 1000 / total) if total else 0, 1000)
            if not self._cancel:
                self.bridge.done.emit({a: h.hexdigest() for a, h in hs.items()}, None)
        except OSError as e:
            self.bridge.done.emit(None, str(e))

    def _done(self, res, err):
        if err:
            self.result.setText(_t("Dosya okunamadı: {0}").format(err))
            return
        for a, v in res.items():
            self.out[a].setText(v)
        self.bar.hide()
        self._compare()

    def _compare(self):
        want = re.sub(r"[^0-9a-f]", "", self.expected.text().lower())
        if not want or not self.out["sha256"].text():
            self.result.setText(_t("Hesaplanıyor…") if not self.out["sha256"].text() else "")
            return
        match = next((a for a in self.ALGOS if self.out[a].text() == want), None)
        if match:
            self.result.setText(_t("✔ Eşleşti ({0}): dosya sağlam.").format(match.upper()))
            self.result.setStyleSheet(f"color: {theme.T['ok']};")
        else:
            self.result.setText(_t("✖ Eşleşmedi: dosya bozuk ya da farklı bir dosya olabilir."))
            self.result.setStyleSheet(f"color: {theme.T['bad']};")


def ask_fields(parent, title, fields):
    """Küçük form penceresi. fields: [(etiket, başlangıç değeri, parola mı)] → değerler listesi ya da None."""
    d = QDialog(parent)
    d.setWindowTitle(title)
    f = QFormLayout(d)
    edits = []
    for label, value, secret in fields:
        e = QLineEdit(value)
        if secret:
            e.setEchoMode(QLineEdit.Password)
        f.addRow(label, e)
        edits.append(e)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(d.accept)
    bb.rejected.connect(d.reject)
    f.addRow(bb)
    return [e.text().strip() for e in edits] if d.exec() == QDialog.Accepted else None


# ------------------------------------------------------------------ güncellemeler
def update_note():
    return (_t("ℹ TurboDM sık güncelleniyor. Güncelleme sırasında program kısa süre kapanır; kurulum bitince görev çubuğunda kendiliğinden yeniden açılır ve inmekte olan indirmeleriniz kaldığı yerden devam eder. Bir şey yapmanıza gerek yok."))


class UpdateDialog(QDialog):
    """Yardım → Güncellemeleri denetle: TurboDM'in kendisi + YouTube motoru (yt-dlp)."""

    def __init__(self, win, prefetched=None):
        super().__init__(win)
        self.win, self.mgr = win, win.mgr
        self.info = None
        self._cancel = False
        self.setWindowTitle(_t("Güncellemeleri Denetle"))
        self.setMinimumWidth(540)
        self.setAttribute(Qt.WA_DeleteOnClose)

        # --- TurboDM
        self.app_lbl = QLabel(_t("TurboDM sürümü denetleniyor…"))
        self.app_lbl.setWordWrap(True)
        self.notes = QTextBrowser()
        self.notes.setMaximumHeight(150)
        self.notes.hide()
        self.app_bar = QProgressBar()
        self.app_bar.hide()
        # Sürümler sık çıktığı için: güncellemenin indirmeleri bozmadığını baştan söyle
        self.app_note = QLabel(update_note())
        self.app_note.setWordWrap(True)
        self.app_note.setStyleSheet(f"color: {theme.T['muted']};")
        self.app_note.hide()
        self.app_btn = QPushButton(_t("İndir ve Kur"))
        self.app_btn.hide()
        self.app_btn.clicked.connect(self._install)
        g1 = QGroupBox(_t("TurboDM  (kurulu: {0})").format(VERSION))
        l1 = QVBoxLayout(g1)
        l1.addWidget(self.app_lbl)
        l1.addWidget(self.notes)
        l1.addWidget(self.app_note)
        l1.addWidget(self.app_bar)
        r1 = QHBoxLayout()
        r1.addStretch()
        r1.addWidget(self.app_btn)
        l1.addLayout(r1)

        # --- yt-dlp
        self.yt_lbl = QLabel(_t("Video motoru denetleniyor…"))
        self.yt_lbl.setWordWrap(True)
        self.yt_btn = QPushButton(_t("Video motorunu güncelle"))
        self.yt_btn.hide()
        self.yt_btn.clicked.connect(self._update_ytdlp)
        g2 = QGroupBox(_t("Video motoru"))
        l2 = QVBoxLayout(g2)
        l2.addWidget(self.yt_lbl)
        r2 = QHBoxLayout()
        r2.addStretch()
        r2.addWidget(self.yt_btn)
        l2.addLayout(r2)

        close = QPushButton(_t("Kapat"))
        close.clicked.connect(self.close)
        lay = QVBoxLayout(self)
        lay.addWidget(g1)
        lay.addWidget(g2)
        rb = QHBoxLayout()
        rb.addStretch()
        rb.addWidget(close)
        lay.addLayout(rb)

        self.b_app, self.b_yt = Bridge(), Bridge()
        self.b_app.done.connect(self._on_app)
        self.b_app.progress.connect(self._on_app_progress)
        self.b_yt.done.connect(self._on_yt)
        if prefetched:
            self._on_app(prefetched, None)
        else:
            self._run(self.b_app, self._check_app)
        self._run(self.b_yt, ytdlp.update_available)

    @staticmethod
    def _run(bridge, fn, *a):
        def work():
            try:
                bridge.done.emit(fn(*a), None)
            except Exception as e:  # noqa: BLE001
                bridge.done.emit(None, str(e))
        threading.Thread(target=work, daemon=True).start()

    def _check_app(self):
        url = updater.manifest_url(self.mgr.settings.get("update_repo") or None)
        if not url:
            raise RuntimeError(_t("Güncelleme sunucusu ayarlanmamış."))
        return updater.check(url)

    # ---- TurboDM
    def _on_app(self, info, err):
        if err:
            if self.app_bar.isVisible():  # indirme sırasında
                self.app_bar.hide()
                self.app_btn.setEnabled(True)
                self.app_lbl.setText(_t("Güncelleme başarısız: {0}").format(err))
            else:
                self.app_lbl.setText(_t("Denetlenemedi: {0}").format(err))
            return
        if isinstance(info, str):  # indirme bitti → kurulum dosyasının yolu
            self.app_lbl.setText(_t("Kurulum başlatılıyor… TurboDM kısa süre kapanacak, kurulum bitince görev çubuğunda kendiliğinden açılacak; inmekte olan indirmeler kaldığı yerden sürecek."))
            try:
                updater.run_installer(info)
            except OSError as e:
                self.app_lbl.setText(_t("Kurulum başlatılamadı: {0}").format(e))
                self.app_btn.setEnabled(True)
            return
        self.info = info
        if not info["available"]:
            self.app_lbl.setText(_t("✔ TurboDM güncel (sürüm {0}).").format(info['current']))
            return
        what = _t("aynı sürümün yeni bir derlemesi") if info["same_version"] else _t("yeni sürüm {0}").format(info['latest'])
        when = f" · {info['published']}" if info.get("published") else ""
        size = f" · {fmt_size(info['size'])}" if info.get("size") else ""
        self.app_lbl.setText(_t("<b>Güncelleme var:</b> {0}{1}{2}").format(what, when, size))
        # sürüm notları programın dilinde: Türkçe ya da (diğer diller için) İngilizce
        notes = info.get("notes") if i18n.language() == "tr" else (info.get("notes_en") or info.get("notes"))
        if notes:
            self.notes.setPlainText(notes)
            self.notes.show()
        self.app_note.show()
        self.app_btn.show()

    def _install(self):
        self.app_btn.setEnabled(False)
        self.app_bar.show()
        self.app_bar.setRange(0, 0)
        self.app_lbl.setText(_t("Kurulum dosyası indiriliyor ve doğrulanıyor…"))
        self._run(self.b_app, updater.download, self.info,
                  lambda got, total: self.b_app.progress.emit(got, total), lambda: self._cancel)

    def _on_app_progress(self, got, total):
        if total:
            self.app_bar.setRange(0, 1000)
            self.app_bar.setValue(int(got / total * 1000))
        self.app_bar.setFormat(f"{fmt_size(got)} / {fmt_size(total)}" if total else fmt_size(got))

    # ---- yt-dlp
    def _on_yt(self, res, err):
        if err:
            self.yt_lbl.setText(_t("Denetlenemedi: {0}").format(err))
            return
        if isinstance(res, str):  # güncelleme yapıldı
            self.yt_lbl.setText(_t("✔ Video motoru güncellendi: {0}").format(res))
            self.yt_btn.hide()
            return
        cur, latest, avail = res
        if avail:
            self.yt_lbl.setText(_t("Güncelleme var: kurulu {0} → en son {1}. Video siteleri değişiklik yaptığında indirmeler bozulabilir; güncel tutmanız önerilir.").format(cur or '—', latest))
            self.yt_btn.show()
        else:
            self.yt_lbl.setText(_t("✔ Video motoru güncel ({0}).").format(cur))

    def _update_ytdlp(self):
        self.yt_btn.setEnabled(False)
        self.yt_lbl.setText(_t("İndiriliyor ve doğrulanıyor…"))
        self._run(self.b_yt, ytdlp.update)

    def closeEvent(self, e):
        self._cancel = True
        super().closeEvent(e)


# ------------------------------------------------------------------ ana pencere
COLUMNS = []
ACTION_TEXT = {}


@i18n.on_change
def _column_texts():
    COLUMNS[:] = ["", _t("Dosya Adı"), _t("Boyut"), _t("Durum"), _t("Kalan Süre"), _t("Aktarım Hızı"), _t("Son Deneme"),
                  _t("Açıklama"), _t("Eklenme"), _t("Bitiş")]
    ACTION_TEXT.update(play=_t("Devam Et"), pause=_t("Durdur"), folder=_t("Klasörü aç"), retry=_t("Tekrar Dene"),
                       more=_t("Diğer"))
SEL = 0    # onay kutusu sütunu (toplu seçim)
NAME = 1
SIZE = 2
STATUS = 3
ETA = 4
SPEED = 5
ACTIONS = 10  # başlıksız son sütun: satırdaki işlem düğmeleri (göster/gizle menüsünde yok)
ROW_HEIGHT = 56
GROUP_HEIGHT = 30
CAT_ICONS = {"compressed": "compressed", "documents": "document", "music": "music", "programs": "program",
             "video": "video", "torrent": "magnet", "general": "general"}
PROGRESS_ROLE = Qt.UserRole + 1   # durum hücresi: 0..1 ilerleme (yoksa None)
TONE_ROLE = Qt.UserRole + 2       # durum hücresi: renk (accent | ok | bad | muted)
SEG_ROLE = Qt.UserRole + 3        # durum hücresi: (toplam, [(başlangıç, bitiş, konum), ...]) parçalı çubuk için
DETAIL_ROLE = Qt.UserRole + 4     # durum hücresi: sağdaki miktar yazısı ("317 MB / 512 MB")
ACTIVE_ROLE = Qt.UserRole + 2     # ad hücresi: iniyor mu (simge zemini vurgulu)
SUB_ROLE = Qt.UserRole + 3        # ad hücresi: alt satır (kategori, bağlantı sayısı, bitiş zamanı…)
ACTIONS_ROLE = Qt.UserRole + 3    # işlem hücresi: düğme adları
GROUP_ROLE = Qt.UserRole + 5      # grup satırı: (başlık, sayı)


COUNT_ROLE = Qt.UserRole + 2      # kenar çubuğu: kategorideki indirme sayısı


class NavDelegate(QStyledItemDelegate):
    """Kenar çubuğu: kategori adı + sağda soluk renkte indirme sayısı (aynı yuvarlatılmış satırda). Seçili satırda
    kalın yazı ve kenarda vurgu çizgisi; anahtarı olmayan satır bölüm başlığıdır ("Kategoriler")."""

    def sizeHint(self, option, index):
        s = super().sizeHint(option, index)
        return QSize(s.width() + 30, max(s.height(), 34))  # ferah satırlar + sayı için yer

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        if option.state & QStyle.State_Selected:
            option.font.setBold(True)

    def paint(self, p, option, index):
        if index.data(Qt.UserRole) is None:  # bölüm başlığı
            p.save()
            f = QFont(option.font)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor(theme.T["muted"]))
            p.drawText(option.rect.adjusted(10, 6, -10, 0), Qt.AlignLeft | Qt.AlignVCenter, index.data())
            p.restore()
            return
        super().paint(p, option, index)
        sel = option.state & QStyle.State_Selected
        n = index.data(COUNT_ROLE)
        if n:
            p.save()
            p.setPen(QColor(theme.T["accent_text"] if sel else theme.T["muted"]))
            p.drawText(option.rect.adjusted(10, 0, -10, 0), Qt.AlignRight | Qt.AlignVCenter, str(n))  # Arapçada sola geçer
            p.restore()
        if sel:
            p.save()
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.T["accent"]))
            r = option.rect
            x = r.right() - 2 if option.direction == Qt.RightToLeft else r.left()
            p.drawRoundedRect(QRectF(x, r.top() + 8, 3, r.height() - 16), 1.5, 1.5)
            p.restore()


class CheckDelegate(QStyledItemDelegate):
    """Seçim sütunu: temaya göre çizilen, her iki temada da belirgin onay kutusu. Grup satırı da bu sütundan
    bütün satıra yayılır (İndiriliyor, Bekleyen, Tamamlanan)."""

    def paint(self, p, option, index):
        group = index.data(GROUP_ROLE)
        if group:
            p.save()
            r = option.rect
            p.fillRect(r, QColor(theme.T["bg"]))
            p.setPen(QColor(theme.T["border_soft"]))
            p.drawLine(r.bottomLeft(), r.bottomRight())
            f = QFont(option.font)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor(theme.T["muted"]))
            p.drawText(r.adjusted(14, 0, -14, 0), Qt.AlignLeft | Qt.AlignVCenter, f"{group[0]}   {group[1]}")
            p.restore()
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        checked = Qt.CheckState(index.data(Qt.CheckStateRole) or 0) == Qt.Checked
        opt.features &= ~QStyleOptionViewItem.HasCheckIndicator
        opt.text = ""
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, p, opt.widget)  # zemin ve seçim
        c = QRectF(opt.rect).center()
        box = QRectF(c.x() - 8, c.y() - 8, 16, 16)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        if checked:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.T["accent"]))
            p.drawRoundedRect(box, 4, 4)
            pen = QPen(QColor("#ffffff"), 2)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            path = QPainterPath(QPointF(box.x() + 4, box.y() + 8.5))
            path.lineTo(box.x() + 7, box.y() + 11.5)
            path.lineTo(box.x() + 12, box.y() + 5)
            p.drawPath(path)
        else:
            p.setPen(QPen(QColor(theme.T["muted"]), 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(box.adjusted(0.75, 0.75, -0.75, -0.75), 3.5, 3.5)
        if opt.state & QStyle.State_Selected:  # seçili satırın kenarındaki vurgu çizgisi
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.T["accent"]))
            r = opt.rect
            p.drawRect(QRectF(r.right() - 2 if opt.direction == Qt.RightToLeft else r.left(), r.top(), 3, r.height()))
        p.restore()


class NameDelegate(QStyledItemDelegate):
    """Dosya adı sütunu: dosya türü simgesi, kalın ad, altında soluk bilgi satırı."""

    def paint(self, p, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text, icon, opt.text, opt.icon = opt.text, QIcon(opt.icon), "", QIcon()
        opt.features &= ~QStyleOptionViewItem.HasDecoration
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, p, opt.widget)  # zemin ve seçim
        r = opt.rect
        tile = QStyle.visualRect(opt.direction, r, QRect(r.left() + 2, r.center().y() - 18, 36, 36))
        text_r = QStyle.visualRect(opt.direction, r, QRect(r.left() + 48, r.top(), max(0, r.width() - 52), r.height()))
        active = index.data(ACTIVE_ROLE)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.T["accent_soft" if active else "surface2"]))
        p.drawRoundedRect(QRectF(tile), 9, 9)
        icon.paint(p, tile.adjusted(9, 9, -9, -9))
        f = QFont(opt.font)
        f.setBold(True)
        fm = QFontMetrics(f)
        sub = index.data(SUB_ROLE) or ""
        mid = r.center().y()
        top = QRect(text_r.left(), mid - fm.height() - (0 if sub else -fm.height() // 2), text_r.width(), fm.height())
        p.setFont(f)
        p.setPen(QColor(theme.T["text"]))
        p.drawText(top, Qt.AlignLeft | Qt.AlignVCenter, fm.elidedText(text, Qt.ElideRight, top.width()))
        if sub:
            p.setFont(opt.font)
            p.setPen(QColor(theme.T["muted"]))
            low = QRect(text_r.left(), mid + 1, text_r.width(), opt.fontMetrics.height())
            p.drawText(low, Qt.AlignLeft | Qt.AlignVCenter, opt.fontMetrics.elidedText(sub, Qt.ElideRight, low.width()))
        p.restore()


class ActionDelegate(QStyledItemDelegate):
    """Satırdaki işlem düğmeleri: fare üstündeyken zemin alır, tıklamayı DownloadTable yakalar."""

    BUTTON = 30
    GAP = 4

    @classmethod
    def rects(cls, cell, names, fm, direction):
        """{ad: dikdörtgen}: düğmeler satırın sonuna hizalı, "retry" yazılı düğmedir."""
        out, x = {}, cell.right() - 8
        for name in reversed(names):
            w = fm.horizontalAdvance(ACTION_TEXT.get("retry", "")) + 20 if name == "retry" else cls.BUTTON
            x -= w
            r = QRect(x, cell.center().y() - cls.BUTTON // 2, w, cls.BUTTON)
            out[name] = QStyle.visualRect(direction, cell, r)
            x -= cls.GAP
        return out

    def paint(self, p, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, p, opt.widget)  # zemin ve seçim
        hover = getattr(opt.widget, "action_hover", None)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        for name, r in self.rects(opt.rect, index.data(ACTIONS_ROLE) or (), opt.fontMetrics, opt.direction).items():
            on = hover == (index.row(), name)
            if name == "retry":
                bad = QColor(theme.T["bad"])
                bad.setAlpha(60 if on else 32)
                p.setPen(Qt.NoPen)
                p.setBrush(bad)
                p.drawRoundedRect(QRectF(r), 7, 7)
                f = QFont(opt.font)
                f.setBold(True)
                p.setFont(f)
                p.setPen(QColor(theme.T["bad"]))
                p.drawText(r, Qt.AlignCenter, ACTION_TEXT.get("retry", ""))
                continue
            if on:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(theme.T["surface2"]))
                p.drawRoundedRect(QRectF(r), 7, 7)
            theme.icon(name).paint(p, r.adjusted(7, 7, -7, -7))
        p.restore()


class StatusDelegate(QStyledItemDelegate):
    """Durum sütunu: ilerleme varsa yüzde, miktar ve altında bağlantı başına parçalı çubuk; yoksa simge ve yazı.
    Tamamlanan yeşil, hatalı kırmızı yazılır. Renkler temaya göre."""

    def paint(self, p, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text, icon, opt.text, opt.icon = opt.text, QIcon(opt.icon), "", QIcon()
        opt.features &= ~QStyleOptionViewItem.HasDecoration
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, p, opt.widget)  # zemin ve seçim
        frac = index.data(PROGRESS_ROLE)
        tone = index.data(TONE_ROLE) or "text"
        r = opt.rect.adjusted(8, 0, -8, 0)
        color = QColor(theme.T.get(tone, theme.T["text"]))
        f = QFont(opt.font)
        f.setBold(tone in ("accent", "ok", "bad"))
        fm = QFontMetrics(f)
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        if frac is None:
            if not icon.isNull():
                ic = QStyle.visualRect(opt.direction, r, QRect(r.left(), r.center().y() - 8, 16, 16))
                icon.paint(p, ic)
                r = QStyle.visualRect(opt.direction, opt.rect, QRect(r.left() + 22, r.top(), r.width() - 22, r.height()))
            p.setFont(f)
            p.setPen(color)
            p.drawText(r, Qt.AlignVCenter | Qt.AlignLeft, fm.elidedText(text, Qt.ElideRight, r.width()))
            p.restore()
            return
        top = QRect(r.left(), r.center().y() - 15, r.width(), 20)
        detail = index.data(DETAIL_ROLE) or ""
        p.setFont(opt.font)
        p.setPen(QColor(theme.T["muted"]))
        p.drawText(top, Qt.AlignVCenter | Qt.AlignRight, detail)
        used = opt.fontMetrics.horizontalAdvance(detail) + 8 if detail else 0
        p.setFont(f)
        p.setPen(color)
        p.drawText(top, Qt.AlignVCenter | Qt.AlignLeft, fm.elidedText(text, Qt.ElideRight, max(0, top.width() - used)))
        self._draw_bar(p, QRectF(r.left(), r.center().y() + 8, r.width(), 6), frac, index.data(SEG_ROLE),
                       theme.T["accent"] if tone in ("accent", "ok") else theme.T["muted"], opt.direction)
        p.restore()

    @staticmethod
    def _draw_bar(p, bar, frac, segs, color, direction):
        """Çubuk: bağlantı parçaları biliniyorsa her biri ayrı (aralarında ince boşluk), yoksa tek parça."""
        total, spans = (segs[0], [(a, b + 1, pos) for a, b, pos in segs[1]]) if segs else (1.0, [(0.0, 1.0, min(1.0, frac))])
        rtl = direction == Qt.RightToLeft
        p.setPen(Qt.NoPen)
        if sum(end - a for a, end, _ in spans) < total:  # HLS yalnız biten parçaları verir: kalanı boş çubuk görünsün
            p.setBrush(QColor(theme.T["track"]))
            p.drawRoundedRect(bar, 1.5, 1.5)
        for a, end, pos in spans:
            x = bar.left() + a / total * bar.width()
            w = (end - a) / total * bar.width() - (2 if end < total else 0)
            if w <= 0:
                continue
            filled = min(w, max(0.0, (min(pos, end) - a) / (end - a)) * w)
            p.setBrush(QColor(theme.T["track"]))
            p.drawRoundedRect(QRectF(bar.right() - (x - bar.left()) - w if rtl else x, bar.top(), w, bar.height()), 1.5, 1.5)
            if filled > 0:
                filled = max(1.5, filled)
                p.setBrush(QColor(color))
                p.drawRoundedRect(QRectF(bar.right() - (x - bar.left()) - filled if rtl else x, bar.top(), filled, bar.height()),
                                  1.5, 1.5)


class DownloadTable(QTableWidget):
    """İndirme listesi. Onay kutusu sütununa tıklamak satırı diğer seçimleri bozmadan seçime ekler/çıkarır
    (dokunmatik ekranda ve Ctrl tuşu bilmeyenler için toplu seçim); kutular seçimi gösterir. Satırdaki işlem
    düğmeleri seçimi değiştirmez; tıklanınca action_clicked(satır, düğme adı) yayınlanır."""

    action_clicked = Signal(int, str)

    def __init__(self, *a):
        super().__init__(*a)
        self.action_hover = None
        self._action_pressed = None
        self.setMouseTracking(True)

    def _action_at(self, pos):
        """Bu noktadaki işlem düğmesi: (satır, ad) ya da None."""
        idx = self.indexAt(pos)
        if not idx.isValid() or idx.column() != ACTIONS:
            return None
        rects = ActionDelegate.rects(self.visualRect(idx), idx.data(ACTIONS_ROLE) or (), self.fontMetrics(),
                                     self.layoutDirection())
        return next(((idx.row(), n) for n, r in rects.items() if r.contains(pos)), None)

    def selectionCommand(self, index, event=None):
        from PySide6.QtCore import QEvent, QItemSelectionModel
        if self._action_pressed:  # düğmeye tıklanırken (fare kıpırdasa, bırakılsa da) seçim değişmez
            return QItemSelectionModel.NoUpdate
        if (index.isValid() and index.column() == SEL and event is not None
                and event.type() == QEvent.MouseButtonPress):
            return QItemSelectionModel.Toggle | QItemSelectionModel.Rows
        return super().selectionCommand(index, event)

    def _is_group(self, row):
        cell = self.item(row, SEL)
        return bool(cell and cell.data(GROUP_ROLE))

    def moveCursor(self, action, modifiers):
        """Klavye gezinmesi grup satırına düşmez, orada takılmaz: yukarı/aşağı atlar, sayfa tuşları komşusuna gider."""
        cur = self.currentIndex()
        step = -1 if action in (QAbstractItemView.MoveUp, QAbstractItemView.MovePageUp) else 1
        if action in (QAbstractItemView.MoveUp, QAbstractItemView.MoveDown):
            r = cur.row() + step if cur.isValid() else 0 if step > 0 else self.rowCount() - 1
            col = cur.column() if cur.isValid() else NAME
        else:
            idx = super().moveCursor(action, modifiers)
            if not idx.isValid():
                return idx
            r, col = idx.row(), idx.column()
        while 0 <= r < self.rowCount() and self._is_group(r):
            r += step
        return self.model().index(r, col) if 0 <= r < self.rowCount() else cur

    def mousePressEvent(self, e):
        self._action_pressed = self._action_at(e.position().toPoint()) if e.button() == Qt.LeftButton else None
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        hit = self._action_pressed
        super().mouseReleaseEvent(e)
        self._action_pressed = None
        if hit and e.button() == Qt.LeftButton and hit == self._action_at(e.position().toPoint()):
            self.action_clicked.emit(*hit)

    def mouseMoveEvent(self, e):
        hover = self._action_at(e.position().toPoint())
        if hover != self.action_hover:
            self.action_hover = hover
            self.viewport().update()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        if self.action_hover:
            self.action_hover = None
            self.viewport().update()
        super().leaveEvent(e)

    def viewportEvent(self, e):
        if e.type() == QEvent.Leave and self.action_hover:  # başlığa geçerken tablonun kendi leaveEvent'i gelmez
            self.action_hover = None
            self.viewport().update()
        if e.type() == QEvent.ToolTip:
            hit = self._action_at(e.pos())
            if hit:
                QToolTip.showText(e.globalPos(), ACTION_TEXT.get(hit[1], ""), self.viewport())
                return True
        return super().viewportEvent(e)


class MainWindow(QMainWindow):
    def __init__(self, mgr: Manager):
        super().__init__()
        self.mgr = mgr
        self.icon = load_icon()
        QApplication.setWindowIcon(self.icon)
        self.setWindowIcon(self.icon)
        area = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1280, area.width()), min(720, area.height() - 40))  # 40: başlık çubuğu; küçük ekrana da sığsın
        self.setAcceptDrops(True)
        self.progress_dialogs = {}
        self._visible = []  # filtreye uyan indirmeler
        self._rows = []     # tablo satırları: indirme kimliği ya da grup satırı (başlık, sayı)
        self._filter = "all"
        self._last_clip = ""
        self._quitting = False

        app = QApplication.instance()
        # kullanıcının seçtiği tema; pencere başlığı rengi ve yeni pencereleri ortalama da burada kurulur
        theme.install(app, mgr.settings.get("theme", "auto"))
        self._build_actions()
        self._build_ui()
        self._build_tray()
        theme.notifier.changed.connect(self._theme_changed)

        try:
            self._fmt_cache = {}
            self._handoffs = {}  # tarayıcıdan devralınan indirmeler: kimlik -> {"iid", "closed", "t"}
            self._started = time.time()  # bundan önce başlamış ama bilinmeyen devir: TurboDM o sırada kapanmış
            self._error_boxes = {}  # açık hata uyarıları: iid -> QMessageBox
            server.handlers["/formats"] = self._formats_handler
            server.handlers["/check"] = self._check_handler
            server.handlers["/handoff"] = self._handoff_handler
            self.srv = server.start(mgr.settings["server_port"])
        except OSError as e:
            self.srv = None
            self.statusBar().showMessage(_t("Tarayıcı köprüsü başlatılamadı: {0}").format(e), 10000)

        QApplication.clipboard().dataChanged.connect(self._on_clipboard)
        QTimer.singleShot(8000, self._auto_update_check)
        self.timer = QTimer(self, interval=500, timeout=self._tick)
        self.timer.start()
        self._smooth = {}  # iid -> SmoothProgress (listedeki akıcı yüzde/hız)
        self.anim = QTimer(self, interval=50, timeout=self._animate_rows)
        self.anim.start()
        self.refresh(force=True)

    # ---------------------------------------------------------- kurulum
    def _act(self, text, icon, slot, shortcut=None):
        """icon: theme.py'deki simge adı (tema değişince yeniden renklenir)."""
        a = QAction(theme.icon(icon) if icon else QIcon(), text, self)
        a.setProperty("tdm_icon", icon)
        a.triggered.connect(slot)
        if shortcut:
            a.setShortcut(shortcut)
        return a

    def _build_actions(self):
        self.a_add = self._act(_t("URL Ekle"), "add", self.add_url_prompt, "Ctrl+N")
        self.a_torrent = self._act(_t("Torrent Ekle"), "torrent", self.add_torrent_prompt, "Ctrl+T")
        self.a_magnet = self._act(_t("Magnet Ekle"), "magnet", self.add_magnet_prompt, "Ctrl+M")
        self.a_resume = self._act(_t("Devam Et"), "play", self.resume_selected)
        self.a_stop = self._act(_t("Durdur"), "pause", self.stop_selected)
        self.a_stop_all = self._act(_t("Tümünü Durdur"), "stop", self.mgr.stop_all)
        self.a_delete = self._act(_t("Sil"), "trash", lambda: self.delete_selected(False), "Del")
        self.a_delete_done = self._act(_t("Bitenleri Sil"), "trash_done", self.delete_completed)
        self.a_select_all = self._act(_t("Tümünü seç"), "finished", self.select_all, "Ctrl+A")
        self.a_select_none = self._act(_t("Seçimi kaldır"), None, lambda: self.table.clearSelection(), "Esc")
        self.a_options = self._act(_t("Seçenekler"), "settings", self.open_options)
        self.a_sched = self._act(_t("Zamanlayıcı"), "clock", lambda: SchedulerDialog(self, self._current_queue()).exec())
        self.a_qstart = self._act(_t("Kuyruğu Başlat"), "queue_start", lambda: self.mgr.start_queue(self._current_queue()))
        self.a_qstop = self._act(_t("Kuyruğu Durdur"), "queue_stop", lambda: self.mgr.stop_queue(self._current_queue()))
        self.a_group = QAction(_t("Gruplara ayır"), self)
        self.a_group.setCheckable(True)
        self.a_group.setChecked(bool(self.mgr.settings.get("group_list", True)))
        self.a_group.toggled.connect(self._set_grouping)
        self.a_batch = self._act(_t("Toplu indirme ekle…"), "add", self.batch_add_prompt, "Ctrl+Shift+N")
        self.a_export = self._act(_t("Listeyi dışa aktar…"), None, self.export_list)
        self.a_import = self._act(_t("Listeyi içe aktar…"), None, self.import_list)
        self.a_quit = self._act(_t("Çıkış"), "quit", self.quit_requested, "Ctrl+Q")
        self.a_update = self._act(_t("Güncellemeleri denetle…"), "refresh", self.check_updates)

    def _theme_changed(self):
        """Windows açık/koyu moda geçti ya da tema seçildi: simgeleri yeni renklerle yeniden çiz."""
        for a in self.findChildren(QAction):
            name = a.property("tdm_icon")
            if name:
                a.setIcon(theme.icon(name))
        self._new_btn.setIcon(theme.icon("plus", "#ffffff"))
        self._new_menu_btn.setIcon(theme.icon("chevron", "#ffffff"))
        self._more_btn.setIcon(theme.icon("chevron", "muted"))
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for it in [top] + [top.child(j) for j in range(top.childCount())]:
                if it.data(0, Qt.UserRole + 1):  # bölüm başlığının simgesi yok
                    it.setIcon(0, theme.icon(it.data(0, Qt.UserRole + 1)))
        for r in range(self.table.rowCount()):  # durum simgeleri yeniden
            cell = self.table.item(r, NAME)
            if cell:
                cell.setData(Qt.UserRole, None)
        self.refresh(force=True)
        if not self.mgr.torrents:
            self.a_torrent.setEnabled(False)
            self.a_magnet.setEnabled(False)

    def _build_ui(self):
        self.setWindowTitle(_t("{0} — İnternet İndirme Yöneticisi").format(APP_NAME))
        mb = self.menuBar()
        m = mb.addMenu(_t("&Görevler"))
        for a in (self.a_add, self.a_batch, self.a_torrent, self.a_magnet):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_export)
        m.addAction(self.a_import)
        m.addSeparator()
        m.addAction(self.a_quit)
        m = mb.addMenu(_t("&İndirmeler"))
        for a in (self.a_resume, self.a_stop, self.a_stop_all, None, self.a_delete,
                  self.a_delete_done, None, self.a_qstart, self.a_qstop, self.a_sched, None, self.a_options):
            m.addSeparator() if a is None else m.addAction(a)
        m.addSeparator()
        self._add_select_menu(m.addMenu(_t("Toplu seçim")))
        m = mb.addMenu(_t("&Yardım"))
        m.addAction(self.a_update)
        m.addAction(theme.icon("document"), _t("Sürüm notları"), lambda: QDesktopServices.openUrl(
            QUrl(f"https://github.com/{UPDATE_REPO}/blob/main/"
                 + ("SURUM_NOTLARI.md" if i18n.language() == "tr" else "RELEASE_NOTES.md"))))
        m.addSeparator()
        m.addAction(_t("Hakkında"), lambda: QMessageBox.about(
            self, APP_NAME, _t("<b>{0}</b> {1}<br>Çok bağlantılı HTTP/HTTPS, FTP, video (HLS/DASH) ve BitTorrent indirme yöneticisi.<br><br>Özgür yazılım: GNU GPL v3 lisansı. Kaynak kodu: <a href=\"https://github.com/{2}\">github.com/{3}</a>").format(APP_NAME, VERSION, UPDATE_REPO, UPDATE_REPO)))
        self._build_language_menu(mb)

        self.tree = QTreeWidget()
        self.tree.setObjectName("nav")
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setIndentation(16)
        self.tree.setIconSize(QSize(18, 18))
        self.tree.setFocusPolicy(Qt.NoFocus)
        self.tree.setItemDelegate(NavDelegate(self.tree))
        def nav_item(text, key, ic):
            it = QTreeWidgetItem([text])
            it.setData(0, Qt.UserRole, key)
            it.setData(0, Qt.UserRole + 1, ic)
            it.setIcon(0, theme.icon(ic))
            return it
        root = nav_item(_t("Tüm İndirmeler"), "all", "all")
        self.tree.addTopLevelItem(root)
        for text, key, ic in ((_t("Bitmemiş"), "unfinished", "unfinished"), (_t("Bitmiş"), "finished", "finished"),
                              (_t("Kuyruk"), "queue", "queue")):
            node = nav_item(text, key, ic)
            if key == "queue" and len(self.mgr.queues()) > 1:
                for q in self.mgr.queues():
                    node.addChild(nav_item(q["name"], "queue:" + q["id"], "queue"))
            self.tree.addTopLevelItem(node)
        head = QTreeWidgetItem([_t("Kategoriler")])  # seçilemeyen bölüm başlığı
        head.setFlags(Qt.NoItemFlags)
        self.tree.addTopLevelItem(head)
        for key, (disp, _, _) in CATEGORIES.items():
            self.tree.addTopLevelItem(nav_item(disp, "cat:" + key, CAT_ICONS.get(key, "general")))
        self.tree.expandAll()
        self.tree.setItemsExpandable(False)
        self.tree.setCurrentItem(root)
        self.tree.currentItemChanged.connect(self._filter_changed)

        self.table = DownloadTable(0, ACTIONS + 1)
        self.table.setObjectName("list")
        self.table.setItemDelegateForColumn(SEL, CheckDelegate(self.table))
        self.table.setItemDelegateForColumn(NAME, NameDelegate(self.table))
        self.table.setItemDelegateForColumn(STATUS, StatusDelegate(self.table))
        self.table.setItemDelegateForColumn(ACTIONS, ActionDelegate(self.table))
        self.table.action_clicked.connect(self._row_action)
        self.table.setIconSize(QSize(18, 18))
        self.table.setHorizontalHeaderLabels(COLUMNS + [""])
        self.table.horizontalHeaderItem(SEL).setToolTip(_t("Tümünü seç / seçimi kaldır"))
        # başlığa tıklamak sütunu (satır seçiminde bütün listeyi) seçmesin; yalnızca kutu başlığı seçim yapar
        self.table.horizontalHeader().sectionPressed.disconnect()
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.horizontalHeader().sectionClicked.connect(self._header_clicked)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        for a in (self.a_select_all, self.a_select_none):  # kısayollar liste odaktayken çalışsın
            a.setShortcutContext(Qt.WidgetWithChildrenShortcut)
            self.table.addAction(a)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.doubleClicked.connect(self._double_click)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(NAME, QHeaderView.Stretch)
        h.setSectionResizeMode(SEL, QHeaderView.Fixed)
        h.setSectionResizeMode(ACTIONS, QHeaderView.Fixed)
        for c, w in ((SEL, 40), (SIZE, 85), (STATUS, 235), (ETA, 95), (SPEED, 105), (6, 130), (7, 150), (8, 130),
                     (9, 130), (ACTIONS, 125)):
            self.table.setColumnWidth(c, max(w, h.sectionSizeHint(c)) if c in (SIZE, ETA, SPEED) else w)  # uzun başlık kırpılmasın
        retry = self.table.fontMetrics().horizontalAdvance(ACTION_TEXT.get("retry", "")) + 20  # uzun çeviri sütundan taşmasın
        self.table.setColumnWidth(ACTIONS, max(125, retry + ActionDelegate.BUTTON + ActionDelegate.GAP + 16))
        h.moveSection(h.visualIndex(SPEED), h.visualIndex(ETA))  # sıra: hız, kalan süre
        for c in range(NAME, ACTIONS):
            right = c in (SIZE, ETA, SPEED)
            self.table.horizontalHeaderItem(c).setTextAlignment((Qt.AlignRight if right else Qt.AlignLeft) | Qt.AlignVCenter)
        self._update_sort_indicator()
        # sütun başlığına sağ tık: sütunları göster/gizle (seçim ve dosya adı her zaman görünür)
        h.setContextMenuPolicy(Qt.CustomContextMenu)
        h.customContextMenuRequested.connect(self._column_menu)
        st = self.mgr.settings
        if not st.get("columns_v2"):  # yeni görünüm: ek sütunlar başta kapalı, sütun başlığına sağ tıkla açılır
            st["hidden_columns"] = sorted({c for c in st.get("hidden_columns") or [] if isinstance(c, int)} | {6, 7, 8, 9})
            st["columns_v2"] = True
        for c in st["hidden_columns"]:
            if isinstance(c, int) and NAME < c < len(COLUMNS):
                self.table.setColumnHidden(c, True)

        body = QWidget()
        lay = QHBoxLayout(body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._build_sidebar())
        line = QFrame()  # kenarlık değil ayrı çizgi: Arapçada yan menüyle birlikte yer değiştirir
        line.setObjectName("sideLine")
        line.setFixedWidth(1)
        lay.addWidget(line)
        lay.addWidget(self._build_main_area(), 1)
        self.setCentralWidget(body)
        self.sel_lbl = QLabel()
        self.statusBar().addPermanentWidget(self.sel_lbl)
        self.speed_lbl = QLabel()
        self.statusBar().addPermanentWidget(self.speed_lbl)
        self.table.setFocus()  # açılışta odak "Yeni İndirme"ye gitmesin: Ctrl+A, Esc liste odaktayken çalışır

    def _build_sidebar(self):
        """Sol sütun: "Yeni İndirme" düğmesi (okundan diğer ekleme yolları), gezinme, en altta Seçenekler."""
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(236)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(12, 16, 12, 10)
        lay.setSpacing(14)
        row = QHBoxLayout()
        row.setSpacing(2)
        self._new_btn = QToolButton()
        self._new_btn.setObjectName("newDownload")
        self._new_btn.setText(_t("Yeni İndirme"))
        self._new_btn.setToolTip(self.a_add.toolTip())
        self._new_btn.setIcon(theme.icon("plus", "#ffffff"))
        self._new_btn.setIconSize(QSize(16, 16))
        self._new_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._new_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._new_btn.clicked.connect(self.a_add.trigger)
        self._new_menu_btn = QToolButton()
        self._new_menu_btn.setObjectName("newDownloadMenu")
        self._new_menu_btn.setIcon(theme.icon("chevron", "#ffffff"))
        self._new_menu_btn.setIconSize(QSize(14, 14))
        self._new_menu_btn.setToolTip(_t("Diğer"))
        self._new_menu_btn.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self._new_menu_btn)
        for a in (self.a_add, self.a_batch, self.a_torrent, self.a_magnet):
            menu.addAction(a)
        self._new_menu_btn.setMenu(menu)
        self._new_menu_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        row.addWidget(self._new_btn, 1)
        row.addWidget(self._new_menu_btn)
        lay.addLayout(row)
        lay.addWidget(self.tree, 1)
        options = QToolButton()
        options.setObjectName("sideButton")
        options.setDefaultAction(self.a_options)
        options.setIconSize(QSize(18, 18))
        options.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        options.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay.addWidget(options)
        return side

    def _build_main_area(self):
        """Sağ taraf: sayfa başlığı ve işlem düğmeleri, altında indirme listesi."""
        area = QWidget()
        lay = QVBoxLayout(area)
        lay.setContentsMargins(22, 18, 22, 0)
        lay.setSpacing(14)
        head = QHBoxLayout()
        head.setSpacing(8)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.page_title = QLabel()
        self.page_title.setObjectName("pageTitle")
        self.page_sub = QLabel()
        self.page_sub.setObjectName("pageSub")
        for w in (self.page_title, self.page_sub):
            w.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)  # dar pencerede düğmeleri itmesin
            titles.addWidget(w)
        head.addLayout(titles, 1)
        for a in (self.a_resume, self.a_stop, self.a_stop_all, self.a_delete):
            b = QToolButton()
            b.setObjectName("headButton")
            b.setDefaultAction(a)
            b.setIconSize(QSize(16, 16))
            b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            head.addWidget(b)
        self._more_btn = QToolButton()
        self._more_btn.setObjectName("headMenu")
        self._more_btn.setText(_t("Diğer"))
        self._more_btn.setIcon(theme.icon("chevron", "muted"))
        self._more_btn.setIconSize(QSize(12, 12))
        self._more_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._more_btn.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self._more_btn)
        for a in (self.a_delete_done, None, self.a_qstart, self.a_qstop, self.a_sched, None, self.a_group):
            menu.addSeparator() if a is None else menu.addAction(a)
        self._more_btn.setMenu(menu)
        head.addWidget(self._more_btn)
        lay.addLayout(head)
        frame = QFrame()
        frame.setObjectName("listFrame")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(1, 6, 1, 0)  # başlık satırı yuvarlak köşelerin altında kalsın
        fl.addWidget(self.table)
        lay.addWidget(frame, 1)
        return area

    def _update_page_head(self):
        cur = self.tree.currentItem()
        title = cur.text(0) if cur else ""
        active = sum(1 for i in self._visible if self.mgr.items[i].status in ("downloading", "connecting", "converting"))
        sub = _t("{0} indirme, {1} tanesi etkin").format(len(self._visible), active)
        if self.page_title.text() != title:
            self.page_title.setText(title)
        if self.page_sub.text() != sub:
            self.page_sub.setText(sub)

    def _build_language_menu(self, mb):
        """Menü çubuğunda sabit 'Language' menüsü: adı her dilde aynı, böylece dili bilmeyen de bulur."""
        m = mb.addMenu("&Language")
        m.setObjectName("language")
        group = QActionGroup(m)
        current = self.mgr.settings.get("language", "auto")
        if current not in i18n.LANGUAGES:
            current = "auto"
        for code, name in [("auto", _t("Sistem dili (otomatik)"))] + list(i18n.LANGUAGES.items()):
            a = m.addAction(name)
            a.setCheckable(True)
            a.setChecked(code == current)
            a.setData(code)
            group.addAction(a)
            a.triggered.connect(lambda _=False, c=code: self.set_language(c))
            if code == "auto":
                m.addSeparator()

    def _tray_menu(self):
        menu = QMenu()
        menu.addAction(_t("Göster"), self.show_normal)
        menu.addAction(self.a_add)
        menu.addAction(self.a_stop_all)
        menu.addSeparator()
        # genel hız sınırını tek tıkla aç/kapat (sınır Seçenekler → Bağlantı'da ayarlanır)
        self.a_limit = menu.addAction("")
        self.a_limit.setCheckable(True)
        self.a_limit.toggled.connect(self._toggle_speed_limit)
        menu.aboutToShow.connect(self._update_limit_action)
        self._update_limit_action()
        menu.addSeparator()
        menu.addAction(self.a_quit)
        return menu

    def _build_tray(self):
        self.tray = QSystemTrayIcon(self.icon, self)
        self.tray.setContextMenu(self._tray_menu())
        self.tray.activated.connect(
            lambda r: self.show_normal() if r == QSystemTrayIcon.DoubleClick else None)
        self.tray.show()

    def show_normal(self):
        bring_to_front(self)

    # ---------------------------------------------------------- liste
    def _filter_changed(self, cur, _prev):
        self._filter = cur.data(0, Qt.UserRole) if cur else "all"
        self.refresh(force=True)

    def _match(self, it):
        f = self._filter
        if f == "all":
            return True
        if f.startswith("cat:"):
            return it.category == f[4:]
        if f == "unfinished":
            return it.status != "completed" and it.status != "seeding"
        if f == "finished":
            return it.status in ("completed", "seeding")
        if f == "queue":
            return it.in_queue
        if f.startswith("queue:"):
            return it.in_queue and self.mgr.queue_of(it) == f[6:]
        return True

    def selected_ids(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        return [self._rows[r] for r in rows if r < len(self._rows) and isinstance(self._rows[r], str)]

    # ---------------------------------------------------------- toplu seçim
    SELECT_PRESETS = ((_t("Bitmemişleri seç"), lambda it: it.status not in ("completed", "seeding")),
                      (_t("Bitenleri seç"), lambda it: it.status in ("completed", "seeding")),
                      (_t("Durdurulanları seç"), lambda it: it.status in ("stopped", "queued")),
                      (_t("Hatalıları seç"), lambda it: it.status == "error"))

    def _add_select_menu(self, m):
        m.addAction(self.a_select_all)
        m.addAction(self.a_select_none)
        m.addSeparator()
        for text, pred in self.SELECT_PRESETS:
            m.addAction(text, lambda p=pred: self.select_where(p))

    def select_all(self):
        self.table.selectAll()

    def select_where(self, pred):
        """Listede görünenlerden koşula uyanları seç (önceki seçim yerine)."""
        self._select_rows([r for r, iid in enumerate(self._rows) if isinstance(iid, str) and pred(self.mgr.items[iid])])

    def _select_rows(self, rows):
        # selectRow() her çağrıda önceki seçimi siler (çoklu seçim kaybolurdu): seçim tek seferde kurulur
        from PySide6.QtCore import QItemSelection, QItemSelectionModel
        sel = QItemSelection()
        last = self.table.columnCount() - 1
        for r in rows:
            sel.select(self.table.model().index(r, 0), self.table.model().index(r, last))
        self.table.blockSignals(True)
        self.table.selectionModel().select(sel, QItemSelectionModel.ClearAndSelect)
        self.table.blockSignals(False)
        self._selection_changed()

    def _selection_changed(self):
        sel = {i.row() for i in self.table.selectedIndexes()}
        for r in range(self.table.rowCount()):
            cell = self.table.item(r, SEL)
            state = Qt.Checked if r in sel else Qt.Unchecked
            if cell and not cell.data(GROUP_ROLE) and cell.checkState() != state:
                cell.setCheckState(state)
        n, total = len(sel), len(self._visible)
        head = self.table.horizontalHeaderItem(SEL)
        head.setText("☑" if total and n == total else "☐")
        if n > 1:
            size = sum(self.mgr.items[i].size or 0 for i in self.selected_ids())
            self.sel_lbl.setText(_t("{0} indirme seçili ({1})  ").format(n, fmt_size(size)))
        else:
            self.sel_lbl.setText("")

    def refresh(self, force=False):
        self._update_nav_counts()
        ids = self._sorted_ids([i for i in self.mgr.order if self._match(self.mgr.items[i])])
        rows = self._layout_rows(ids)
        self._visible = ids
        if force or rows != self._rows:
            sel = set(self.selected_ids())
            self._rebuild_rows(rows)
            self._select_rows([r for r, iid in enumerate(rows) if iid in sel])
        for r, iid in enumerate(self._rows):
            if isinstance(iid, str):
                self._update_row(r, self.mgr.items[iid])
        self._update_page_head()

    def _layout_rows(self, ids):
        """Tablo satırları: gruplama açıksa her grubun başında (başlık, sayı) satırı; boş grup gösterilmez."""
        if not self.mgr.settings.get("group_list", True):
            return list(ids)
        groups = (("downloading connecting converting", _t("İndiriliyor")), ("queued stopped error", _t("Bekleyen")),
                  ("completed seeding", _t("Tamamlanan")))
        rows = []
        for statuses, title in groups:
            members = [i for i in ids if self.mgr.items[i].status in statuses.split()]
            if members:
                rows.append((title, len(members)))
                rows.extend(members)
        known = {r for r in rows if isinstance(r, str)}
        rows.extend(i for i in ids if i not in known)  # bilinmeyen durum listeden kaybolmasın
        return rows

    def _rebuild_rows(self, rows):
        from PySide6.QtCore import QItemSelectionModel
        t = self.table
        scroll = t.verticalScrollBar().value()
        cur = t.currentIndex()
        cur_id = self._rows[cur.row()] if 0 <= cur.row() < len(self._rows) else None
        pressed = t._action_pressed
        if pressed and rows[pressed[0]:pressed[0] + 1] != self._rows[pressed[0]:pressed[0] + 1]:
            t._action_pressed = None  # basılan düğmenin satırına başka indirme geldi: bırakınca ona uygulanmasın
        t.clearSpans()
        t.clearContents()
        t.setRowCount(len(rows))
        self._rows = rows
        for r, iid in enumerate(rows):
            if not isinstance(iid, str):  # grup satırı: seçilemez, bütün satıra yayılır
                cell = QTableWidgetItem()
                cell.setFlags(Qt.NoItemFlags)
                cell.setData(GROUP_ROLE, iid)
                t.setItem(r, SEL, cell)
                t.setSpan(r, SEL, 1, t.columnCount())
                t.setRowHeight(r, GROUP_HEIGHT)
                continue
            t.setRowHeight(r, ROW_HEIGHT)
            for c in range(t.columnCount()):
                cell = QTableWidgetItem()
                if c == SEL:  # kutu seçimi gösterir; tıklama DownloadTable'da seçimi değiştirir
                    cell.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    cell.setCheckState(Qt.Unchecked)
                elif c in (SIZE, ETA, SPEED):
                    cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                t.setItem(r, c, cell)
            f = t.item(r, SPEED).font()
            f.setBold(True)
            t.item(r, SPEED).setFont(f)
        if isinstance(cur_id, str) and cur_id in rows:  # klavye konumu ve Shift ile seçimin başlangıcı kaybolmasın
            t.setAutoScroll(False)  # liste geçerli hücreye kaymasın
            t.selectionModel().setCurrentIndex(t.model().index(rows.index(cur_id), cur.column()), QItemSelectionModel.NoUpdate)
            t.setAutoScroll(True)
        t.verticalScrollBar().setValue(scroll)

    SORT_KEYS = {
        NAME: lambda it: it.filename.casefold(),
        SIZE: lambda it: it.size or 0,
        STATUS: lambda it: (it.status, (it.done_bytes / it.size) if it.size else 0),
        ETA: lambda it: (it.size - it.done_bytes) / it.speed if it.size and it.speed > 1 else float("inf"),
        SPEED: lambda it: it.speed or 0,
        6: lambda it: it.last_try or 0,
        7: lambda it: (it.description or "").casefold(),
        8: lambda it: it.added or 0,
        9: lambda it: it.extra.get("finished_at") or 0,
    }

    def _sort_state(self):
        s = self.mgr.settings.get("list_sort")
        return s if isinstance(s, list) and len(s) == 2 and type(s[0]) is int and s[0] in self.SORT_KEYS else None

    def _sorted_ids(self, ids):
        s = self._sort_state()
        if not s:
            return ids
        # hız ve kalan süre sürekli değişir: satırlar fare altından kaymasın diye en çok 3 sn'de bir sıralanır
        live, now = s[0] in (ETA, SPEED), time.monotonic()
        last = getattr(self, "_live_sort", None)
        if live and last and last[0] == tuple(s) and set(last[1]) == set(ids) and now - last[2] < 3:
            return list(last[1])
        key = self.SORT_KEYS[s[0]]
        out = sorted(ids, key=lambda i: key(self.mgr.items[i]), reverse=not s[1])
        self._live_sort = (tuple(s), out, now) if live else None
        return out

    def _update_sort_indicator(self):
        h = self.table.horizontalHeader()
        s = self._sort_state()
        h.setSortIndicatorShown(bool(s))
        if s:
            h.setSortIndicator(s[0], Qt.AscendingOrder if s[1] else Qt.DescendingOrder)

    def _header_clicked(self, c):
        """Kutu başlığı: tümünü seç/kaldır. Diğer başlıklar: artan, azalan, sonra eklenme sırası."""
        self._update_sort_indicator()  # Qt her tıkta göstergeyi tıklanan sütuna taşır
        if c == SEL:
            if len(self.selected_ids()) == len(self._visible):
                self.table.clearSelection()
            else:
                self.select_all()
            return
        if c not in self.SORT_KEYS:
            return
        s = self._sort_state()
        self.mgr.settings["list_sort"] = [c, True] if not s or s[0] != c else [c, False] if s[1] else None
        self._live_sort = None
        self.mgr.save()
        self._update_sort_indicator()
        self.refresh()

    def _set_grouping(self, on):
        self.mgr.settings["group_list"] = bool(on)
        self.mgr.save()
        self.refresh(force=True)

    def _row_action(self, row, name):
        """Satırdaki düğme: yalnızca o satırı etkiler; "Diğer" o satırın sağ tık menüsünü açar."""
        iid = self._rows[row] if row < len(self._rows) else None
        it = self.mgr.items.get(iid) if isinstance(iid, str) else None
        if it is None:
            return
        if name in ("play", "retry"):
            self.mgr.start(iid)
            if name == "retry":
                self.show_progress(iid)
        elif name == "pause":
            self.mgr.stop(iid)
        elif name == "folder":
            open_folder(self._item_path(it))
        elif name == "more":
            if iid not in self.selected_ids():
                self._select_rows([row])
            cell = self.table.visualRect(self.table.model().index(row, ACTIONS))
            self._context_menu(cell.bottomRight() - QPoint(cell.width() // 4, cell.height() // 4))
        self.refresh()

    def _smoothed(self, it):
        """İnen indirmenin akıcı gösterilen (indirilen, hız) değerleri; diğerlerinde gerçek değerler."""
        if it.status not in ("downloading", "connecting"):
            self._smooth.pop(it.id, None)
            return it.done_bytes, it.speed
        sm = self._smooth.get(it.id)
        if sm is None:
            sm = self._smooth[it.id] = SmoothProgress()
        return sm.step(it.done_bytes, it.speed, it.size, True)

    def _animate_rows(self):
        """Saniyede ~20 kez: yalnızca inmekte olan satırların yüzdesi, ilerleme çizgisi ve hızı (akıcı)."""
        if not self.isVisible() or self.isMinimized():
            return
        for r, iid in enumerate(self._rows):
            it = self.mgr.items.get(iid) if isinstance(iid, str) else None
            if it and it.status in ("downloading", "connecting") and r < self.table.rowCount():
                self._update_row(r, it)

    def _update_row(self, r, it):
        done, speed = self._smoothed(it)
        if it.status in ("downloading", "connecting") and it.size:
            st = fmt_pct(done / it.size * 100, 2)
            if it.status == "connecting" and it.error:
                st = it.error
        elif it.status == "error":
            st = _t("Hata: {0}").format(it.error or "")
        else:
            st = STATUS_TEXT.get(it.status, it.status)
            if it.status in ("stopped", "queued") and it.size and it.done_bytes:
                st += f" ({fmt_pct(it.done_bytes / it.size * 100, 1)})"
        if it.kind == "torrent" and it.status in ("downloading", "seeding"):
            st += _t("  ·  {0} eş").format(it.peers)
        frac = (done / it.size if it.size and it.status in ("downloading", "connecting", "stopped", "queued") else None)
        if it.status == "queued" and not done:
            frac = None  # henüz başlamadı: boş çubuk yerine simge ve yazı
        tone = {"completed": "ok", "seeding": "ok", "error": "bad", "downloading": "accent",
                "converting": "accent"}.get(
            it.status, "muted" if it.status in ("stopped", "queued") else "text")
        sc = self.table.item(r, STATUS)
        if sc.data(PROGRESS_ROLE) != frac or sc.data(TONE_ROLE) != tone:
            sc.setData(PROGRESS_ROLE, frac)
            sc.setData(TONE_ROLE, tone)
        segs = self._bar_segments(it) if frac is not None else None
        if sc.data(SEG_ROLE) != segs:
            sc.setData(SEG_ROLE, segs)
        detail = f"{fmt_size(done)} / {fmt_size(it.size)}" if frac is not None else ""
        if sc.data(DETAIL_ROLE) != detail:
            sc.setData(DETAIL_ROLE, detail)
        stamp = lambda t: datetime.fromtimestamp(t).strftime("%d.%m.%Y %H:%M") if t else ""  # noqa: E731
        eta = (it.size - done) / speed if it.size and speed > 1 and it.status == "downloading" else None
        vals = (it.filename, fmt_size(it.size) if it.size else "", st, fmt_time(eta),
                fmt_speed(speed), stamp(it.last_try), it.description, stamp(it.added),
                stamp(it.extra.get("finished_at")))
        for c, v in enumerate(vals, start=NAME):
            cell = self.table.item(r, c)
            if cell.text() != v:
                cell.setText(v)
        cell0 = self.table.item(r, NAME)
        state = f"{it.kind}{it.status}{it.category}"
        if cell0.data(Qt.UserRole) != state:
            cell0.setData(Qt.UserRole, state)
            cell0.setIcon(theme.icon("magnet" if it.kind == "torrent" else CAT_ICONS.get(it.category, "general")))
            cell0.setData(ACTIVE_ROLE, it.status in ("downloading", "connecting", "converting"))
            sc.setIcon(self._status_icon(it))
            self.table.item(r, ACTIONS).setData(ACTIONS_ROLE, self._row_actions(it))
        sub = self._row_subtitle(it, stamp)
        if cell0.data(SUB_ROLE) != sub:
            cell0.setData(SUB_ROLE, sub)

    @staticmethod
    def _bar_segments(it):
        """Parçalı çubuk verisi; bilinmiyorsa, parça çok fazlaysa ya da kayıt bozuksa None (tek parça çizilir)."""
        task = it.task
        if task is not None and hasattr(task, "bar_data"):
            total, segs = task.bar_data()
        elif it.kind == "http":
            total, segs = it.size, it.segments
        else:
            return None
        try:
            if not total or not segs or len(segs) > 32:
                return None
            out = sorted((int(a), int(b), int(pos)) for a, b, pos in segs)
            return (total, out) if all(0 <= a <= b < total for a, b, _ in out) else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _row_actions(it):
        if it.status in ("downloading", "connecting", "seeding"):
            return ("pause", "more")
        if it.status == "completed":
            return ("folder", "more")
        if it.status == "error":
            return ("retry", "more")
        if it.status == "converting":
            return ("more",)
        return ("play", "more")

    @staticmethod
    def _row_subtitle(it, stamp):
        cat = CATEGORIES.get(it.category)
        parts = [cat[0]] if cat else []
        if it.status == "downloading" and it.task is not None and hasattr(it.task, "connections_snapshot"):
            n = len(it.task.connections_snapshot())
            if n:
                parts.append(_t("{0} bağlantı").format(n))
        elif it.status == "stopped" and it.done_bytes and it.resumable:
            parts.append(_t("kaldığı yerden sürer"))
        elif it.status == "completed" and it.extra.get("finished_at"):
            parts.append(stamp(it.extra["finished_at"]))
        return " · ".join(parts)

    def _status_icon(self, it):
        return theme.status_icon(it.status)

    def _update_nav_counts(self):
        """Kenar çubuğundaki her kategorinin yanında indirme sayısı."""
        items = list(self.mgr.items.values())
        saved = self._filter
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for node in [top] + [top.child(j) for j in range(top.childCount())]:
                self._filter = node.data(0, Qt.UserRole)
                if self._filter is None:  # bölüm başlığı
                    continue
                n = sum(1 for it in items if self._match(it))
                if node.data(0, COUNT_ROLE) != n:
                    node.setData(0, COUNT_ROLE, n)
        self._filter = saved

    # ---------------------------------------------------------- periyodik
    def _tick(self):
        self.mgr.tick()
        while self.mgr.events:
            kind, it = self.mgr.events.pop(0)
            if kind == "completed":
                self.tray.showMessage(APP_NAME, _t("İndirme tamamlandı:\n{0}").format(it.filename), self.icon, 4000)
                if it.kind == "http" and it.path.lower().endswith(".torrent") and self.mgr.torrents:
                    self.add_source(it.path)  # inen .torrent → torrent olarak indirmeyi öner
                    continue
                oc = getattr(it, "on_complete", None) or {}
                if oc.get("show_dialog", self.mgr.settings["show_complete_dialog"]):
                    self._complete_dialog(it)
                action = next((a for a in ("shutdown", "sleep", "exit") if oc.get(a)), None)
                if action:
                    bring_to_front(PowerActionDialog(self, action, oc.get("force", False),
                                                     reason=_t("İndirme tamamlandı: {0}").format(it.filename)))
            elif kind == "error":
                self.tray.showMessage(APP_NAME, _t("Hata: {0}\n{1}").format(it.filename, it.error),
                                      QSystemTrayIcon.Warning, 5000)
                self._error_dialog(it)
            elif kind == "queue_done":
                self.tray.showMessage(APP_NAME, _t("Kuyruktaki tüm indirmeler işlendi."), self.icon, 4000)
                action = self.mgr.settings.get("queue_done_action") or "none"
                if action in POWER_ACTIONS:
                    bring_to_front(PowerActionDialog(self, action, self.mgr.settings.get("queue_done_force", False),
                                                     reason=_t("Kuyruktaki tüm indirmeler tamamlandı.")))
            elif kind == "info":
                self.tray.showMessage(APP_NAME, it, self.icon, 3000)
        while not server.requests.empty():
            self._handle_external(server.requests.get())
        self.refresh()
        sp = self.mgr.total_speed()
        active = sum(1 for i in self.mgr.items.values() if i.status in ("downloading", "connecting"))
        q = _t("  ·  Kuyruk çalışıyor") if any(self.mgr.is_queue_running(x["id"]) for x in self.mgr.queues()) else ""
        self.speed_lbl.setText(_t("Etkin: {0}   ·   Toplam hız: {1}{2}").format(active, fmt_speed(sp) or '0 B/s', q))
        self.tray.setToolTip(f"{APP_NAME}\n{fmt_speed(sp) or _t("Boşta")}")

    def _complete_dialog(self, it):
        path = it.path if it.kind != "torrent" else os.path.join(it.path, it.name)
        box = QMessageBox(self)
        box.setWindowTitle(_t("İndirme tamamlandı"))
        box.setIcon(QMessageBox.Information)
        box.setText(_t("<b>{0}</b><br>{1}<br>{2}").format(it.filename, fmt_size(it.size), path))
        b_open = box.addButton(_t("Aç"), QMessageBox.AcceptRole)
        b_dir = box.addButton(_t("Klasörü Aç"), QMessageBox.ActionRole)
        box.addButton(_t("Kapat"), QMessageBox.RejectRole)
        box.setAttribute(Qt.WA_DeleteOnClose)
        box.buttonClicked.connect(lambda b: open_path(path) if b is b_open
                                  else open_folder(path) if b is b_dir else None)
        bring_to_front(box)

    def _extension_outdated(self, info):
        """Elle kurulmuş tarayıcı eklentisi eski: tarayıcı onu TurboDM güncellenince kendiliğinden yenilemez."""
        have, latest = str(info.get("version") or ""), str(info.get("latest") or "")
        box = QMessageBox(self)
        box.setWindowTitle(_t("Tarayıcı eklentisi güncel değil"))
        box.setIcon(QMessageBox.Information)
        version = (_t("Bu tarayıcıdaki TurboDM eklentisi eski bir sürüm ({0}); TurboDM ile gelen sürüm {1}.").format(have, latest)
                   if have else _t("Bu tarayıcıdaki TurboDM eklentisi eski bir sürüm; TurboDM ile gelen sürüm {0}.").format(latest))
        box.setText(version + "<br><br>" + _t(
            "Elle kurulan eklentiyi tarayıcı kendiliğinden yenilemez. Yeni özellikler ve düzeltmeler için:<br>"
            "1. Tarayıcının eklentiler sayfasını açın (<b>chrome://extensions</b>, <b>brave://extensions</b>, "
            "<b>edge://extensions</b> ya da <b>opera://extensions</b>)<br>"
            "2. TurboDM Entegrasyonu kartındaki yenile (↻) düğmesine basın<br>"
            "3. Açık sayfaları yenileyin (F5)"))
        box.addButton(_t("Tamam"), QMessageBox.AcceptRole)
        box.setAttribute(Qt.WA_DeleteOnClose)
        bring_to_front(box)

    def perform_power_action(self, action, force=False):
        """Bitince yapılacaklar: önce indirme listesi kaydedilir, sonra işlem yapılır."""
        self.mgr.save()
        if action == "exit":
            self.quit_app()
        elif action == "shutdown":
            args = ["shutdown", "/s", "/t", "5"] + (["/f"] if force else [])
            subprocess.Popen(args, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.quit_app()
        elif action == "sleep":
            import ctypes
            power.keep_awake(False)
            ctypes.windll.powrprof.SetSuspendState(False, False, False)

    def _error_dialog(self, it, waited=False):
        """İndirme hatası: IDM gibi önde bir uyarı, tek tıkla yeniden deneme."""
        if not waited and self._handoff_failed(it) and any(
                h["iid"] == it.id for h in getattr(self, "_handoffs", {}).values()):
            # tarayıcıdan devralınmıştı: eklenti indirmeyi birkaç saniye içinde tarayıcıya geri verecek;
            # vermezse (eklenti kapalı/eski) uyarı yine gösterilir
            iid = it.id
            QTimer.singleShot(8000, lambda: self._error_dialog(self.mgr.items[iid], True)
                              if self._handoff_failed(self.mgr.items.get(iid)) else None)
            return
        box = QMessageBox(self)
        self._error_boxes[it.id] = box
        box.destroyed.connect(lambda _=None, i=it.id: self._error_boxes.pop(i, None))
        box.setWindowTitle(_t("İndirme hatası"))
        box.setIcon(QMessageBox.Warning)
        box.setText(_t("<b>{0}</b><br><br>{1}").format(it.filename, it.error or _t('Bilinmeyen hata')))
        b_retry = box.addButton(_t("Tekrar Dene"), QMessageBox.AcceptRole)
        box.addButton(_t("Kapat"), QMessageBox.RejectRole)
        box.setAttribute(Qt.WA_DeleteOnClose)
        iid = it.id
        box.buttonClicked.connect(lambda b: (self.mgr.start(iid), self.show_progress(iid)) if b is b_retry else None)
        bring_to_front(box)

    # ---------------------------------------------------------- ekleme
    def add_url_prompt(self):
        clip = QApplication.clipboard().text().strip()
        default = clip if re.match(r"^(https?|ftp)://|^magnet:", clip, re.I) else "https://"
        url, ok = QInputDialog.getText(self, _t("Yeni indirme"), _t("İndirilecek adres (URL veya magnet):"), text=default)
        if ok and url.strip():
            self.add_source(url.strip())

    def add_torrent_prompt(self):
        p, _ = QFileDialog.getOpenFileName(self, _t("Torrent dosyası seç"), "", _t("Torrent (*.torrent)"))
        if p:
            self.add_source(p)

    def add_magnet_prompt(self):
        url, ok = QInputDialog.getText(self, _t("Magnet ekle"), _t("Magnet bağlantısı:"))
        if ok and url.strip():
            self.add_source(url.strip())

    def add_source(self, src, headers=None, suggested=None, cookies=None, handoff=None):
        if is_magnet(src) or (src.lower().endswith(".torrent") and os.path.isfile(src)):
            if not self.mgr.torrents:
                QMessageBox.warning(self, APP_NAME, _t("Torrent desteği yok: {0}").format(self.mgr.torrent_error))
                return
            d = TorrentAddDialog(self, src)
        elif re.match(r"^(https?|ftp)://", src, re.I):
            d = FileInfoDialog(self, src, headers, suggested, cookies)
            if handoff:
                d.handoff = handoff
                d.finished.connect(lambda _r, t=handoff: self._handoffs.get(t, {}).update(closed=True))
        else:
            QMessageBox.warning(self, APP_NAME, _t("Geçersiz adres. http(s)://, ftp:// ya da magnet: bağlantısı girin."))
            return
        bring_to_front(d)

    def _handle_external(self, req):
        if req.get("show"):
            self.show_normal()
            return
        if req.get("quit"):
            self.quit_app()
            return
        if req.get("notice"):  # tarayıcının indirmesi devralınamadı: neden bildirilir, indirme tarayıcıda sürer
            self.tray.showMessage(APP_NAME, req["notice"], self.icon, 8000)
            self.statusBar().showMessage(req["notice"], 15000)
            return
        if req.get("handoff_returned"):
            self._handoff_returned(req["handoff_returned"])
            return
        if isinstance(req.get("ext_outdated"), dict):
            self._extension_outdated(req["ext_outdated"])
            return
        tf = req.get("torrent_file")
        if isinstance(tf, str) and tf.lower().endswith(".torrent") and os.path.isfile(tf):
            # Tarayıcının indirdiği .torrent (site yalnızca tarayıcıya veriyorsa): dosya seçimiyle aç
            self.add_source(tf)
            return
        url = req.get("url", "")
        if isinstance(req.get("cookies"), list):  # eklentiden sayfa videosu: tek videoya indirgenir
            url = ytdlp.canonical_url(url)
        headers = self._request_headers(req)
        name = os.path.basename(req.get("filename") or "") or None
        cookies = req.get("cookies") if isinstance(req.get("cookies"), list) else None
        if cookies:  # yapılandırılmış çerezler (YouTube): yt-dlp'ye çerez dosyasıyla verilir
            headers.pop("Cookie", None)
        if isinstance(req.get("choice"), dict) and req["choice"].get("format"):
            # Kalite tarayıcıdaki menüden seçildi (IDM gibi): kayıt yeri penceresi, kalite seçili gelir
            self._video_from_menu(url, req["choice"], req.get("title") or "", headers, cookies)
            return
        token = req.get("handoff")
        if isinstance(token, str) and 0 < len(token) <= 64:
            # eklenti tarayıcıdaki indirmeyi iptal etti: indirme hiç başlayamazsa tarayıcıya geri verebilsin diye izlenir
            self._handoffs[token] = {"iid": None, "closed": False, "t": time.time()}
            for k in [k for k, h in self._handoffs.items() if time.time() - h["t"] > 3 * 3600]:
                del self._handoffs[k]
        else:
            token = None
        self.add_source(url, headers, name, cookies, handoff=token)

    @staticmethod
    def _request_headers(req):
        """Eklentiden gelen istek için başlıklar: tarayıcının çerezi, yönlendiren sayfa ve tarayıcı kimliği."""
        headers = {}
        if req.get("cookie"):
            headers["Cookie"] = req["cookie"]
        if req.get("referrer"):
            headers["Referer"] = req["referrer"]
        if req.get("userAgent"):
            headers["User-Agent"] = req["userAgent"]
        if isinstance(req.get("origin"), str) and re.match(r"^https?://[^/]+$", req["origin"]):
            headers["Origin"] = req["origin"]  # gömülü oynatıcının kökeni (video sunucusu denetleyebilir)
        return headers

    def _check_handler(self, data):
        """Köprü iş parçacığında: tarayıcının başlattığı indirmeyi devralmadan önce TurboDM dosyaya ulaşabiliyor mu?
        None → evet (eklenti tarayıcıdaki indirmeyi iptal eder); metin → hayır, nedeni (indirme tarayıcıda sürer).
        Ör. Cloudflare korumalı sitelerde tarayıcı doğrulamayı geçmiştir ama koruma TurboDM'i ayırt edip engelleyebilir."""
        url = data.get("url") or ""
        if not re.match(r"^(https?|ftp)://", url, re.I):
            return None
        host = urllib.parse.urlparse(url).hostname or url
        try:
            info = probe(url, self._request_headers(data), timeout=12)
        except Exception as e:  # noqa: BLE001
            if engine.is_bot_challenge(e):
                return _t("{0} bot koruması (Cloudflare) kullanıyor ve TurboDM'in dosyaya erişmesine izin vermedi. Dosya tarayıcıda iniyor.").format(host)
            return _t("TurboDM bu dosyaya erişemedi ({0}). Dosya tarayıcıda iniyor.").format(engine._err_text(e))
        mime = (data.get("mime") or "").lower()
        if info.get("content_type") == "text/html" and mime and "html" not in mime:
            return _t("{0} TurboDM'e dosya yerine bir web sayfası gönderdi (giriş ya da doğrulama sayfası olabilir). Dosya tarayıcıda iniyor.").format(host)
        return None

    # Devralınan indirme hiç veri alamadan bu hatalardan biriyle düşerse tarayıcıya geri verilir: ön denetim geçse de
    # bazı sunucular bağlantıyı yalnızca bir kez ya da tek bağlantıyla verir (ör. süreli/imzalı depolama bağlantıları).
    HANDOFF_FAIL = re.compile(r"\bHTTP (401|403|404|410)\b")

    def _handoff_failed(self, it):
        return (it is not None and it.status == "error" and not it.done_bytes
                and bool(self.HANDOFF_FAIL.search(it.error or "")))

    def _handoff_handler(self, data):
        """Köprü iş parçacığında (/handoff): eklenti, iptal ettiği tarayıcı indirmesinin TurboDM'de başlayıp
        başlamadığını sorar. pending: pencere açık ya da indirme henüz veri almadı · ok: indiriliyor/bitti ·
        failed: hiç başlayamadı (eklenti tarayıcıda yeniden başlatır) · gone: kullanıcı vazgeçti ya da silindi.
        returned: eklenti indirmeyi tarayıcıda başlattı; TurboDM'deki başarısız kayıt kaldırılır."""
        token = data.get("id")
        h = self._handoffs.get(token) if isinstance(token, str) else None
        if data.get("returned"):
            server.leave_to_browser(data.get("url"))  # yeniden başlatılan indirmeyi hiçbir eklenti kopyası yakalamasın
            if h is not None:
                server.requests.put({"handoff_returned": token})
            return {"state": "returned"}
        if h is None and isinstance(token, str):
            # TurboDM devirden sonra yeniden başladı: indirme kaydedildiyse kayıttan bulunur
            it = next((i for i in list(self.mgr.items.values()) if i.extra.get("handoff") == token), None)
            if it is not None:
                h = self._handoffs.setdefault(token, {"iid": it.id, "closed": True, "t": time.time()})
        if h is None:
            t = data.get("t")
            if not isinstance(t, (int, float)):
                return {"state": "gone"}  # devir zamanını göndermeyen eski eklenti
            if t / 1000 < self._started:
                # devir TurboDM açılmadan önceydi ve hiç kaydedilmedi (TurboDM o sırada kapandı ya da çöktü):
                # eklenti indirmeyi tarayıcıda yeniden başlatır
                return {"state": "failed", "error": _t("TurboDM indirmeyi devralırken kapandı")}
            return {"state": "pending"}  # istek az önce geldi, henüz işlenmedi
        if h["iid"] is None:
            return {"state": "gone" if h["closed"] else "pending"}
        it = self.mgr.items.get(h["iid"])
        if it is None:
            return {"state": "gone"}
        if it.done_bytes or it.status == "completed":
            return {"state": "ok"}
        if self._handoff_failed(it):
            return {"state": "failed", "error": it.error}
        return {"state": "pending"}

    def _handoff_returned(self, token):
        h = self._handoffs.pop(token, None)
        it = self.mgr.items.get(h["iid"]) if h else None
        if not self._handoff_failed(it):
            return
        msg = _t("TurboDM bu dosyayı indiremedi ({0}). İndirme tarayıcıda başlatıldı.").format(it.error)
        for d in (self._error_boxes.pop(it.id, None), self.progress_dialogs.get(it.id)):
            try:
                if d is not None:
                    d.close()
            except RuntimeError:  # pencere zaten kapanmış
                pass
        self.mgr.remove(it.id, False)  # hiç veri inmedi: yalnızca TurboDM'in yarım dosya kayıtları silinir
        self.refresh(force=True)
        self.tray.showMessage(APP_NAME, msg, self.icon, 8000)
        self.statusBar().showMessage(msg, 15000)

    # ---------------------------------------------------------- tarayıcıdaki kalite menüsü
    FORMAT_CACHE_SECONDS = 20 * 60

    def _formats_handler(self, data):
        """Köprü iş parçacığında çalışır (/formats): eklentinin sayfada göstereceği kalite listesi.
        Sonuç (akış adresleriyle) önbelleğe alınır; kalite seçilince YouTube'a ikinci istek gitmez."""
        url = data.get("url") or ""
        if not re.match(r"^https?://", url, re.I):
            raise ValueError(_t("Geçersiz adres"))
        url = ytdlp.canonical_url(url)
        if not ytdlp.available():
            raise RuntimeError(_t("yt-dlp bulunamadı"))
        hit = self._fmt_cache.get(url)
        if hit and time.time() - hit[0] < self.FORMAT_CACHE_SECONDS:
            info = hit[1]
        else:
            cookies = data.get("cookies") if isinstance(data.get("cookies"), list) else None
            info = ytdlp.inspect(url, self.mgr.ffmpeg(), cookies)
            self._fmt_cache[url] = (time.time(), info)
        return {"title": info["title"], "duration": info.get("duration"),
                "choices": [{k: v for k, v in c.items() if k != "streams"} for c in info["choices"]]}

    def _video_from_menu(self, url, choice, title, headers, cookies):
        """Tarayıcı menüsünde seçilen kalite: 'İndirme Dosyası Bilgisi' penceresi kalite ve uzantı seçili açılır;
        kayıt yeri / Sonra İndir / Başlat kullanıcıda. Önbellekteki bilgi kullanılır (YouTube'a yeni istek yok)."""
        hit = self._fmt_cache.get(url)
        info = hit[1] if hit and time.time() - hit[0] < self.FORMAT_CACHE_SECONDS else None
        if info is None:  # önbellek yoksa pencere kaliteleri kendisi sorgular; seçim yine uygulanır
            d = FileInfoDialog(self, url, headers, None, cookies)
            d._preselect = choice.get("format")
        else:
            d = FileInfoDialog(self, url, headers, None, cookies, video_info=info, preselect=choice.get("format"))
        bring_to_front(d)

    # ---------------------------------------------------------- güncellemeler
    def check_updates(self, prefetched=None):
        d = UpdateDialog(self, prefetched)
        bring_to_front(d)

    def _auto_update_check(self):
        """Açılıştan kısa süre sonra, günde en fazla bir kez, sessizce denetle."""
        s = self.mgr.settings
        url = updater.manifest_url(s.get("update_repo") or None)
        if not url or not s.get("auto_update_check", True) or time.time() - s.get("last_update_check", 0) < 86400:
            return
        s["last_update_check"] = time.time()
        self._upd_bridge = Bridge()
        self._upd_bridge.done.connect(self._on_auto_update)

        def work():
            try:
                self._upd_bridge.done.emit(updater.check(url), None)
            except Exception as e:  # noqa: BLE001
                self._upd_bridge.done.emit(None, str(e))
        threading.Thread(target=work, daemon=True).start()

    def _on_auto_update(self, info, err):
        if info and info["available"]:
            self.tray.showMessage(APP_NAME, _t("Yeni sürüm var: {0}").format(info['latest']), self.icon, 5000)
            self.check_updates(prefetched=info)

    def _on_clipboard(self):
        if not self.mgr.settings["clipboard_monitor"]:
            return
        text = QApplication.clipboard().text().strip()
        if not text or text == self._last_clip or "\n" in text:
            return
        self._last_clip = text
        if is_magnet(text) and self.mgr.torrents:
            self.add_source(text)
            return
        if re.match(r"^(https?|ftp)://\S+$", text, re.I):
            path = urllib.parse.urlparse(text).path
            ext = os.path.splitext(path)[1].lower().lstrip(".")
            if ext in CATCH_EXTS or ext in ("torrent", "m3u8"):
                if any(i.url == text for i in self.mgr.items.values()):
                    return
                self.add_source(text)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls() or e.mimeData().hasText():
            e.acceptProposedAction()

    def dropEvent(self, e):
        md = e.mimeData()
        if md.hasUrls():
            for u in md.urls():
                self.add_source(u.toLocalFile() if u.isLocalFile() else u.toString())
        elif md.hasText():
            self.add_source(md.text().strip())

    # ---------------------------------------------------------- işlemler
    def show_progress(self, iid):
        d = self.progress_dialogs.get(iid)
        if d is not None:
            try:
                bring_to_front(d)
                return
            except RuntimeError:
                pass
        d = ProgressDialog(self, iid)
        d.destroyed.connect(lambda *_, d=d: self.progress_dialogs.get(iid) is d and self.progress_dialogs.pop(iid))
        self.progress_dialogs[iid] = d
        bring_to_front(d)

    def resume_selected(self):
        for iid in self.selected_ids():
            self.mgr.start(iid)

    def stop_selected(self):
        for iid in self.selected_ids():
            self.mgr.stop(iid)

    def delete_selected(self, with_file):
        ids = self.selected_ids()
        if not ids:
            return
        if not with_file:
            box = QMessageBox(QMessageBox.Question, APP_NAME,
                              _t("{0} indirme listeden silinsin mi?").format(len(ids)), parent=self)
            b_list = box.addButton(_t("Listeden sil"), QMessageBox.AcceptRole)
            b_file = box.addButton(_t("Dosyalarla birlikte sil"), QMessageBox.DestructiveRole)
            box.addButton(_t("İptal"), QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is b_file:
                with_file = True
            elif box.clickedButton() is not b_list:
                return
        for iid in ids:
            self.mgr.remove(iid, with_file)
        self.refresh(force=True)

    def delete_completed(self):
        done = [i for i in self.mgr.order if self.mgr.items[i].status == "completed"]
        if done and QMessageBox.question(self, APP_NAME, _t("{0} tamamlanmış indirme listeden kaldırılsın mı?\n(Dosyalar diskte kalır.)").format(len(done))) == QMessageBox.Yes:
            for iid in done:
                self.mgr.remove(iid, False)
            self.refresh(force=True)

    def open_options(self):
        OptionsDialog(self).exec()

    def _item_path(self, it):
        return it.path if it.kind != "torrent" else os.path.join(it.path, it.name)

    def _double_click(self, idx):
        iid = self._rows[idx.row()] if idx.row() < len(self._rows) else None
        if not isinstance(iid, str) or idx.column() == ACTIONS:
            return
        it = self.mgr.items[iid]
        if it.status == "completed":
            open_path(self._item_path(it))
        else:
            self.show_progress(it.id)

    def _context_menu(self, pos):
        ids = self.selected_ids()
        m = QMenu(self)
        if not ids:  # boş alana sağ tık: yalnızca toplu seçim
            self._add_select_menu(m)
            m.exec(self.table.viewport().mapToGlobal(pos))
            return
        it = self.mgr.items[ids[0]]
        many = len(ids) > 1
        if many:  # toplu işlem: hepsine uygulanan komutlar
            head = m.addAction(_t("{0} indirme seçili").format(len(ids)))
            head.setEnabled(False)
            m.addSeparator()
        else:
            m.addAction(_t("Aç"), lambda: open_path(self._item_path(it))).setEnabled(it.status == "completed")
            m.addAction(_t("Klasörü aç"), lambda: open_folder(self._item_path(it)))
            m.addAction(_t("İndirme durumu…"), lambda: self.show_progress(it.id))
            m.addSeparator()
        m.addAction(self.a_resume)
        m.addAction(self.a_stop)
        m.addSeparator()
        queues = self.mgr.queues()
        if len(queues) > 1:
            qm = m.addMenu(_t("Kuyruğa ekle"))
            for q in queues:
                qm.addAction(q["name"], lambda qid=q["id"]: [self.mgr.set_queue(i, True, qid) for i in ids])
        else:
            m.addAction(_t("Kuyruğa ekle"), lambda: [self.mgr.set_queue(i, True) for i in ids])
        m.addAction(_t("Kuyruktan çıkar"), lambda: [self.mgr.set_queue(i, False) for i in ids])
        m.addSeparator()
        m.addAction(_t("Adresleri kopyala") if many else _t("Adresi kopyala"), lambda: QApplication.clipboard().setText(
            "\n".join(self.mgr.items[i].url for i in ids if i in self.mgr.items)))
        if not many:
            if it.kind != "torrent":
                m.addAction(_t("İndirme adresini yenile…"), lambda: self._refresh_address(it))
                if it.status == "completed":
                    m.addAction(_t("Dosyayı doğrula (MD5 / SHA-256)…"),
                                lambda: bring_to_front(ChecksumDialog(self, self._item_path(it))))
            else:
                m.addAction(_t("Dosya seçimi…"), lambda: self.show_progress(it.id))
        m.addSeparator()
        m.addAction(_t("Sil ({0})…").format(len(ids)) if many else _t("Sil…"), lambda: self.delete_selected(False))
        self._add_select_menu(m.addMenu(_t("Toplu seçim")))
        m.exec(self.table.viewport().mapToGlobal(pos))

    def _refresh_address(self, it):
        """Süresi dolmuş linkler için (IDM'deki 'Refresh download address')."""
        url, ok = QInputDialog.getText(self, _t("Adresi yenile"), _t("Yeni indirme adresi:"), text=it.url)
        if ok and url.strip():
            self.mgr.stop(it.id)
            it.url = url.strip()
            self._last_clip = it.url
            self.mgr.save()

    # ---------------------------------------------------------- kapanış
    def closeEvent(self, e):
        if self._quitting:
            e.accept()
            return
        e.ignore()
        self.hide()
        # yalnızca ilk kez: programın kapanmadığını öğrensin, sonra her seferinde bildirim göstermesin
        if not self.mgr.settings.get("tray_hint_shown"):
            self.mgr.settings["tray_hint_shown"] = True
            self.mgr.save()
            self.tray.showMessage(APP_NAME, _t("Program arka planda çalışmaya devam ediyor."), self.icon, 2000)

    # ---------------------------------------------------------- dil
    def set_language(self, code):
        """Dili anında değiştirir, program kapanmaz: indirmeler sürer; menüler, yan menü, liste ve açık
        indirme pencereleri yeni dille yeniden kurulur."""
        if code not in i18n.LANGUAGES and code != "auto":
            return
        self.mgr.settings["language"] = code
        self.mgr.save()
        target = i18n.resolve(code)  # auto → Windows'un dili
        if target == i18n.language():
            for a in self.menuBar().findChild(QMenu, "language").actions():  # yalnızca işaret değişir
                if a.isCheckable():
                    a.setChecked(a.data() == code)
            return
        i18n.set_language(target)  # çevrilmiş tablolar (durum, sütun, kategori…) yeniden dolar
        i18n.apply_to_app(QApplication.instance())  # Qt'nin kendi metinleri, Arapçada sağdan sola
        self._retranslate()

    def _retranslate(self):
        filt, sel = self._filter, set(self.selected_ids())
        old_actions = [v for k, v in vars(self).items() if k.startswith("a_") and isinstance(v, QAction)]
        for w in (self.sel_lbl, self.speed_lbl):
            self.statusBar().removeWidget(w)
            w.deleteLater()
        self.setMenuBar(QMenuBar(self))  # eski menü çubuğu (ve menüleri) silinir
        self._build_actions()
        self._build_ui()  # yeni gezinme ağacı ve liste; eskileri setCentralWidget ile silinir
        for a in old_actions:
            a.deleteLater()
        old_menu = self.tray.contextMenu()
        self.tray.setContextMenu(self._tray_menu())
        old_menu.deleteLater()
        if not self.mgr.torrents:
            self.a_torrent.setEnabled(False)
            self.a_magnet.setEnabled(False)
        for i in range(self.tree.topLevelItemCount()):  # seçili kategori korunsun
            top = self.tree.topLevelItem(i)
            for it in [top] + [top.child(j) for j in range(top.childCount())]:
                if it.data(0, Qt.UserRole) == filt:
                    self.tree.setCurrentItem(it)
        self._filter = self.tree.currentItem().data(0, Qt.UserRole)  # seçili kuyruk silindiyse "Tüm İndirmeler"e dön
        self._visible, self._rows = [], []
        self.refresh(force=True)
        self._select_rows([r for r, iid in enumerate(self._rows) if iid in sel])
        for iid, d in list(self.progress_dialogs.items()):  # açık indirme pencereleri yeni dille
            pos = d.pos()
            self.progress_dialogs.pop(iid, None)
            d.close()
            d.deleteLater()
            self.show_progress(iid)
            nd = self.progress_dialogs.get(iid)
            if nd is not None:
                nd.move(pos)

    def quit_requested(self):
        """Menü/tepsi/Ctrl+Q ile çıkış: inmekte olan dosya varsa onay sorulur. (Güncelleme ve kaldırma programının
        istediği kapanış quit_app'i doğrudan çağırır, soru sormaz.)"""
        n = self.mgr.active_count()
        if n and self.mgr.settings.get("confirm_exit", True):
            box = QMessageBox(QMessageBox.Question, APP_NAME,
                              _t("{0} indirme sürüyor. TurboDM kapatılsın mı?\n(İndirmeler sonra kaldığı yerden devam edebilir.)").format(n),
                              QMessageBox.Yes | QMessageBox.No, self)
            box.setDefaultButton(QMessageBox.No)
            if box.exec() != QMessageBox.Yes:
                return
        self.quit_app()

    def _current_queue(self):
        """Kenar çubuğunda bir kuyruk seçiliyse o, değilse Ana kuyruk."""
        return self._filter[6:] if self._filter.startswith("queue:") else "main"

    def _update_limit_action(self):
        kb = self.mgr.settings["speed_limit_kb"]
        self.a_limit.blockSignals(True)
        self.a_limit.setText(_t("Hız sınırı ({0})").format(fmt_speed(kb * 1024)) if kb else _t("Hız sınırı (Seçenekler'de ayarlanmadı)"))
        self.a_limit.setEnabled(bool(kb))
        self.a_limit.setChecked(bool(kb) and self.mgr.settings.get("speed_limit_enabled", True))
        self.a_limit.blockSignals(False)

    def _toggle_speed_limit(self, on):
        self.mgr.settings["speed_limit_enabled"] = bool(on)
        self.mgr.apply_settings()

    def _column_menu(self, pos):
        m = QMenu(self)
        hidden = set(self.mgr.settings.get("hidden_columns", []))
        for c in range(NAME + 1, len(COLUMNS)):
            a = m.addAction(COLUMNS[c])
            a.setCheckable(True)
            a.setChecked(c not in hidden)
            a.toggled.connect(lambda on, col=c: self._set_column(col, on))
        m.addSeparator()
        m.addAction(self.a_group)
        m.exec(self.table.horizontalHeader().mapToGlobal(pos))

    def _set_column(self, col, visible):
        hidden = [c for c in self.mgr.settings.get("hidden_columns", []) if c != col]
        if not visible:
            hidden.append(col)
        self.mgr.settings["hidden_columns"] = sorted(hidden)
        self.table.setColumnHidden(col, not visible)
        self.mgr.save()

    def batch_add_prompt(self):
        clip = QApplication.clipboard().text()
        d = BatchAddDialog(self, clip if extract_urls(clip) else "")
        bring_to_front(d)

    def export_list(self):
        path, _ = QFileDialog.getSaveFileName(self, _t("Listeyi dışa aktar"),
                                              os.path.join(os.path.expanduser("~"), "TurboDM-liste.json"), "JSON (*.json)")
        if path:
            ids = self.selected_ids()
            n = self.mgr.export_list(path, set(ids) if len(ids) > 1 else None)
            self.statusBar().showMessage(_t("{0} indirme dışa aktarıldı").format(n), 5000)

    def import_list(self):
        path, _ = QFileDialog.getOpenFileName(self, _t("Listeyi içe aktar"), os.path.expanduser("~"), "JSON (*.json)")
        if path:
            try:
                n = self.mgr.import_list(path)
            except (OSError, ValueError) as e:
                QMessageBox.warning(self, APP_NAME, _t("Liste okunamadı: {0}").format(e))
                return
            self.refresh(force=True)
            self.statusBar().showMessage(_t("{0} indirme içe aktarıldı").format(n), 5000)

    def quit_app(self):
        self._quitting = True
        self.timer.stop()
        for d in list(self.progress_dialogs.values()):  # bağımsız indirme pencereleri de kapansın
            d.close()
        self.mgr.shutdown()
        if self.srv:
            self.srv.shutdown()
        self.tray.hide()
        QApplication.quit()

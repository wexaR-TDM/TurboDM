import math
import os
import sys
import tempfile
import time

# Kullanım: python ekran_goruntusu.py <auto|light|dark> <çıktı.png> [dil: tr|en|…]
# README.md Türkçe, README.en.md İngilizce ekran görüntülerini kullanır.
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QPA_FONTDIR"] = r"C:\Windows\Fonts"
tmp = tempfile.mkdtemp(prefix="tdm_shot_")
os.environ["APPDATA"] = tmp
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))  # proje kökü
from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

mode, out = sys.argv[1], sys.argv[2]
lang = sys.argv[3] if len(sys.argv) > 3 else "tr"
os.environ["TURBODM_LANG"] = lang
app = QApplication([])
app.setStyle("Fusion")
app.setFont(QFont("Segoe UI", 9))
from turbodm import manager as M  # noqa: E402
M.DEFAULT_SETTINGS.update(download_root=os.path.join(tmp, "dl"), server_port=9697, torrent_port=6997,
                          auto_update_check=False, theme=mode)
from turbodm import i18n  # noqa: E402
from turbodm.gui import MainWindow, apply_theme  # noqa: E402
i18n.apply_to_app(app)
apply_theme(app)
mgr = M.Manager()
rows = [("Doğa Belgeseli - Kuzey Ormanları.mp4", "downloading", 512, 0.62, 48.4, "video"),
        ("ubuntu-24.04-desktop-amd64.iso", "downloading", 5900, 0.31, 61.2, "general"),
        ("Proje Sunumu.pdf", "completed", 14, 1, 0, "documents"),
        ("Albüm - Canlı Kayıt.zip", "completed", 820, 1, 0, "compressed"),
        ("kurulum-araci.exe", "queued", 96, 0, 0, "programs"),
        ("Oyun Kurulumu.iso", "stopped", 33000, 0.44, 0, "general"),
        ("eski-baglanti.rar", "error", 300, 0.12, 0, "compressed")]
if lang != "tr":  # örnek dosya adları da o dilde (İngilizce)
    names = ["Nature Documentary - Northern Forests.mp4", "ubuntu-24.04-desktop-amd64.iso", "Project Presentation.pdf",
             "Album - Live Recording.zip", "setup-tool.exe", "Game Setup.iso", "old-link.rar"]
    rows = [(n,) + r[1:] for n, r in zip(names, rows)]
for name, status, mb, frac, speed, cat in rows:
    it = mgr.add_http(f"https://ornek.test/{name}", os.path.join(tmp, "dl", name), start=False)
    it.size, it.status, it.category = mb * 1024 * 1024, status, cat
    it.done_bytes = int(it.size * frac)
    if 0 < frac < 1:  # bağlantı başına parçalı çubuk görünsün
        step = it.size // 8
        it.segments = [[i * step, (i + 1) * step - 1, i * step + int(step * min(1.0, frac * (1.4 - i * 0.1)))]
                       for i in range(8)]
    it.speed = speed * 1024 * 1024
    it.error = "HTTP 404" if status == "error" else None
win = MainWindow(mgr)
win.resize(1280, 640)
win.show()
win.select_where(lambda it: it.status == "stopped")
for _ in range(15):
    app.processEvents()
    time.sleep(0.02)
win.refresh(force=True)
win.sp_graph.samples.extend((40 + 60 * abs(math.sin(i / 9)) + i % 5 * 3) * 1024 * 1024 for i in range(60))  # hız grafiği dolu görünsün
win.sp_graph.samples[-1] = 109.6 * 1024 * 1024
app.processEvents()
win.grab().save(out)
import shutil  # noqa: E402
shutil.rmtree(tmp, ignore_errors=True)  # geçici ayar/indirme klasörü kalmasın
os._exit(0)

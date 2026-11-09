"""TurboDM arayüz testleri (ekran dışı Qt). Yalnızca yerel sunucular; internete çıkmaz.
Çalıştırma:  python -m unittest tests.test_gui -v
"""
import atexit
import hashlib
import shutil
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.environ["TURBODM_LANG"] = "tr"  # testler Türkçe metinlerle yazıldı; sistem dilinden bağımsız
os.makedirs(os.path.join(ROOT, "build", "tmp"), exist_ok=True)
TMP = tempfile.mkdtemp(prefix="tdm_gui_", dir=os.path.join(ROOT, "build", "tmp"))  # proje içinde
atexit.register(shutil.rmtree, TMP, True)  # bilgisayarda test kalıntısı bırakma
atexit.register(shutil.rmtree, os.path.join(tempfile.gettempdir(), "TurboDM-update"), True)
os.environ.update(APPDATA=os.path.join(TMP, "appdata"), QT_QPA_PLATFORM="offscreen",
                  QT_QPA_FONTDIR=os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Fonts"))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))

from PySide6.QtWidgets import QApplication, QTabWidget, QToolBar  # noqa: E402
from test_turbodm import FakeServer  # noqa: E402
from turbodm import manager as M, server, updater  # noqa: E402

APP = QApplication.instance() or QApplication([])
import turbodm.gui as G  # noqa: E402

PORT = 9690 + os.getpid() % 50
M.DEFAULT_SETTINGS.update(download_root=os.path.join(TMP, "dl"), server_port=PORT,
                          torrent_port=6990 + os.getpid() % 50, auto_update_check=False)


def pump(seconds=0.0, until=None, win=None):
    """Qt olay döngüsünü (ve TurboDM'in 0,5 sn'lik tik'ini) çalıştır."""
    end = time.time() + seconds
    while True:
        APP.processEvents()
        if until and until():
            return True
        if time.time() >= end:
            return bool(until and until())
        time.sleep(0.02)


def visible(cls_name):
    return [w for w in QApplication.topLevelWidgets() if type(w).__name__ == cls_name and w.isVisible()]


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = FakeServer()
        cls.data = os.urandom(6 * 1024 * 1024)
        cls.s.files["/arsiv.zip"] = cls.data
        cls.win = G.MainWindow(M.Manager())
        cls.win.show()
        cls.win.perform_power_action = mock.Mock()   # TESTTE GERÇEK KAPATMA/UYKU YOK

    @classmethod
    def tearDownClass(cls):
        cls.win.quit_app()
        cls.s.close()

    def close_dialogs(self):
        for w in QApplication.topLevelWidgets():
            if w is not self.win and w.isVisible():
                w.close()
        pump(0.1)

    def tearDown(self):
        self.close_dialogs()

    def test_add_download_via_dialog_and_progress_window(self):
        d = G.FileInfoDialog(self.win, self.s.url("/arsiv.zip"))
        d.show()
        self.assertTrue(pump(10, lambda: "Devam ettirme" in d.size_lbl.text()), d.size_lbl.text())
        self.assertEqual(d.cat.currentData(), "compressed")
        self.assertTrue(d.path_edit.text().endswith("Compressed"), "alan yalnızca klasör olmalı")
        d._go(True)
        it = [i for i in self.win.mgr.items.values() if i.url.endswith("arsiv.zip")][-1]
        pd = self.win.progress_dialogs.get(it.id)
        self.assertIsNotNone(pd, "ilerleme penceresi açılmadı")
        # ana pencereye bağlı değil: ana pencere simge durumuna küçültülünce indirme penceresi açık kalır
        self.assertIsNone(pd.parentWidget())
        self.win.showMinimized()
        pump(0.2)
        self.assertTrue(pd.isVisible() and not pd.isMinimized())
        self.win.showNormal()
        for hint in (G.Qt.WindowMinimizeButtonHint, G.Qt.WindowMaximizeButtonHint, G.Qt.WindowCloseButtonHint):
            self.assertTrue(pd.windowFlags() & hint, f"başlık çubuğunda düğme yok: {hint}")
        tabs = pd.findChild(QTabWidget)
        self.assertEqual([tabs.tabText(i) for i in range(tabs.count())],
                         ["İndirme durumu", "Hız sınırlayıcı", "Bitince yapılacaklar"])
        self.assertTrue(pump(30, lambda: it.status == "completed"), it.error)
        self.assertEqual(open(it.path, "rb").read(), self.data)
        self.assertTrue(visible("QMessageBox"), "'İndirme tamamlandı' penceresi açılmadı")

    def test_complete_action_countdown_can_be_cancelled(self):
        self.s.files["/b.bin"] = os.urandom(2 * 1024 * 1024)
        it = self.win.mgr.add_http(self.s.url("/b.bin"), os.path.join(TMP, "dl", "b.bin"), start=False)
        it.on_complete = {"show_dialog": False, "shutdown": True}
        self.win.mgr.start(it.id)
        self.assertTrue(pump(30, lambda: visible("PowerActionDialog")), "geri sayım açılmadı")
        dlg = visible("PowerActionDialog")[0]
        self.assertIn("kapatılacak", dlg.msg.text())
        dlg.reject()
        pump(1.5)
        self.win.perform_power_action.assert_not_called()

    def test_error_dialog_has_retry(self):
        it = self.win.mgr.add_http(self.s.url("/yok.bin"), os.path.join(TMP, "dl", "yok.bin"), start=True)
        self.assertTrue(pump(20, lambda: it.status == "error"))
        pump(1)
        boxes = [b for b in visible("QMessageBox") if b.windowTitle() == "İndirme hatası"]
        self.assertTrue(boxes, "hata penceresi açılmadı")
        self.assertIn("Tekrar Dene", [b.text() for b in boxes[0].buttons()])

    def test_dialogs_open(self):
        for cls in (G.OptionsDialog, G.SchedulerDialog):
            d = cls(self.win)
            d.show()
            pump(0.2)
            d.close()
        tabs = G.OptionsDialog(self.win).findChild(QTabWidget)
        self.assertEqual([tabs.tabText(i) for i in range(tabs.count())],
                         ["Genel", "Bağlantı", "Video", "Torrent", "Kategoriler"])

    def test_update_check_download_verify_and_reject_corrupt(self):
        setup = os.urandom(500_000)
        manifest = {"version": "99.0.0", "build": "x", "url": self.s.url("/TurboDM-Setup-99.exe"),
                    "sha256": hashlib.sha256(setup).hexdigest(), "size": len(setup), "notes": "• deneme"}
        from test_turbodm import sign_manifest  # test anahtarıyla imzalı güncelleme bilgisi
        pub = sign_manifest(manifest)
        self.s.files["/latest.json"] = json.dumps(manifest).encode()
        self.s.files["/TurboDM-Setup-99.exe"] = setup
        launched = []
        with mock.patch.object(self.win.mgr, "settings", dict(self.win.mgr.settings, update_repo=self.s.url("/latest.json"))), \
                mock.patch.object(updater, "PUBLIC_KEYS", (pub,)), \
                mock.patch.object(updater, "ALLOWED_DOWNLOAD", (self.s.url("/"),)), \
                mock.patch.object(updater, "run_installer", launched.append), \
                mock.patch.object(G.ytdlp, "update_available", return_value=("1", "1", False)):
            d = G.UpdateDialog(self.win)
            d.show()
            self.assertTrue(pump(10, lambda: d.app_btn.isVisible()), d.app_lbl.text())
            self.assertTrue(d.app_note.isVisible() and "kaldığı yerden" in d.app_note.text())
            d._install()
            self.assertTrue(pump(15, lambda: launched), d.app_lbl.text())
            self.assertEqual(open(launched[0], "rb").read(), setup)
            d.close()
            # bozuk dosya: kurulum başlatılmamalı
            self.s.files["/TurboDM-Setup-99.exe"] = setup[:-1] + b"\0"
            launched.clear()
            d = G.UpdateDialog(self.win)
            d.show()
            pump(10, lambda: d.app_btn.isVisible())
            d._install()
            self.assertTrue(pump(15, lambda: "başarısız" in d.app_lbl.text()), d.app_lbl.text())
            self.assertEqual(launched, [])

    def test_browser_menu_flow_opens_preselected_dialog(self):
        info = {"title": "Deneme | Video ™", "duration": 10, "extractor": "Youtube", "choices": [
            {"label": "720p", "format": "22", "ext": "mp4", "size": 1000, "height": 720, "streams": None},
            {"label": "Yalnızca ses · m4a", "format": "140", "ext": "m4a", "size": 100, "height": 0, "streams": None}]}
        with mock.patch.object(G.ytdlp, "inspect", return_value=info):
            url = "https://www.youtube.com/watch?v=MENU"
            body = json.dumps({"url": url, "cookies": []}).encode()
            req = urllib.request.Request(f"http://127.0.0.1:{PORT}/formats", data=body,
                                         headers={"X-TurboDM": "1", "Content-Type": "application/json"})
            res = {}
            threading.Thread(target=lambda: res.update(json.load(urllib.request.urlopen(req, timeout=10))),
                             daemon=True).start()
            self.assertTrue(pump(10, lambda: res))
            self.assertEqual([c["label"] for c in res["choices"]], ["720p", "Yalnızca ses · m4a"])
            server.requests.put({"url": url, "title": res["title"], "choice": res["choices"][1], "cookies": []})
            self.assertTrue(pump(5, lambda: visible("FileInfoDialog")))
            d = visible("FileInfoDialog")[0]
            self.assertEqual(d.quality.currentText(), "Yalnızca ses · m4a")
            self.assertEqual(d.name, "Deneme _ Video ™.m4a")
            self.assertFalse(any(i.url == url for i in self.win.mgr.items.values()), "soru sormadan başladı")

    def test_torrent_link_opens_torrent_dialog_not_html(self):
        from test_turbodm import TorrentLinkTests
        self.s.files["/x/film.torrent"] = TorrentLinkTests.TORRENT
        self.s.files["/sayfa/y.torrent"] = b"<!DOCTYPE html><html><body>Download</body></html>"
        # site torrent yerine indirme sayfası veriyor: .html kaydedilmemeli, ne yapılacağı anlatılmalı
        d = G.FileInfoDialog(self.win, self.s.url("/sayfa/y.torrent"))
        d.show()
        self.assertTrue(pump(10, lambda: "web sayfası" in d.size_lbl.text()), d.size_lbl.text())
        self.assertFalse(any(b.isEnabled() for b in d.go_buttons))
        d.close()
        if not self.win.mgr.torrents:
            self.skipTest("libtorrent yok")
        # gerçek .torrent bağlantısı: doğrudan torrent dosya seçimi penceresi
        d = G.FileInfoDialog(self.win, self.s.url("/x/film.torrent"))
        d.show()
        self.assertTrue(pump(10, lambda: visible("TorrentAddDialog")), d.size_lbl.text())
        self.assertFalse(d.isVisible())
        self.close_dialogs()
        # tarayıcının indirdiği .torrent (eklenti köprüsü)
        p = os.path.join(TMP, "tarayici.torrent")
        with open(p, "wb") as f:
            f.write(TorrentLinkTests.TORRENT)
        server.requests.put({"url": "https://site/x.torrent", "torrent_file": p})
        self.assertTrue(pump(5, lambda: visible("TorrentAddDialog")))
        self.assertFalse(visible("FileInfoDialog"), "torrent dosyası HTTP indirmesi olarak açılmamalı")

    def test_bulk_selection_with_checkboxes(self):
        from PySide6.QtCore import Qt as QtC
        from PySide6.QtTest import QTest
        win, t = self.win, self.win.table
        for iid in list(win.mgr.order):  # önceki testlerin kayıtları
            win.mgr.remove(iid, False)
        win.a_group.setChecked(False)  # satır numaraları grup satırları olmadan
        self.addCleanup(win.a_group.setChecked, True)
        d = os.path.join(TMP, "toplu")
        items = [win.mgr.add_http(self.s.url(f"/t{i}.bin"), os.path.join(d, f"t{i}.bin"), start=False)
                 for i in range(4)]
        items[3].status = "completed"
        win.refresh(force=True)
        pump(0.2)

        def click_box(row):
            rect = t.visualRect(t.model().index(row, G.SEL))
            QTest.mouseClick(t.viewport(), QtC.LeftButton, QtC.NoModifier, rect.center())
            pump(0.05)

        click_box(0)
        click_box(2)  # Ctrl'siz: önceki seçim korunmalı
        self.assertEqual(win.selected_ids(), [items[0].id, items[2].id])
        self.assertEqual([t.item(r, G.SEL).checkState() == QtC.Checked for r in range(4)], [True, False, True, False])
        self.assertIn("2 indirme seçili", win.sel_lbl.text())
        click_box(0)  # tekrar tıklayınca seçimden çıkar
        self.assertEqual(win.selected_ids(), [items[2].id])
        t.horizontalHeader().sectionClicked.emit(G.SEL)  # başlık kutusu: tümü
        self.assertEqual(len(win.selected_ids()), 4)
        self.assertEqual(t.horizontalHeaderItem(G.SEL).text(), "☑")
        t.horizontalHeader().sectionClicked.emit(G.SEL)  # tekrar: hiçbiri
        self.assertEqual(win.selected_ids(), [])
        win.select_where(win.SELECT_PRESETS[0][1])  # bitmemişler
        self.assertEqual(win.selected_ids(), [i.id for i in items[:3]])
        win.refresh(force=True)  # liste yenilenince çoklu seçim korunmalı
        self.assertEqual(win.selected_ids(), [i.id for i in items[:3]])
        with mock.patch.object(G.QMessageBox, "exec", lambda self: None), \
                mock.patch.object(G.QMessageBox, "clickedButton",
                                  lambda self: next(b for b in self.buttons() if b.text() == "Listeden sil")):
            win.delete_selected(False)  # toplu silme
        self.assertEqual(win.mgr.order, [items[3].id])

    def test_theme_light_dark_switch(self):
        from PySide6.QtGui import QPalette
        try:
            for mode, dark in (("light", False), ("dark", True)):
                G.theme.apply(APP, mode)
                pump(0.1)
                self.assertEqual(G.theme.T["dark"], dark)
                bg = APP.palette().color(QPalette.Window)
                self.assertEqual(bg.lightness() < 128, dark, mode)
                self.assertIn(G.theme.T["accent"].lower(), APP.styleSheet().lower())
                # simgeler yeniden çizildi (araç çubuğu eylemleri)
                self.assertFalse(self.win.a_add.icon().isNull())
            self.assertIsNotNone(G.theme.status_icon("completed"))
        finally:
            G.theme.apply(APP, "auto")

    def test_new_windows_open_centered(self):
        from PySide6.QtGui import QCursor, QGuiApplication
        scr = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        g = scr.availableGeometry()
        it = self.win.mgr.add_http(self.s.url("/arsiv.zip"), os.path.join(TMP, "dl", "orta.zip"), start=False)
        for d in (G.OptionsDialog(self.win), G.ProgressDialog(self.win, it.id)):
            d.show()
            pump(0.2)
            c = d.frameGeometry().center()
            self.assertLess(abs(c.x() - g.center().x()), 40, type(d).__name__)
            self.assertLess(abs(c.y() - g.center().y()), 60, type(d).__name__)
            d.close()
        self.win.mgr.remove(it.id, False)

    def test_dash_stream_opens_video_dialog_with_format_choice(self):
        info = {"title": "Örnek akış", "duration": 60, "extractor": "Generic", "choices": [
            {"label": "1080p · mp4", "format": "v1080+a", "ext": "mp4", "size": 1000, "height": 1080, "streams": None}]}
        seen = {}

        def fake_inspect(url, ffmpeg=None, cookies=None, headers=None):
            seen.update(url=url, headers=headers)
            return info
        with mock.patch.object(G.ytdlp, "inspect", fake_inspect), mock.patch.object(G.ytdlp, "available", lambda: True):
            hdr = {"Referer": "https://oynatici.example/embed/1", "Origin": "https://oynatici.example"}
            d = G.FileInfoDialog(self.win, "https://cdn.example/akis/manifest.mpd", hdr)
            d.show()
            self.assertTrue(pump(10, lambda: d.video_info), d.size_lbl.text())
            self.assertEqual(seen["url"], "https://cdn.example/akis/manifest.mpd")
            self.assertEqual(seen["headers"]["Origin"], "https://oynatici.example")  # oynatıcının kökeni iletilir
            self.assertTrue(d.form.isRowVisible(d.fmt), "biçim seçimi görünmüyor")
            self.assertEqual([d.fmt.itemData(i) for i in range(d.fmt.count())], ["", "mkv", "avi", "mp3"])
            # seçilen biçim indirmeye yazılır (indirme bitince dönüştürülür)
            d.fmt.setCurrentIndex(d.fmt.findData("mkv"))
            before = set(self.win.mgr.items)
            d._go(False)
            new = [self.win.mgr.items[i] for i in self.win.mgr.items if i not in before]
            self.assertEqual(len(new), 1)
            self.assertEqual(new[0].extra.get("convert"), "mkv")
            self.win.mgr.remove(new[0].id, False)

    def test_release_notes_menu_opens_public_notes(self):
        opened = []
        with mock.patch.object(G.QDesktopServices, "openUrl", lambda u: opened.append(u.toString())):
            act = next(a for m in self.win.menuBar().findChildren(G.QMenu) for a in m.actions()
                       if a.text() == "Sürüm notları")
            act.trigger()
        self.assertEqual(opened, ["https://github.com/wexaR-TDM/TurboDM/blob/main/SURUM_NOTLARI.md"])

    def test_browser_download_checked_before_takeover(self):
        # Tarayıcının indirmesi devralınmadan önce TurboDM dosyaya ulaşabiliyor mu? (metin2.download gibi Cloudflare
        # korumalı sitelerde koruma TurboDM'i engeller: indirme tarayıcıda kalmalı, kullanıcıya nedeni söylenmeli)
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path.startswith("/korumali"):  # Cloudflare "Just a moment…" yanıtının özü
                    body = b"<html><title>Just a moment...</title></html>"
                    self.send_response(403)
                    self.send_header("Server", "cloudflare")
                    self.send_header("cf-mitigated", "challenge")
                    self.send_header("Content-Type", "text/html")
                elif self.path.startswith("/giris"):  # dosya yerine giriş sayfası
                    body = b"<html>login</html>"
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                else:
                    body = b"PK" + b"x" * 100
                    self.send_response(200)
                    self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        base = f"http://127.0.0.1:{srv.server_port}"
        check = self.win._check_handler
        self.assertIsNone(check({"url": base + "/dosya.zip", "mime": "application/zip"}))  # erişilebilir: devral
        reason = check({"url": base + "/korumali/client.zip", "mime": "application/zip"})
        self.assertIn("Cloudflare", reason)
        self.assertIn("tarayıcıda", reason)
        self.assertIn("web sayfası", check({"url": base + "/giris/dosya.zip", "mime": "application/zip"}))
        # köprü: "check" istenince reddedilen indirme listeye eklenmez, eklentiye ok:false döner, kullanıcıya bildirilir
        import json as _json
        import urllib.request
        while not G.server.requests.empty():
            G.server.requests.get()
        port = self.win.mgr.settings["server_port"]
        req = urllib.request.Request(f"http://127.0.0.1:{port}/add", method="POST",
                                     data=_json.dumps({"url": base + "/korumali/a.zip", "mime": "application/zip",
                                                       "check": True}).encode(),
                                     headers={"Content-Type": "application/json", "X-TurboDM": "1"})
        with urllib.request.urlopen(req, timeout=30) as r:
            self.assertEqual(_json.loads(r.read())["ok"], False)
        queued = G.server.requests.get(timeout=5)
        self.assertIn("notice", queued)  # tepside nedeni gösterilir; indirme eklenmez
        self.assertTrue(G.server.requests.empty())

    def test_video_link_cannot_start_until_video_found(self):
        # YouTube bağlantısı elle eklendi: video incelenirken ya da inceleme başarısız olursa "Başlat" kapalı kalmalı;
        # yoksa video yerine sitenin web sayfası iner (forumdaki "indirdiği şey video değildi" bildirimi)
        gate = threading.Event()
        outcome = {}

        def fake_inspect(url, ffmpeg=None, cookies=None, headers=None):
            gate.wait(10)
            if "err" in outcome:
                raise RuntimeError(outcome["err"])
            return {"title": "Örnek", "duration": 10, "extractor": "Youtube", "choices": [
                {"label": "1080p · mp4", "format": "137+140", "ext": "mp4", "size": 1000, "height": 1080, "streams": None}]}
        with mock.patch.object(G.ytdlp, "inspect", fake_inspect), mock.patch.object(G.ytdlp, "available", lambda: True):
            for err in ("Sign in to confirm you're not a bot", None):
                gate.clear()
                outcome.clear()
                if err:
                    outcome["err"] = err
                d = G.FileInfoDialog(self.win, "https://www.youtube.com/watch?v=abcdefghijk")
                d.show()
                pump(0.2)
                self.assertFalse(any(b.isEnabled() for b in d.go_buttons))  # incelenirken başlatılamaz
                gate.set()
                pump(1.0, lambda: d.video_info or "alınamadı" in d.size_lbl.text())
                if err:
                    self.assertIn("alınamadı", d.size_lbl.text())
                    self.assertFalse(any(b.isEnabled() for b in d.go_buttons))  # sayfa indirilmesin
                else:
                    self.assertTrue(d.video_info)
                    self.assertTrue(all(b.isEnabled() for b in d.go_buttons))
                d.close()

    def test_handoff_answered_after_app_restart(self):
        # TurboDM devirden sonra kapanıp yeniden açıldı (çökme): bellekteki devir kayıtları yok
        win = self.win
        h = win._handoff_handler
        now_ms = time.time() * 1000
        self.assertEqual(h({"id": "eski-devir", "t": (win._started - 60) * 1000})["state"], "failed")  # hiç kaydedilmemiş
        self.assertEqual(h({"id": "yeni-devir", "t": now_ms}), {"state": "pending"})  # az önce geldi, işleniyor
        self.assertEqual(h({"id": "eski-eklenti"}), {"state": "gone"})               # zaman göndermeyen eski eklenti
        # indirme kaydedilmişti: yeniden açılan TurboDM onu kayıttan bulur (tarayıcıda ikinci kez inmez)
        it = win.mgr.add_http(self.s.url("/arsiv.zip"), os.path.join(TMP, "dl", "devir-kayit.zip"), start=False)
        self.addCleanup(lambda: it.id in win.mgr.items and win.mgr.remove(it.id))
        it.extra["handoff"] = "kayitli-devir"
        it.done_bytes = 100
        self.assertEqual(h({"id": "kayitli-devir", "t": (win._started - 60) * 1000}), {"state": "ok"})
        # eklenti tarayıcıda başlattığını bildirdi (TurboDM devri tanımasa da): adres tarayıcıya bırakılır
        G.server._owners.clear()
        self.assertEqual(h({"id": "eski-devir", "returned": True, "url": "https://example.com/b.zip"}),
                         {"state": "returned"})
        self.assertEqual(G.server.claim("https://example.com/b.zip"), {"handle": False, "reason": "browser"})
        G.server._owners.clear()

    def test_outdated_extension_warning(self):
        # Köprü eski elle kurulmuş eklenti bildirdi: kullanıcıya eklentiyi nasıl yenileyeceği söylenir
        before = {id(w) for w in APP.topLevelWidgets() if isinstance(w, G.QMessageBox)}
        self.win._handle_external({"ext_outdated": {"version": "", "latest": "1.7.6"}})
        pump(0.2)
        boxes = [w for w in APP.topLevelWidgets() if isinstance(w, G.QMessageBox) and id(w) not in before]
        self.assertEqual(len(boxes), 1)
        self.assertIn("brave://extensions", boxes[0].text())
        self.assertIn("1.7.6", boxes[0].text())
        boxes[0].close()

    def test_handoff_failed_download_goes_back_to_browser(self):
        # Eklenti tarayıcıdaki indirmeyi iptal edip TurboDM'e verdi; indirme TurboDM'de hiç veri alamadan erişim
        # hatasıyla düşerse (ör. 403) eklenti bunu /handoff ile öğrenir ve indirmeyi tarayıcıda yeniden başlatır.
        win = self.win
        h = win._handoff_handler
        self.assertEqual(h({"id": "yok"}), {"state": "gone"})
        # pencere açık (kullanıcı henüz karar vermedi): bekle
        win._handle_external({"url": self.s.url("/arsiv.zip"), "handoff": "devir-1"})
        pump(0.3)
        d = next(w for w in APP.topLevelWidgets() if isinstance(w, G.FileInfoDialog) and getattr(w, "handoff", "") == "devir-1")
        self.assertEqual(h({"id": "devir-1"}), {"state": "pending"})
        d.path_edit.setText(os.path.join(TMP, "dl"))
        d._go(False)  # "Sonra İndir": kayıt oluşur, henüz veri yok
        iid = win._handoffs["devir-1"]["iid"]
        it = win.mgr.items[iid]
        self.assertEqual(h({"id": "devir-1"})["state"], "pending")
        # sunucu reddetti, hiç veri inmedi: hata uyarısı hemen açılmaz (eklenti geri verecek), durum "failed"
        it.status, it.error, it.done_bytes = "error", "HTTP 403 Forbidden", 0
        win._error_dialog(it)
        self.assertNotIn(iid, win._error_boxes)
        self.assertEqual(h({"id": "devir-1"}), {"state": "failed", "error": "HTTP 403 Forbidden"})
        # eklenti tarayıcıda başlattı: TurboDM'deki başarısız kayıt kaldırılır, kullanıcıya nedeni söylenir
        while not G.server.requests.empty():
            G.server.requests.get()
        self.assertEqual(h({"id": "devir-1", "returned": True}), {"state": "returned"})
        win._handle_external(G.server.requests.get(timeout=5))
        self.assertNotIn(iid, win.mgr.items)
        self.assertIn("tarayıcıda", win.statusBar().currentMessage())
        self.assertEqual(h({"id": "devir-1"}), {"state": "gone"})
        # veri inmeye başladıysa (ya da bağlantı/disk hatası gibi başka bir hata) geri verilmez
        win._handle_external({"url": self.s.url("/arsiv.zip"), "handoff": "devir-2"})
        pump(0.3)
        d = next(w for w in APP.topLevelWidgets() if isinstance(w, G.FileInfoDialog) and getattr(w, "handoff", "") == "devir-2")
        d.path_edit.setText(os.path.join(TMP, "dl"))
        d._go(False)
        it = win.mgr.items[win._handoffs["devir-2"]["iid"]]
        it.status, it.error, it.done_bytes = "error", "HTTP 403 Forbidden", 4096
        self.assertEqual(h({"id": "devir-2"}), {"state": "ok"})
        it.status, it.error, it.done_bytes = "error", "Bağlantı koptu", 0
        self.assertEqual(h({"id": "devir-2"}), {"state": "pending"})
        win.mgr.remove(it.id, False)
        # kullanıcı pencereyi kapatıp vazgeçti: eklenti izlemeyi bırakır, tarayıcıda başlatmaz
        win._handle_external({"url": self.s.url("/arsiv.zip"), "handoff": "devir-3"})
        pump(0.3)
        d = next(w for w in APP.topLevelWidgets() if isinstance(w, G.FileInfoDialog) and getattr(w, "handoff", "") == "devir-3")
        d.reject()
        pump(0.1)
        self.assertEqual(h({"id": "devir-3"}), {"state": "gone"})

    def test_batch_add_probes_names_and_adds_to_queue(self):
        self.s.files["/belge.pdf"] = b"x" * 1000
        text = f"İndirilecekler:\n{self.s.url('/arsiv.zip')}\nşu da: {self.s.url('/belge.pdf')}, ve tekrar {self.s.url('/arsiv.zip')}"
        d = G.BatchAddDialog(self.win, text)
        self.assertEqual(d.table.rowCount(), 2)  # tekrar eden bağlantı bir kez
        end = time.time() + 15
        while time.time() < end and any(v is None for v in d.info.values()):
            pump(0.1)
        self.assertEqual(d.table.item(1, 2).text(), G.fmt_size(1000))  # sorgulanan gerçek boyut
        d.mode.setCurrentIndex(1)  # Ana kuyruğa ekle (hemen başlatma)
        before = set(self.win.mgr.items)
        d._add()
        new = [self.win.mgr.items[i] for i in set(self.win.mgr.items) - before]
        names = sorted(os.path.basename(i.path) for i in new)  # aynı adlı dosya varsa "arsiv (1).zip" olur
        self.assertTrue(names[0].startswith("arsiv") and names[0].endswith(".zip") and names[1] == "belge.pdf", names)
        self.assertTrue(all(i.in_queue and i.status == "queued" for i in new))
        for i in new:
            self.win.mgr.remove(i.id)

    def test_checksum_dialog_verifies_file(self):
        import hashlib
        path = os.path.join(TMP, "dogrula.bin")
        with open(path, "wb") as f:
            f.write(self.data)
        d = G.ChecksumDialog(self.win, path)
        end = time.time() + 15
        while time.time() < end and not d.out["sha256"].text():
            pump(0.1)
        self.assertEqual(d.out["sha256"].text(), hashlib.sha256(self.data).hexdigest())
        d.expected.setText(hashlib.md5(self.data).hexdigest().upper())  # büyük harf de olur
        self.assertIn("✔", d.result.text())
        d.expected.setText("0" * 64)
        self.assertIn("✖", d.result.text())
        d.close()

    def test_exit_asks_when_downloads_running(self):
        it = self.win.mgr.add_http(self.s.url("/arsiv.zip"), os.path.join(TMP, "dl", "cikis.zip"), start=False)
        it.status = "downloading"
        try:
            with mock.patch.object(self.win, "quit_app") as quit_app, \
                    mock.patch.object(G.QMessageBox, "exec", return_value=G.QMessageBox.No):
                self.win.quit_requested()
                quit_app.assert_not_called()  # "Hayır": program açık kalır
            with mock.patch.object(self.win, "quit_app") as quit_app, \
                    mock.patch.object(G.QMessageBox, "exec", return_value=G.QMessageBox.Yes):
                self.win.quit_requested()
                quit_app.assert_called_once()
        finally:
            it.status = "stopped"
            self.win.mgr.remove(it.id)

    def test_main_window_shell(self):
        win = self.win
        self.assertFalse(win.findChildren(QToolBar))  # araç çubuğu yerine yan menü ve sayfa başlığı
        # "Yeni İndirme": tıklama URL ekler, okundan bütün ekleme yolları açılır
        calls = []
        win.a_add.triggered.disconnect()  # gerçek pencere açılıp testi bekletmesin
        win.a_add.triggered.connect(lambda: calls.append(1))
        win._new_btn.click()
        self.assertEqual(calls, [1])
        win.a_add.triggered.disconnect()
        win.a_add.triggered.connect(lambda: win.add_url_prompt())
        self.assertEqual(win._new_menu_btn.menu().actions(), [win.a_add, win.a_batch, win.a_torrent, win.a_magnet])
        # kaldırılan araç çubuğundaki işlemler hâlâ ulaşılabilir
        reach = {a for b in win.findChildren(G.QToolButton) for a in b.actions()}
        reach |= {a for b in (win._new_menu_btn, win._more_btn) for a in b.menu().actions()}
        for a in (win.a_resume, win.a_stop, win.a_stop_all, win.a_delete, win.a_delete_done, win.a_options,
                  win.a_sched, win.a_qstart, win.a_qstop):
            self.assertIn(a, reach, a.text())
        # gezinme: görünümler üstte, kategoriler başlığın altında; başlık seçilemez ve sayaç hatası vermez
        tree = win.tree
        keys = [tree.topLevelItem(i).data(0, G.Qt.UserRole) for i in range(tree.topLevelItemCount())]
        self.assertEqual(keys[:5], ["all", "unfinished", "finished", "queue", None])
        self.assertTrue(all(k.startswith("cat:") for k in keys[5:]) and len(keys) > 5)
        head = tree.topLevelItem(4)
        self.assertEqual(head.text(0), "Kategoriler")
        self.assertEqual(head.flags(), G.Qt.NoItemFlags)
        win.refresh(force=True)
        # sayfa başlığı seçili görünümü ve sayıları izler
        tree.setCurrentItem(tree.topLevelItem(2))
        self.assertEqual(win.page_title.text(), "Bitmiş")
        n = len(win._visible)
        self.assertEqual(win.page_sub.text(), f"{n} indirme, 0 tanesi etkin")
        tree.setCurrentItem(tree.topLevelItem(0))
        self.assertEqual(win.page_title.text(), "Tüm İndirmeler")
        # tema değişince yeni düğmeler ve bölüm başlığı hata vermez
        G.theme.apply(APP, "light")
        G.theme.apply(APP, "dark")
        G.theme.apply(APP, "auto")
        self.assertFalse(win._more_btn.icon().isNull())

    def test_selection_box_is_visible_in_both_themes(self):
        # Seçilmemiş kutu zeminden belirgin ayrılmalı (koyu temada soluk kalıyordu); seçilince vurgu rengi dolar
        from PySide6.QtGui import QColor
        win = self.win
        it = win.mgr.add_http(self.s.url("/arsiv.zip"), os.path.join(TMP, "dl", "kutu.zip"), start=False)
        self.addCleanup(lambda: it.id in win.mgr.items and win.mgr.remove(it.id))
        win.tree.setCurrentItem(win.tree.topLevelItem(0))
        win.refresh(force=True)
        row = win._rows.index(it.id)
        win.table.clearSelection()
        try:
            for mode in ("dark", "light"):
                G.theme.apply(APP, mode)
                pump(0.1)
                rect = win.table.visualRect(win.table.model().index(row, G.SEL))
                self.assertTrue(rect.isValid())
                img = win.table.viewport().grab(rect).toImage()
                ratio = img.width() / rect.width()
                bg = QColor(img.pixel(1, 1))
                y = int(img.height() / 2)
                edge = [QColor(img.pixel(x, y)) for x in range(img.width())]
                diff = max(abs(c.lightness() - bg.lightness()) for c in edge)
                self.assertGreater(diff, 60, f"{mode}: kutu kenarı zeminden ayrılmıyor ({ratio})")
        finally:
            G.theme.apply(APP, "auto")

    def _list_items(self):
        """Dört durumda indirme; listeyi temiz başlatır."""
        win = self.win
        for iid in list(win.mgr.order):
            win.mgr.remove(iid, False)
        d = os.path.join(TMP, "liste")
        items = {}
        for name, status in (("b.bin", "completed"), ("a.bin", "stopped"), ("d.bin", "downloading"), ("c.bin", "error")):
            it = win.mgr.add_http(self.s.url("/" + name), os.path.join(d, name), start=False)
            it.status, it.size, it.done_bytes = status, 1000, 400 if status != "completed" else 1000
            it.error = "HTTP 404" if status == "error" else None
            items[status] = it
        win.tree.setCurrentItem(win.tree.topLevelItem(0))
        win.a_group.setChecked(True)
        win.mgr.settings["list_sort"] = None
        win.refresh(force=True)
        pump(0.1)

        def restore():
            items["downloading"].status = "stopped"
            win.mgr.settings["list_sort"] = None
            win._update_sort_indicator()
            win.a_group.setChecked(True)
            for iid in list(win.mgr.order):
                win.mgr.remove(iid, False)
            win.refresh(force=True)
        self.addCleanup(restore)
        return items

    def test_list_grouping_can_be_turned_off(self):
        win, t = self.win, self.win.table
        items = self._list_items()
        titles = [r[0] for r in win._rows if not isinstance(r, str)]
        self.assertEqual(titles, ["İndiriliyor", "Bekleyen", "Tamamlanan"])
        self.assertEqual(win._rows[0], ("İndiriliyor", 1))
        self.assertEqual(win._rows[1], items["downloading"].id)
        self.assertEqual(win._rows[3:5], [items["stopped"].id, items["error"].id])
        # grup satırı seçilemez; tümünü seç yalnızca indirmeleri alır, sayılar doğru kalır
        win.select_all()
        self.assertEqual(sorted(win.selected_ids()), sorted(i.id for i in items.values()))
        self.assertEqual(t.rowHeight(0), G.GROUP_HEIGHT)
        self.assertEqual(t.columnSpan(0, 0), t.columnCount())
        self.assertEqual(t.rowHeight(1), G.ROW_HEIGHT)
        self.assertEqual(win.page_sub.text(), "4 indirme, 1 tanesi etkin")
        # durum değişince indirme grubunu değiştirir, seçim korunur
        win._select_rows([win._rows.index(items["downloading"].id)])
        items["downloading"].status = "completed"
        win.refresh()
        self.assertEqual(win.selected_ids(), [items["downloading"].id])
        self.assertNotIn("İndiriliyor", [r[0] for r in win._rows if not isinstance(r, str)])
        items["downloading"].status = "downloading"
        # kapatılınca grup satırı kalmaz, ayar kaydedilir, seçim korunur
        win.a_group.setChecked(False)
        self.assertFalse(win.mgr.settings["group_list"])
        self.assertTrue(all(isinstance(r, str) for r in win._rows))
        self.assertEqual(len(win._rows), 4)
        self.assertEqual(win.selected_ids(), [items["downloading"].id])
        self.assertEqual(t.columnSpan(0, 0), 1)
        win.a_group.setChecked(True)
        self.assertTrue(win.mgr.settings["group_list"])

    def test_header_click_sorts_inside_groups(self):
        win, t = self.win, self.win.table
        items = self._list_items()
        extra = win.mgr.add_http(self.s.url("/0.bin"), os.path.join(TMP, "liste", "0.bin"), start=False)
        extra.status = "stopped"
        win.refresh(force=True)
        waiting = lambda: [win.mgr.items[r].filename for r in win._rows  # noqa: E731
                           if isinstance(r, str) and win.mgr.items[r].status in ("stopped", "error")]
        default = waiting()
        h = t.horizontalHeader()
        h.sectionClicked.emit(G.NAME)
        self.assertEqual(waiting(), sorted(default))
        self.assertEqual(win.mgr.settings["list_sort"], [G.NAME, True])
        self.assertTrue(h.isSortIndicatorShown())
        self.assertEqual(win._rows[0][0], "İndiriliyor")  # gruplar yerinde kalır
        h.sectionClicked.emit(G.NAME)
        self.assertEqual(waiting(), sorted(default, reverse=True))
        h.sectionClicked.emit(G.NAME)  # üçüncü tık: eklenme sırası
        self.assertEqual(waiting(), default)
        self.assertIsNone(win.mgr.settings["list_sort"])
        self.assertFalse(h.isSortIndicatorShown())
        # işlem sütunu sıralamaz; bozuk kayıtlı ayar yok sayılır
        h.sectionClicked.emit(G.ACTIONS)
        self.assertIsNone(win.mgr.settings["list_sort"])
        win.mgr.settings["list_sort"] = ["x", 1]
        win.refresh(force=True)
        self.assertEqual(waiting(), default)
        win.mgr.settings["list_sort"] = None
        # sıralama listeyi değiştirmez, yalnızca görünümü: kuyruk sırası korunur
        order = list(win.mgr.order)
        h.sectionClicked.emit(G.SIZE)
        self.assertEqual(win.mgr.order, order)

    def test_row_buttons_act_without_changing_selection(self):
        from PySide6.QtCore import Qt as QtC
        from PySide6.QtTest import QTest
        win, t = self.win, self.win.table
        items = self._list_items()
        pump(0.1)

        def click(it, name):
            row = win._rows.index(it.id)
            cell = t.visualRect(t.model().index(row, G.ACTIONS))
            r = G.ActionDelegate.rects(cell, t.item(row, G.ACTIONS).data(G.ACTIONS_ROLE), t.fontMetrics(),
                                       t.layoutDirection())[name]
            QTest.mouseClick(t.viewport(), QtC.LeftButton, QtC.NoModifier, r.center())
            pump(0.05)
        stopped, active, failed, done = (items[k] for k in ("stopped", "downloading", "error", "completed"))
        self.assertEqual(G.MainWindow._row_actions(active), ("pause", "more"))
        self.assertEqual(G.MainWindow._row_actions(stopped), ("play", "more"))
        self.assertEqual(G.MainWindow._row_actions(failed), ("retry", "more"))
        self.assertEqual(G.MainWindow._row_actions(done), ("folder", "more"))
        win._select_rows([win._rows.index(done.id)])
        with mock.patch.object(win.mgr, "start") as start, mock.patch.object(win.mgr, "stop") as stop, \
                mock.patch.object(win, "show_progress") as prog, mock.patch.object(G, "open_folder") as folder, \
                mock.patch.object(win, "_context_menu") as menu:
            click(stopped, "play")
            start.assert_called_once_with(stopped.id)
            prog.assert_not_called()
            click(active, "pause")
            stop.assert_called_once_with(active.id)
            click(failed, "retry")
            start.assert_called_with(failed.id)
            prog.assert_called_once_with(failed.id)
            click(done, "folder")
            folder.assert_called_once()
            self.assertEqual(win.selected_ids(), [done.id])  # düğmeler seçimi değiştirmedi
            click(stopped, "more")  # "Diğer" o satırın menüsünü açar: satır seçilir
            menu.assert_called_once()
            self.assertEqual(win.selected_ids(), [stopped.id])
            # boş alana tıklamak ve çift tıklama düğme gibi davranmaz
            start.reset_mock()
            prog.reset_mock()
            row = win._rows.index(stopped.id)
            win._double_click(t.model().index(row, G.ACTIONS))
            prog.assert_not_called()
            win._double_click(t.model().index(0, G.SEL))  # grup satırı
            prog.assert_not_called()

    def test_row_shows_type_subtitle_and_connection_bar(self):
        win, t = self.win, self.win.table
        items = self._list_items()
        stopped, active = items["stopped"], items["downloading"]
        stopped.category = "video"
        stopped.resumable = True
        stopped.segments = [[0, 499, 300], [500, 999, 600]]
        win.refresh(force=True)
        row = win._rows.index(stopped.id)
        self.assertEqual(t.item(row, G.NAME).data(G.SUB_ROLE), "Video · kaldığı yerden sürer")
        self.assertFalse(t.item(row, G.NAME).icon().isNull())
        self.assertEqual(t.item(row, G.STATUS).data(G.SEG_ROLE), (1000, [(0, 499, 300), (500, 999, 600)]))
        self.assertIn("/", t.item(row, G.STATUS).data(G.DETAIL_ROLE))
        # bilinmeyen parça yoksa ya da çok fazlaysa tek parça çizilir
        stopped.segments = [[i, i, i] for i in range(40)]
        self.assertIsNone(win._bar_segments(stopped))
        stopped.segments = [[0, 499, 300], [500, 999, 600]]
        # hatalı indirmede çubuk yok, simge ve yazı var
        row = win._rows.index(items["error"].id)
        self.assertIsNone(t.item(row, G.STATUS).data(G.PROGRESS_ROLE))
        self.assertFalse(t.item(row, G.STATUS).icon().isNull())
        # iki temada ve sağdan solda çizim hata vermez, tür simgesi ve çubuk gerçekten çizilir
        accent = lambda: G.QColor(G.theme.T["accent"]).rgb()  # noqa: E731
        try:
            for mode in ("dark", "light"):
                G.theme.apply(APP, mode)
                pump(0.05)
                row = win._rows.index(active.id)
                rect = t.visualRect(t.model().index(row, G.STATUS))
                img = t.viewport().grab(rect).toImage()
                found = any(img.pixel(x, y) == accent() for x in range(img.width()) for y in range(img.height()))
                self.assertTrue(found, f"{mode}: çubuk çizilmedi")
                row = win._rows.index(stopped.id)
                rect = t.visualRect(t.model().index(row, G.NAME))
                img = t.viewport().grab(rect).toImage()
                tile = {img.pixel(x, y) for x in range(12, 34) for y in range(img.height() // 2 - 8, img.height() // 2 + 8)}
                self.assertGreater(len(tile), 3, f"{mode}: tür simgesi çizilmedi")
            t.setLayoutDirection(G.Qt.RightToLeft)
            t.viewport().grab()
        finally:
            t.setLayoutDirection(G.Qt.LayoutDirectionAuto)
            G.theme.apply(APP, "auto")

    def _button_center(self, row, name):
        t = self.win.table
        cell = t.visualRect(t.model().index(row, G.ACTIONS))
        return G.ActionDelegate.rects(cell, t.item(row, G.ACTIONS).data(G.ACTIONS_ROLE), t.fontMetrics(),
                                      t.layoutDirection())[name].center()

    def test_row_button_never_changes_multi_selection(self):
        from PySide6.QtCore import QEvent, QPoint, QPointF, Qt as QtC
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtTest import QTest
        win, t = self.win, self.win.table
        items = self._list_items()
        a, b = items["stopped"], items["error"]
        rows = [win._rows.index(a.id), win._rows.index(b.id)]
        win._select_rows(rows)
        with mock.patch.object(win.mgr, "start"):
            QTest.mouseClick(t.viewport(), QtC.LeftButton, QtC.NoModifier, self._button_center(rows[0], "play"))
        pump(0.02)
        self.assertEqual(sorted(win.selected_ids()), sorted([a.id, b.id]))
        # tıklarken fare biraz kıpırdasa da seçim değişmez
        p = self._button_center(rows[0], "more")
        send = lambda tp, pos, btn, btns: APP.sendEvent(t.viewport(), QMouseEvent(  # noqa: E731
            tp, QPointF(pos), QPointF(t.viewport().mapToGlobal(pos)), btn, btns, QtC.NoModifier))
        with mock.patch.object(win, "_context_menu"):
            win._select_rows([rows[1]])
            send(QEvent.MouseButtonPress, p, QtC.LeftButton, QtC.LeftButton)
            send(QEvent.MouseMove, p + QPoint(2, 1), QtC.NoButton, QtC.LeftButton)
            self.assertEqual(win.selected_ids(), [b.id])
            send(QEvent.MouseButtonRelease, p + QPoint(2, 1), QtC.LeftButton, QtC.NoButton)
        # sağ tık düğmenin üstünde de o satırı seçer: menü başka indirmeye uygulanmaz
        win._select_rows([rows[1]])
        with mock.patch.object(win, "_context_menu"):
            QTest.mouseClick(t.viewport(), QtC.RightButton, QtC.NoModifier, self._button_center(rows[0], "more"))
        pump(0.02)
        self.assertEqual(win.selected_ids(), [a.id])

    def test_keyboard_skips_group_rows(self):
        from PySide6.QtCore import Qt as QtC
        from PySide6.QtTest import QTest
        win, t = self.win, self.win.table
        items = self._list_items()
        t.setFocus()
        active, stopped = win._rows.index(items["downloading"].id), win._rows.index(items["stopped"].id)
        self.assertFalse(isinstance(win._rows[active + 1], str))  # arada grup satırı var
        for col in (G.SEL, G.NAME, G.STATUS):
            t.setCurrentIndex(t.model().index(active, col))
            QTest.keyClick(t, QtC.Key_Down)
            self.assertEqual((t.currentIndex().row(), t.currentIndex().column()), (stopped, col))
            QTest.keyClick(t, QtC.Key_Up)
            self.assertEqual((t.currentIndex().row(), t.currentIndex().column()), (active, col))
        QTest.keyClick(t, QtC.Key_Up)  # en üstteki grup satırına çıkmaz
        self.assertEqual(t.currentIndex().row(), active)
        QTest.keyClick(t, QtC.Key_PageUp)
        self.assertEqual(t.currentIndex().row(), active)
        t.setCurrentIndex(t.model().index(-1, -1))  # henüz geçerli hücre yokken ilk indirmeye gider
        QTest.keyClick(t, QtC.Key_Down)
        self.assertEqual(t.currentIndex().row(), active)

    def test_rebuild_keeps_position_and_never_hits_another_row(self):
        from PySide6.QtCore import QItemSelectionModel, Qt as QtC
        from PySide6.QtTest import QTest
        win, t = self.win, self.win.table
        self._list_items()
        for i in range(30):
            it = win.mgr.add_http(self.s.url(f"/e{i}.bin"), os.path.join(TMP, "liste", f"e{i}.bin"), start=False)
            it.status = "stopped"
        win.refresh(force=True)
        pump(0.05)
        row = len(win._rows) - 3
        iid = win._rows[row]
        t.setFocus()
        t.setCurrentIndex(t.model().index(row, G.NAME))
        t.verticalScrollBar().setValue(2)
        win.refresh(force=True)
        self.assertEqual(t.currentIndex().row(), row)
        self.assertEqual(t.verticalScrollBar().value(), 2)  # geçerli satıra kaymadı
        self.assertEqual(win.selected_ids(), [iid])
        # Shift ile seçim geçerli satırdan sürer
        QTest.keyClick(t, QtC.Key_Up, QtC.ShiftModifier)
        self.assertEqual(len(win.selected_ids()), 2)
        # geçerli hücre dar pencerede ekran dışında kalsa da liste yana kaymaz
        t.selectionModel().setCurrentIndex(t.model().index(row, G.ACTIONS), QItemSelectionModel.NoUpdate)
        t.horizontalScrollBar().setValue(0)
        win.refresh(force=True)
        self.assertEqual(t.horizontalScrollBar().value(), 0)
        # basılıyken satırlar yer değiştirirse bırakınca başka indirmeye uygulanmaz
        t.clearSelection()
        t.verticalScrollBar().setValue(0)
        pump(0.05)
        row = next(r for r, i in enumerate(win._rows) if isinstance(i, str) and win.mgr.items[i].status == "stopped")
        p = self._button_center(row, "play")
        with mock.patch.object(win.mgr, "start") as start:
            QTest.mousePress(t.viewport(), QtC.LeftButton, QtC.NoModifier, p)
            win.mgr.settings["list_sort"] = [G.NAME, False]
            win.refresh()
            QTest.mouseRelease(t.viewport(), QtC.LeftButton, QtC.NoModifier, p)
            pump(0.02)
            start.assert_not_called()
        # yer değiştirmediyse tıklama çalışır
        row = next(r for r, i in enumerate(win._rows) if isinstance(i, str) and win.mgr.items[i].status == "stopped")
        p = self._button_center(row, "play")
        with mock.patch.object(win.mgr, "start") as start:
            QTest.mousePress(t.viewport(), QtC.LeftButton, QtC.NoModifier, p)
            win.refresh(force=True)
            QTest.mouseRelease(t.viewport(), QtC.LeftButton, QtC.NoModifier, p)
            pump(0.02)
            start.assert_called_once_with(win._rows[row])

    def test_real_header_click_keeps_sort_indicator(self):
        from PySide6.QtCore import QPoint, Qt as QtC
        from PySide6.QtTest import QTest
        win, h = self.win, self.win.table.horizontalHeader()
        self._list_items()

        def click(c):
            QTest.mouseClick(h.viewport(), QtC.LeftButton, QtC.NoModifier,
                             QPoint(h.sectionViewportPosition(c) + h.sectionSize(c) // 2, h.height() // 2))
        click(G.NAME)
        self.assertEqual(win.mgr.settings["list_sort"], [G.NAME, True])
        for c in (G.SEL, G.ACTIONS):  # sıralamayan sütuna tıklamak gösterge yerini değiştirmez
            click(c)
            self.assertEqual(h.sortIndicatorSection(), G.NAME)
            self.assertEqual(h.sortIndicatorOrder(), G.Qt.AscendingOrder)
        win.table.clearSelection()
        click(G.NAME)
        self.assertEqual(h.sortIndicatorOrder(), G.Qt.DescendingOrder)
        self.assertEqual(win.mgr.settings["list_sort"], [G.NAME, False])

    def test_broken_saved_values_do_not_break_the_list(self):
        win, t = self.win, self.win.table
        items = self._list_items()
        for bad in ([[1], True], [{"a": 1}, True], [1.0, True], [True, True], "x", 5, {}, [None, None], [99, 1], [1]):
            win.mgr.settings["list_sort"] = bad
            self.assertIsNone(win._sort_state(), bad)
            win.refresh(force=True)
            win._update_sort_indicator()
        win.mgr.settings["list_sort"] = None
        it = items["stopped"]
        for bad in ([1, 2], [[0, 1]], [[0, None, 3]], [["a", "b", "c"]], [None], [[0, 1, 2], "abc"], "zzz", 7,
                    [[-5, 999, 1]], [[0, 1 << 62, 5]], [[5, 1, 3]]):
            it.segments = bad
            self.assertIsNone(win._bar_segments(it), bad)
            win.refresh(force=True)
            t.viewport().grab()
        it.segments = []
        it.category = None  # eski/bozuk kayıt
        win.refresh(force=True)
        it.category = "general"

    def test_bar_draws_empty_track_for_partial_runs_and_mirrors_in_rtl(self):
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QImage, QPainter

        def draw(segs, direction=G.Qt.LeftToRight):
            img = QImage(300, 20, QImage.Format_RGB32)
            img.fill(G.QColor(255, 0, 255))
            p = QPainter(img)
            G.StatusDelegate._draw_bar(p, QRectF(50, 5, 200, 6), 0.5, segs, "#00ff00", direction)
            p.end()
            return [G.QColor(img.pixel(x, 7)) for x in range(300)]
        bg, fill = G.QColor(255, 0, 255), G.QColor(0, 255, 0)
        row = draw((100, [(0, 9, 10)]))  # HLS: yalnız biten parçalar
        self.assertEqual(row[60], fill)
        self.assertEqual(row[200], G.QColor(G.theme.T["track"]))  # kalan kısım boş çubuk, zemin değil
        self.assertEqual(row[10], bg)
        self.assertEqual(row[280], bg)
        row = draw((100, [(0, 99, 25)]), G.Qt.RightToLeft)  # sağdan sola dolar
        self.assertEqual(row[240], fill)
        self.assertEqual(row[60], G.QColor(G.theme.T["track"]))

    def test_row_button_hover_ends_when_mouse_leaves_list(self):
        from PySide6.QtCore import QEvent, QPointF, Qt as QtC
        from PySide6.QtGui import QMouseEvent
        win, t = self.win, self.win.table
        self._list_items()
        row = next(r for r, i in enumerate(win._rows) if isinstance(i, str))
        p = self._button_center(row, "more")
        APP.sendEvent(t.viewport(), QMouseEvent(QEvent.MouseMove, QPointF(p), QPointF(t.viewport().mapToGlobal(p)),
                                                QtC.NoButton, QtC.NoButton, QtC.NoModifier))
        self.assertEqual(t.action_hover, (row, "more"))
        APP.sendEvent(t.viewport(), QEvent(QEvent.Leave))
        self.assertIsNone(t.action_hover)

    def test_row_button_tooltip(self):
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QHelpEvent
        from PySide6.QtWidgets import QToolTip
        win, t = self.win, self.win.table
        self._list_items()
        row = next(r for r, i in enumerate(win._rows) if isinstance(i, str))
        p = self._button_center(row, "more")
        self.assertTrue(APP.sendEvent(t.viewport(), QHelpEvent(QEvent.ToolTip, p, t.viewport().mapToGlobal(p))))
        self.assertEqual(QToolTip.text(), "Diğer")
        QToolTip.hideText()

    def test_live_sort_does_not_reorder_on_every_tick(self):
        # Hıza göre sıralıyken satırlar her yenilemede yer değiştirmesin (fare altından kaymasın); en çok 3 sn'de bir
        win = self.win
        items = self._list_items()
        a, b = items["stopped"], items["error"]
        a.speed, b.speed = 10, 20
        win.table.horizontalHeader().sectionClicked.emit(G.SPEED)
        first = list(win._visible)
        self.assertLess(first.index(a.id), first.index(b.id))
        a.speed, b.speed = 30, 5
        win.refresh()
        self.assertEqual(win._visible, first)  # hemen değişmez
        win._live_sort = (win._live_sort[0], win._live_sort[1], time.monotonic() - 4)
        win.refresh()
        self.assertLess(win._visible.index(b.id), win._visible.index(a.id))  # süre dolunca sıralanır

    def test_extra_columns_start_hidden_once(self):
        win = self.win
        st = win.mgr.settings
        saved = (list(st["hidden_columns"]), st.get("columns_v2"))
        try:
            # önceki sürümden gelen ayar: ek sütunlar bir kez gizlenir, kullanıcının seçimi sonra korunur
            st["hidden_columns"], st["columns_v2"] = [3], False
            win._retranslate()
            self.assertEqual(st["hidden_columns"], [3, 6, 7, 8, 9])
            self.assertTrue(st["columns_v2"])
            win._set_column(8, True)
            win._retranslate()
            self.assertFalse(win.table.isColumnHidden(8))
            self.assertTrue(win.table.isColumnHidden(9))
        finally:
            st["hidden_columns"], st["columns_v2"] = saved
            win._retranslate()

    def test_shell_edge_cases(self):
        win = self.win
        st = win.mgr.settings
        saved = (list(st["hidden_columns"]), st.get("columns_v2"))
        q = None
        try:
            # açılışta ve dil değişince odak listede: Ctrl+A, Esc gibi liste kısayolları hemen çalışır
            self.assertIs(win.focusWidget(), win.table)
            # bozuk ayar programı açılışta düşürmesin
            st["hidden_columns"], st["columns_v2"] = ["x", [1], 3], False
            win._retranslate()
            self.assertEqual(st["hidden_columns"], [3, 6, 7, 8, 9])
            self.assertIs(win.focusWidget(), win.table)
            # seçili kuyruk silinince liste boş kalmaz, başlık ile içerik aynı görünümü gösterir
            q = win.mgr.add_queue("Geçici")
            win._retranslate()
            win._filter = "queue:" + q["id"]
            win._retranslate()
            self.assertEqual(win.page_title.text(), "Geçici")
            win.mgr.remove_queue(q["id"])
            win._retranslate()
            self.assertEqual(win._filter, "all")
            self.assertEqual(win.page_title.text(), "Tüm İndirmeler")
            # dönüştürülen indirme de etkin sayılır (çıkış uyarısıyla aynı)
            it = win.mgr.add_http("http://127.0.0.1:9/donusum.mp4", os.path.join(TMP, "donusum.mp4"), start=False)
            it.status = "converting"
            win.refresh(force=True)
            self.assertIn("1 tanesi etkin", win.page_sub.text())
            it.status = "stopped"
            win.mgr.remove(it.id)
        finally:
            st["hidden_columns"], st["columns_v2"] = saved
            win._retranslate()

    def test_columns_can_be_hidden_and_dates_shown(self):
        self.assertEqual(G.COLUMNS[-2:], ["Eklenme", "Bitiş"])
        self.win._set_column(6, False)  # "Son Deneme"
        self.assertTrue(self.win.table.isColumnHidden(6))
        self.assertIn(6, self.win.mgr.settings["hidden_columns"])
        self.win._set_column(6, True)
        self.assertFalse(self.win.table.isColumnHidden(6))

    def test_queues_dialog_and_tray_speed_limit(self):
        d = G.SchedulerDialog(self.win)
        with mock.patch.object(G.QInputDialog, "getText", return_value=("Gece", True)):
            d._add()
        q = [x for x in self.win.mgr.queues() if x["name"] == "Gece"]
        self.assertEqual(len(q), 1)
        with mock.patch.object(G.QMessageBox, "question", return_value=G.QMessageBox.Yes):
            d._delete()
        self.assertFalse([x for x in self.win.mgr.queues() if x["name"] == "Gece"])
        d.reject()
        s = self.win.mgr.settings
        s["speed_limit_kb"] = 500
        try:
            self.win._update_limit_action()
            self.assertTrue(self.win.a_limit.isEnabled() and self.win.a_limit.isChecked())
            self.win.a_limit.setChecked(False)  # tepsiden kapat
            self.assertFalse(s["speed_limit_enabled"])
            self.assertEqual(self.win.mgr.limiter.rate, 0)
        finally:
            s.update(speed_limit_kb=0, speed_limit_enabled=True)
            self.win.mgr.apply_settings()

    def test_smooth_progress_is_fluid_monotonic_and_honest(self):
        # gerçek değer yarım saniyede bir 50 MB'lık sıçramalarla gelir (video indirme gibi);
        # ekranda saniyede ~30 kare: sıçramadan, geri gitmeden, gerçeğin fazla önüne geçmeden ilerlemeli
        s = G.SmoothProgress()
        size, speed = 2_000_000_000, 100e6
        t, actual, prev, steps = 0.0, 0, None, []
        while t < 10:
            if int(t * 1000) % 500 < 33:
                actual = min(size, actual + 50_000_000)
            shown, _ = s.step(actual, speed, size, True, now=t)
            if prev is not None:
                self.assertGreaterEqual(shown, prev)  # geri gitmez
                steps.append(shown - prev)
            self.assertLessEqual(shown, actual + speed * s.LOOKAHEAD + 1)  # gerçeğin en fazla ~1 sn önünde
            prev = shown
            t += 0.033
        self.assertLess(max(steps) / size, 0.005)  # kare başına %0.5'ten az (eskiden %2.5'lik sıçrama)
        # duraklatınca/bitince gösterilen değer gerçek değere hemen eşitlenir, hız 0
        self.assertEqual(s.step(actual, 0, size, False, now=t), (actual, 0.0))
        # bağlantı satırları: hız verilmez, artıştan tahmin edilir; yine akıcı ve geri gitmeyen
        c = G.SmoothProgress()
        t, actual, prev, moved = 0.0, 0, None, 0
        while t < 5:
            if int(t * 1000) % 500 < 33:
                actual += 5_000_000  # bağlantı başına ~10 MB/s, yarım saniyede bir
            shown, _ = c.step(actual, None, 700_000_000, True, now=t)
            if prev is not None:
                self.assertGreaterEqual(shown, prev)
                moved += shown != prev
            prev = shown
            t += 0.033
        self.assertGreater(moved, 100)  # 150 karenin çoğunda ilerledi (yarım saniyede bir sıçrama değil)

    def test_progress_values_redraw_fast(self):
        it = self.win.mgr.add_http(self.s.url("/arsiv.zip"), os.path.join(TMP, "dl", "akici.zip"), start=False)
        try:
            d = G.ProgressDialog(self.win, it.id)
            self.assertLessEqual(d.anim.interval(), 50)  # indirme penceresi: ~30 kare/sn
            self.assertLessEqual(self.win.anim.interval(), 50)  # ana liste: ~20 kare/sn
            d.close()
        finally:
            self.win.mgr.remove(it.id, False)

    def test_unknown_size_shows_no_fake_total(self):
        # sunucu boyut bildirmeyince: yüzde yerine kayan çubuk, bağlantı satırında "/ 4194304 TB" gibi uydurma toplam yok
        it = self.win.mgr.add_http(self.s.url("/arsiv.zip"), os.path.join(TMP, "dl", "boyutsuz.zip"), start=False)
        try:
            it.size, it.status, it.done_bytes = 0, "downloading", 150 * 1024 * 1024
            it.segments = [[0, (1 << 62) - 1, it.done_bytes]]
            task = G.engine.HttpTask.__new__(G.engine.HttpTask)
            task.item, task.lock = it, threading.Lock()
            task.active, task.conn_info = {id(it.segments[0])}, {id(it.segments[0]): "Veri alınıyor (tek bağlantı)"}
            self.assertEqual(task.connections_snapshot()[0][2], 0)
            it.task = mock.Mock(connections_snapshot=task.connections_snapshot,
                                bar_data=lambda: (0, [list(s) for s in it.segments]))
            d = G.ProgressDialog(self.win, it.id)
            d.details.setVisible(True)
            d._animate()
            self.assertEqual(d.pbar.maximum(), 0)  # kayan çubuk
            self.assertNotIn("%", d.lbl["done"].text())
            self.assertNotIn("TB", d.table.item(0, 1).text())
            it.size = it.done_bytes * 2  # boyut öğrenilince yüzdeye döner
            d._animate()
            self.assertEqual(d.pbar.maximum(), 1000)
            d.close()
        finally:
            it.task, it.status = None, "stopped"
            self.win.mgr.remove(it.id, False)

    def test_tray_hint_shown_only_once(self):
        # pencere kapatılınca tepsiye iner; "arka planda çalışıyor" bildirimi yalnızca ilk sefer
        shown = []
        self.win.mgr.settings.pop("tray_hint_shown", None)
        with mock.patch.object(self.win.tray, "showMessage", lambda *a, **k: shown.append(a)):
            for _ in range(3):
                self.win.show()
                self.win.close()
                APP.processEvents()
        self.assertEqual(len(shown), 1)
        self.assertTrue(self.win.mgr.settings["tray_hint_shown"])

    def test_language_menu_switches_instantly(self):
        # menü çubuğunda sabit "Language" menüsü; seçince program kapanmadan her şey yeni dilde
        it = self.win.mgr.add_http(self.s.url("/arsiv.zip"), os.path.join(TMP, "dl", "dil.zip"), start=False)
        self.win.refresh(force=True)
        self.win.show_progress(it.id)
        try:
            titles = lambda: [a.text() for a in self.win.menuBar().actions()]  # noqa: E731
            self.assertEqual(titles()[-1], "&Language")
            lang_menu = self.win.menuBar().findChild(G.QMenu, "language")
            de = next(a for a in lang_menu.actions() if a.data() == "de")
            de.trigger()
            APP.processEvents()
            self.assertIn("&Hilfe", titles())
            self.assertEqual(titles()[-1], "&Language")
            self.assertEqual(self.win.table.horizontalHeaderItem(G.NAME).text(), "Dateiname")
            t = self.win.table  # en uzun "Tekrar Dene" çevirisi de işlem sütununa sığar
            rects = G.ActionDelegate.rects(t.visualRect(t.model().index(0, G.ACTIONS)), ("retry", "more"), t.fontMetrics(),
                                           t.layoutDirection())
            self.assertGreaterEqual(rects["retry"].left(), t.visualRect(t.model().index(0, G.ACTIONS)).left())
            self.assertEqual(self.win.mgr.settings["language"], "de")
            row = self.win._rows.index(it.id)
            self.assertEqual(self.win.table.item(row, G.STATUS).text(), G.STATUS_TEXT[it.status])
            self.assertNotEqual(G.STATUS_TEXT["queued"], "Kuyrukta")
            self.assertIn(it.id, self.win.progress_dialogs)  # açık indirme penceresi yeniden açıldı
            first = self.win.menuBar().findChild(G.QMenu, "language").actions()[0]
            self.assertEqual(first.data(), "auto")  # ilk seçenek: sistem dili (varsayılan)
            self.assertFalse(first.isChecked())
            self.win.set_language("auto")
            self.assertEqual(G.i18n.language(), G.i18n.system_language())
            self.assertEqual(self.win.mgr.settings["language"], "auto")
            self.win.set_language("ar")
            self.assertEqual(APP.layoutDirection(), G.Qt.RightToLeft)
        finally:
            self.win.set_language("tr")
            APP.processEvents()
            self.assertEqual(APP.layoutDirection(), G.Qt.LeftToRight)
            self.assertIn("&Yardım", [a.text() for a in self.win.menuBar().actions()])
            for d in list(self.win.progress_dialogs.values()):
                d.close()
            self.win.mgr.remove(it.id, False)

    def test_list_survives_restart(self):
        it = self.win.mgr.add_http(self.s.url("/arsiv.zip"), os.path.join(TMP, "dl", "kalici.zip"), start=False)
        self.win.mgr.save()
        m2 = M.Manager()
        try:
            self.assertIn(it.id, m2.items)
            self.assertEqual(m2.items[it.id].status, "queued")
        finally:
            if m2.torrents:
                m2.torrents.shutdown()


try:
    import libtorrent as lt
except ImportError:
    lt = None


@unittest.skipUnless(lt, "libtorrent yok")
class TorrentGuiTests(unittest.TestCase):
    def test_magnet_metadata_file_selection_download(self):
        seeddir = os.path.join(TMP, "seed")
        album = os.path.join(seeddir, "Album")
        os.makedirs(os.path.join(album, "CD2"), exist_ok=True)
        files = {"01.flac": os.urandom(1_500_000), "02.flac": os.urandom(1_000_000),
                 os.path.join("CD2", "big.iso"): os.urandom(2_000_000)}
        for n, d in files.items():
            open(os.path.join(album, n), "wb").write(d)
        fs = lt.file_storage()
        lt.add_files(fs, album)
        ct = lt.create_torrent(fs, 256 * 1024)
        lt.set_piece_hashes(ct, seeddir)
        ti = lt.torrent_info(lt.bencode(ct.generate()))
        port = 7100 + os.getpid() % 50
        seeder = lt.session({"listen_interfaces": f"127.0.0.1:{port}", "enable_dht": False, "enable_lsd": False,
                             "enable_upnp": False, "enable_natpmp": False,
                             "allow_multiple_connections_per_ip": True})
        p = lt.add_torrent_params()
        p.ti, p.save_path = ti, seeddir
        seeder.add_torrent(p)
        win = G.MainWindow(M.Manager())   # kendi penceresi: önceki sınıf kendi penceresini kapatmış olabilir
        win.perform_power_action = mock.Mock()
        self.addCleanup(win.quit_app)
        mgr = win.mgr
        d = G.TorrentAddDialog(win, lt.make_magnet_uri(ti) + f"&x.pe=127.0.0.1:{port}")
        d.show()
        self.assertTrue(pump(30, lambda: d.ti is not None), "meta veri gelmedi")
        names = [leaf.text(0) for leaf, _ in d.files.leaves]
        self.assertEqual(sorted(names), ["01.flac", "02.flac", "big.iso"], "dolgu dosyaları gizlenmeli")
        for leaf, _ in d.files.leaves:
            if leaf.text(0) == "02.flac":
                from PySide6.QtCore import Qt
                leaf.setCheckState(0, Qt.Unchecked)
        d._go(True)
        it = [i for i in mgr.items.values() if i.kind == "torrent"][-1]
        self.assertTrue(pump(60, lambda: it.status == "completed"), it.error)
        base = os.path.join(it.path, "Album")
        self.assertEqual(open(os.path.join(base, "01.flac"), "rb").read(), files["01.flac"])
        self.assertEqual(open(os.path.join(base, "CD2", "big.iso"), "rb").read(), files[os.path.join("CD2", "big.iso")])
        f2 = os.path.join(base, "02.flac")
        self.assertFalse(os.path.exists(f2) and open(f2, "rb").read() == files["02.flac"], "seçilmeyen dosya indi")
        seeder.pause()


if __name__ == "__main__":
    unittest.main(verbosity=2)

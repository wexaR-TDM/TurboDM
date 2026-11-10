"""Tarayıcı eklentisi ve ikinci program örneği için yerel HTTP köprüsü (yalnızca 127.0.0.1).

Web sayfalarının bu porta istek atmasını engellemek için özel `X-TurboDM` başlığı zorunludur:
bu başlık tarayıcıda CORS ön kontrolünü (preflight) tetikler ve biz ona izin vermediğimiz için
sıradan siteler istek gönderemez. Eklentiler host_permissions sayesinde CORS'tan muaftır.
"""
import json
import os
import queue
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import appinfo

requests = queue.Queue()   # GUI tarafından tick'te okunur
_extension_last_seen = None
_extension_lock = threading.Lock()


def extension_seen(max_age=150):
    """Doğrulanan eklenti son birkaç dakika içinde iletişim kurdu mu?"""
    with _extension_lock:
        return _extension_last_seen is not None and time.monotonic() - _extension_last_seen <= max_age


def _note_extension(headers):
    global _extension_last_seen
    if headers.get("X-TurboDM") != "1" or not re.fullmatch(
            r"chrome-extension://[a-p]{32}/?", headers.get("Origin") or ""):
        return
    with _extension_lock:
        _extension_last_seen = time.monotonic()

# Tarayıcı indirmelerinin sahipliği (eklenti hem mağazadan hem elle kurulmuşsa iki kopya da her indirmeyi görür):
#  * "app": indirmeyi bir kopya üstlendi; aynı adres kısa sürede yeniden gelirse ikinci pencere açılmaz
#  * "browser": TurboDM alamadı, indirme tarayıcıda (yeniden) başlatıldı; hiçbir kopya onu yakalamamalı
# Karar burada tutulur ki kopyalar birbirinin indirmesini kapıp tarayıcıda sürekli yeniden başlatmasın.
CLAIM_WINDOW = 10    # sn: aynı indirmeyi ikinci kopyanın görmesi
BROWSER_WINDOW = 60  # sn: tarayıcıya bırakılan adres bu süre boyunca yakalanmaz
_owners = {}         # adres -> (zaman, "app" | "browser")
_owners_lock = threading.Lock()


def _owner(url, take=None):
    """Adresin şimdiki sahibi (yoksa None). take verilirse ve sahibi yoksa, aynı kilit içinde sahiplenir."""
    now = time.monotonic()
    with _owners_lock:
        for u in [u for u, (t, who) in _owners.items()
                  if now - t > (BROWSER_WINDOW if who == "browser" else CLAIM_WINDOW)]:
            del _owners[u]
        hit = _owners.get(url)
        if hit is None and take:
            _owners[url] = (now, take)
        return hit[1] if hit else None


def leave_to_browser(url):
    """Bu adresin indirmesi tarayıcıya bırakıldı: kısa bir süre hiçbir eklenti kopyası onu yakalamaz."""
    if isinstance(url, str) and url:
        with _owners_lock:
            _owners[url] = (time.monotonic(), "browser")


def claim(url):
    """Eklenti, tarayıcıdaki indirmeye dokunmadan önce sorar. İlk soran kopya üstlenir (handle: True);
    ikinci kopya ya da tarayıcıya bırakılmış indirme için handle: False (indirmeye hiç dokunulmaz)."""
    who = _owner(url, take="app")
    return {"handle": True} if who is None else {"handle": False, "reason": who}

# Eklenti sürümü: Chrome/Brave/Opera'da eklenti TurboDM klasöründen elle ("paketlenmemiş") kurulur. TurboDM
# güncellenince klasördeki dosyalar yenilenir ama tarayıcı eklentiyi kendiliğinden yeniden yüklemez; eski kopya
# çalışmayı sürdürür. Eklentinin istekleri Origin başlığında kimliğini taşır (eski sürümler de), 1.7.6'dan beri
# X-TurboDM-Ext başlığında sürümünü. Mağaza kopyası mağazadan güncellendiği için uyarılmaz.
STORE_IDS = {i for i in (appinfo.EDGE_EXTENSION_ID,) if i}
_ext_warned = set()
_bundled_ext = None


def bundled_extension_version():
    """TurboDM ile gelen (kurulum klasöründeki) eklentinin sürümü; okunamazsa None."""
    global _bundled_ext
    if _bundled_ext is None:
        try:
            with open(os.path.join(appinfo.install_dir(), "browser_extension", "manifest.json"), encoding="utf-8") as f:
                _bundled_ext = str(json.load(f)["version"])
        except (OSError, ValueError, KeyError):
            _bundled_ext = ""
    return _bundled_ext or None


def _vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or ""))


def check_extension(headers):
    """Elle kurulmuş eklenti TurboDM ile gelen sürümden eskiyse GUI'ye bir kez (her eklenti kopyası için) bildirir."""
    origin = headers.get("Origin") or ""
    if not origin.startswith("chrome-extension://"):
        return
    ext_id = origin.split("://", 1)[1].strip("/")
    latest = bundled_extension_version()
    if not latest or ext_id in STORE_IDS or ext_id in _ext_warned:
        return
    have = headers.get("X-TurboDM-Ext") or ""
    if have and _vtuple(have) >= _vtuple(latest):
        return
    _ext_warned.add(ext_id)
    requests.put({"ext_outdated": {"version": have, "latest": latest}})


# Eşzamanlı yanıt veren işleyiciler (yol → fonksiyon(data) → dict). GUI başlarken doldurur.
# /formats: eklentinin sayfada kalite menüsü gösterebilmesi için video kaliteleri (yt-dlp, ~3 sn).
handlers = {}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _reply(self, code, obj):
        if code == 200:
            _note_extension(self.headers)
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _host_ok(self):
        """DNS rebinding koruması: kötü niyetli bir alan adı 127.0.0.1'e çözülse bile tarayıcı Host başlığına
        o alan adını yazar. Yalnızca gerçekten yerel adresle gelen istekler kabul edilir."""
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]").lower()
        return host in ("127.0.0.1", "localhost", "::1")

    def do_OPTIONS(self):
        self._reply(403, {"error": "forbidden"})

    def do_GET(self):
        if not self._host_ok():
            return self._reply(403, {"error": "forbidden"})
        if self.path == "/ping":
            self._reply(200, {"app": "TurboDM"})
        else:
            self._reply(404, {"error": "not found"})

    def do_POST(self):
        if self.headers.get("X-TurboDM") != "1" or not self._host_ok():
            return self._reply(403, {"error": "forbidden"})
        try:
            n = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(min(n, 1 << 20)) or b"{}")
        except ValueError:
            return self._reply(400, {"error": "bad json"})
        if not isinstance(data, dict):
            return self._reply(400, {"error": "bad json"})
        check_extension(self.headers)
        if self.path == "/ping":
            self._reply(200, {"app": "TurboDM"})
        elif self.path == "/add" and isinstance(data.get("url"), str):
            # Tarayıcının başlattığı indirme ("check"): kabul etmeden önce TurboDM dosyaya gerçekten ulaşabiliyor mu?
            # Ulaşamıyorsa (bot koruması, giriş, süresi dolmuş bağlantı…) reddedilir; eklenti indirmeyi tarayıcıda sürdürür.
            if data.get("check"):
                url = data["url"]
                if _owner(url) == "browser":  # tarayıcıya bırakılmış indirme (ör. öteki eklenti kopyası yeniden başlattı)
                    return self._reply(200, {"ok": False, "reason": "browser"})
                # /claim ile sormayan eski eklenti: aynı indirme kısa sürede ikinci kez geldiyse ikinci pencere açılmaz
                if not data.get("claimed") and _owner(url, take="app") == "app":
                    return self._reply(200, {"ok": True, "duplicate": True})
            if data.get("check") and "/check" in handlers:
                try:
                    reason = handlers["/check"](data)
                except Exception as e:  # noqa: BLE001
                    reason = str(e) or e.__class__.__name__
                if reason:
                    leave_to_browser(data["url"])
                    requests.put({"notice": reason, "url": data["url"]})
                    return self._reply(200, {"ok": False, "reason": reason})
            requests.put(data)
            self._reply(200, {"ok": True})
        elif self.path == "/claim" and isinstance(data.get("url"), str):
            self._reply(200, claim(data["url"]))
        elif self.path == "/show":
            requests.put({"show": True})
            self._reply(200, {"ok": True})
        elif self.path == "/quit":  # kurulum/kaldırma programı için
            requests.put({"quit": True})
            self._reply(200, {"ok": True})
        elif self.path in handlers:
            try:
                self._reply(200, handlers[self.path](data))
            except Exception as e:  # noqa: BLE001
                self._reply(200, {"error": str(e) or e.__class__.__name__})
        else:
            self._reply(400, {"error": "bad request"})


def start(port):
    srv = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

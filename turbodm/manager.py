"""İndirme yöneticisi: liste, kalıcılık, kuyruk, zamanlayıcı, kategoriler, hız sınırı."""
import copy
import json
import os
import re
import shutil
import threading
import time
import uuid
from datetime import datetime

from . import torrent as tmod
from .engine import ChainLimiter, HttpTask, SpeedLimiter
from .hls import HlsTask, find_ffmpeg
from . import convert, engine, power, secure, ytdlp
from . import i18n
from .i18n import _t

APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "TurboDM")
TORRENT_DIR = os.path.join(APP_DIR, "torrents")
DEFAULT_ROOT = os.path.join(os.path.expanduser("~"), "Downloads", "TurboDM")

# anahtar: (görünen ad, klasör, uzantılar)
CATEGORIES = {}


@i18n.on_change
def _texts():
    CATEGORIES.update({
    "compressed": (_t("Sıkıştırılmış"), "Compressed",
                   "zip rar 7z tar gz tgz bz2 xz iso cab arj lzh z ace".split()),
    "documents": (_t("Belgeler"), "Documents",
                  "pdf doc docx xls xlsx ppt pptx txt rtf odt ods epub csv".split()),
    "music": (_t("Müzik"), "Music", "mp3 wav flac aac ogg wma m4a opus aif aiff".split()),
    "programs": (_t("Programlar"), "Programs", "exe msi apk dmg deb rpm msix appx bat".split()),
    "video": (_t("Video"), "Video",
              "mp4 mkv avi mov wmv flv webm m4v mpg mpeg 3gp ts m2ts".split()),
    "torrent": (_t("Torrent"), "Torrent", []),
    "general": (_t("Genel"), "General", []),
    })

DEFAULT_SETTINGS = {
    "download_root": DEFAULT_ROOT,
    "connections": 8,
    "max_concurrent": 3,
    "speed_limit_kb": 0,
    "clipboard_monitor": True,
    "server_port": 9614,
    "torrent_port": 0,          # 0: ilk açılışta rastgele seçilir (6881 bazı servis sağlayıcılarda yavaşlatılır)
    "torrent_port_random": False,
    "torrent_upload_kb": 0,     # elle yükleme sınırı (0 = sınırsız ya da otomatik)
    "torrent_upload_auto": True,  # indirirken yüklemeyi otomatik sınırla: dolan yükleme hattı indirmeyi yavaşlatır
    "seed_after_complete": False,
    "show_complete_dialog": True,
    "schedule_enabled": False,
    "schedule_start": "02:00",
    "schedule_stop": "07:00",
    "ffmpeg_path": "",
    "auto_update_check": True,
    "language": "auto",         # auto (Windows dili) | tr | en | de | fr | es | ar | it
    "theme": "auto",            # auto (Windows ile aynı) | light | dark
    "last_update_check": 0,
    "update_repo": "",      # boşsa appinfo.UPDATE_REPO kullanılır
    "keep_awake": True,             # indirme sürerken bilgisayar uyku moduna geçmesin
    "speed_limit_enabled": True,    # genel hız sınırı açık mı (tepsiden açılıp kapatılır)
    "speed_limit_when_active": False,  # sınır yalnızca bilgisayar kullanılırken (boştayken tam hız)
    "auto_retry": True,             # bağlantı hatasıyla duran indirmeyi kendiliğinden yeniden başlat
    "auto_retry_count": 3,
    "auto_retry_delay": 30,         # sn
    "confirm_exit": True,           # inen dosya varken Çıkış'ta onay sor
    "proxy_mode": "system",         # system | none | manual
    "proxy_url": "",                # elle: http://sunucu:port
    "user_agent": "",               # boş: varsayılan tarayıcı kimliği
    "site_logins": [],              # [{"site", "user", "password" (DPAPI ile şifreli)}]
    "queues": [],                   # ana kuyruk dışındaki kuyruklar [{"id", "name", "max_concurrent", ...}]
    "custom_categories": [],        # [{"key": "c_…", "name", "folder", "exts": [...]}]
    "hidden_columns": [],           # listede gizlenen sütunlar
    "group_list": True,             # liste İndiriliyor / Bekleyen / Tamamlanan olarak gruplansın
    "list_sort": None,              # [sütun, artan mı]; yoksa eklenme sırası
}

IDLE_AFTER = 120  # sn: bu kadar süre klavye/fare kullanılmazsa bilgisayar "boşta" sayılır

CATCH_EXTS = set(e for k, v in CATEGORIES.items() for e in v[2])


def category_for(filename):
    """Uzantıya göre kategori. Kullanıcının tanımladığı kategoriler (c_…) önce denenir."""
    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    for key, (_, _, exts) in sorted(CATEGORIES.items(), key=lambda kv: not kv[0].startswith("c_")):
        if ext in exts:
            return key
    return "general"


def set_custom_categories(cats):
    """Seçenekler → Kategoriler: kullanıcı kategorilerini CATEGORIES'e yerleştirir (yerinde günceller)."""
    for key in [k for k in CATEGORIES if k.startswith("c_")]:
        del CATEGORIES[key]
    for c in cats or []:
        key = c.get("key") or ""
        if key.startswith("c_") and c.get("name"):
            exts = [e.lower().lstrip(".") for e in c.get("exts", []) if e.strip(" .")]
            CATEGORIES[key] = (c["name"], c.get("folder") or c["name"], exts)
    CATCH_EXTS.clear()
    CATCH_EXTS.update(e for v in CATEGORIES.values() for e in v[2])


SECRET_HEADERS = ("cookie", "authorization")


def _seal_headers(headers):
    """Diske yazılacak başlıklar: oturum çerezi ve kimlik bilgisi açık metin kalmaz (DPAPI; yalnızca aynı
    Windows kullanıcısı çözebilir). Çerez yine de saklanır: program yeniden açılınca oturum isteyen indirme
    kaldığı yerden sürebilsin."""
    return {k: secure.protect(v) if k.lower() in SECRET_HEADERS and isinstance(v, str) and v else v
            for k, v in (headers or {}).items()}


def _unseal_headers(headers):
    out = {}
    for k, v in (headers or {}).items():
        if k.lower() in SECRET_HEADERS and isinstance(v, str) and v.startswith((secure.PREFIX, "b64:")):
            v = secure.unprotect(v)
            if not v:  # başka kullanıcı/bilgisayarda çözülemedi: başlık hiç gönderilmez
                continue
        out[k] = v
    return out


def _retryable(error):
    """Otomatik yeniden denemeye değer mi? Bağlantı kopması/zaman aşımı/sunucu hatası evet;
    "bulunamadı/yasak" (HTTP 4xx, 408 ve 429 hariç), disk dolu ya da izin hatası hayır."""
    e = error or ""
    m = re.search(r"\bHTTP (\d{3})\b", e)
    if m:
        code = int(m.group(1))
        return code >= 500 or code in (408, 429)
    # motorun disk hata metinleri (engine.disk_error) seçili dilde: kalıpların sabit başlangıcıyla tanınır
    disk = (_t("Diskte yeterli boş alan yok"),
            _t("Klasöre yazılamıyor (izin yok ya da dosya kullanımda): {0}").split("{")[0],
            _t("Kayıt klasörüne ulaşılamıyor (sürücü çıkarılmış olabilir): {0}").split("{")[0],
            _t("Dosya yolu çok uzun; daha kısa bir klasör seçin"))
    return not any(d.strip(": ") and d.strip(": ") in e for d in disk)


class DownloadItem:
    FIELDS = ("id", "kind", "url", "path", "category", "size", "resumable", "segments",
              "headers", "description", "added", "last_try", "status", "error",
              "connections", "in_queue", "done_bytes", "source", "extra")

    def __init__(self, **kw):
        self.id = kw.get("id") or uuid.uuid4().hex[:12]
        self.kind = kw.get("kind", "http")          # http (http/https/ftp) | hls | torrent
        self.extra = kw.get("extra") or {}          # hls: parça durumu, torrent: dosya öncelikleri
        self.url = kw.get("url", "")
        self.path = kw.get("path", "")              # http: dosya yolu, torrent: kayıt klasörü
        self.category = kw.get("category", "general")
        self.size = kw.get("size")
        self.resumable = kw.get("resumable", True)
        self.segments = kw.get("segments") or []
        self.headers = _unseal_headers(kw.get("headers") or {})
        self.description = kw.get("description", "")
        self.added = kw.get("added") or time.time()
        self.last_try = kw.get("last_try")
        self.status = kw.get("status", "stopped")
        self.error = kw.get("error")
        self.connections = kw.get("connections", 8)
        self.in_queue = kw.get("in_queue", False)
        self.done_bytes = kw.get("done_bytes", 0)
        self.source = kw.get("source", "")          # torrent: magnet ya da .torrent kopyası
        # çalışma zamanı (kaydedilmez)
        self.task = None
        self.speed = 0.0
        self.ul_speed = 0.0
        self.peers = 0
        self.seeds = 0
        self.name = kw.get("name") or ""
        self._last_bytes = None
        self._last_t = None

    @property
    def filename(self):
        if self.kind == "torrent":
            return self.name or _t("(meta veri bekleniyor)")
        return os.path.basename(self.path)

    def to_dict(self):
        d = {k: getattr(self, k) for k in self.FIELDS}
        d["headers"] = _seal_headers(self.headers)
        d["extra"] = copy.deepcopy(self.extra)
        for k in ("cookies", "streams", "streams_t"):  # oturum çerezleri / geçici akış adresleri diske yazılmaz
            d["extra"].pop(k, None)
        d["name"] = self.name
        if self.status in ("seeding", "converting"):  # yarıda kalan dönüştürme: asıl dosya duruyor
            d["status"] = "completed"
            if self.status == "converting":
                d["in_queue"] = False
        elif self.status in ("downloading", "connecting"):
            d["status"] = "queued" if self.in_queue else "stopped"
        return d

    def eta(self):
        if not self.size or self.speed <= 1:
            return None
        return max(0, (self.size - self.done_bytes) / self.speed)


class Manager:
    def __init__(self):
        os.makedirs(TORRENT_DIR, exist_ok=True)
        # bağlantıdan alınıp dosya seçimi bekleyen geçici .torrent'ler (eklenince TORRENT_DIR'e kopyalanır)
        shutil.rmtree(os.path.join(TORRENT_DIR, "gelen"), ignore_errors=True)
        self.settings = dict(DEFAULT_SETTINGS)
        saved = self._load_json("settings.json", {})
        if saved and "tray_hint_shown" not in saved:
            saved["tray_hint_shown"] = True  # önceki sürümlerden gelen kullanıcı bu bildirimi zaten gördü
        self.settings.update(saved)
        if not self.settings["torrent_port_random"] and self.settings["torrent_port"] in (0, 6881):
            # bilinen BitTorrent portu yerine bu bilgisayara özgü rastgele bir port (bir kez seçilir)
            import random
            self.settings["torrent_port"] = random.randint(49160, 65000)
            self.settings["torrent_port_random"] = True
        set_custom_categories(self.settings.get("custom_categories"))
        self._apply_network()
        self._auto_ul = None    # otomatik yükleme sınırının son uygulanan değeri
        self._auto_ul_t = 0
        self.items = {}
        self.order = []
        self.limiter = SpeedLimiter(self.settings["speed_limit_kb"] * 1024)
        self._queue_running = {"main": False}
        self._limit_rate = None   # uygulanan genel hız sınırı (bayt/sn); boşta/açık-kapalı durumuna göre
        self._limit_t = 0
        self.events = []        # GUI'ye bildirimler: ("completed"|"error", item)
        self._last_save = 0
        self._sched_last = None
        self.torrents = None
        self.torrent_error = None
        if tmod.AVAILABLE:
            try:
                self.torrents = tmod.TorrentEngine(
                    self.settings["torrent_port"], 0, self.settings["torrent_upload_kb"] * 1024)
                self.torrents.resume_cb = self._on_resume_data
                self.torrents.error_cb = self._on_torrent_error
            except Exception as e:  # noqa: BLE001
                self.torrent_error = str(e)
        else:
            self.torrent_error = _t("libtorrent yüklü değil")
        self._apply_torrent_limits()
        for d in self._load_json("downloads.json", []):
            it = DownloadItem(**d)
            self.items[it.id] = it
            self.order.append(it.id)
            if it.kind == "torrent" and self.torrents and it.status != "completed":
                self._attach_torrent(it, paused=True)

    # ------------------------------------------------------------ kalıcılık
    def _load_json(self, name, default):
        """Kayıt bozuksa (elektrik kesintisi, disk hatası) bir önceki sağlam kopya (.bak) yüklenir;
        bozuk dosya silinmez, incelenebilsin diye kenara alınır. Liste sessizce kaybolmaz."""
        p = os.path.join(APP_DIR, name)
        for path in (p, p + ".bak"):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, type(default)):
                    return data
                raise ValueError(_t("beklenmeyen biçim"))
            except FileNotFoundError:
                continue
            except (OSError, ValueError):
                try:
                    os.replace(path, path + time.strftime(".bozuk-%Y%m%d-%H%M%S"))
                except OSError:
                    pass
        return default

    def _save_json(self, name, data):
        p = os.path.join(APP_DIR, name)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())  # elektrik kesilse bile yarım yazılmış dosya kalmasın
        if os.path.exists(p):
            try:
                os.replace(p, p + ".bak")  # bir önceki sağlam sürüm
            except OSError:
                pass
        os.replace(tmp, p)

    def save(self):
        data = []
        for i in self.order:
            it = self.items[i]
            if it.task:
                with it.task.lock:  # segment listesi tutarlı kopyalansın
                    d = it.to_dict()
                    d["segments"] = [list(s) for s in it.segments]
            else:
                d = it.to_dict()
            data.append(d)
        self._save_json("downloads.json", data)
        self._save_json("settings.json", self.settings)
        self._last_save = time.time()

    def apply_settings(self):
        set_custom_categories(self.settings.get("custom_categories"))
        self._apply_network()
        self._limit_rate = None
        self._tick_speed_limit(time.time(), force=True)
        self._apply_torrent_limits()
        self.save()

    def _apply_network(self):
        """Seçenekler → Bağlantı: vekil sunucu, tarayıcı kimliği ve site girişleri motora aktarılır."""
        from . import secure
        s = self.settings
        engine.NET.proxy_mode = s.get("proxy_mode") or "system"
        engine.NET.proxy_url = (s.get("proxy_url") or "").strip()
        engine.NET.user_agent = s.get("user_agent") or ""
        engine.NET.logins = {x["site"].strip().lower(): (x.get("user", ""), secure.unprotect(x.get("password", "")))
                             for x in s.get("site_logins", []) if x.get("site", "").strip()}

    def speed_limit_rate(self):
        """Şu an uygulanması gereken genel hız sınırı (bayt/sn, 0 = sınırsız): sınır kapalıysa ya da
        "yalnızca bilgisayar kullanılırken" seçiliyken bilgisayar boştaysa sınırsız."""
        s = self.settings
        if not s["speed_limit_kb"] or not s.get("speed_limit_enabled", True):
            return 0
        if s.get("speed_limit_when_active") and power.idle_seconds() >= IDLE_AFTER:
            return 0
        return s["speed_limit_kb"] * 1024

    def _tick_speed_limit(self, now, force=False):
        if not force and now - self._limit_t < 2:
            return
        self._limit_t = now
        rate = self.speed_limit_rate()
        if rate != self._limit_rate:
            self._limit_rate = rate
            self.limiter.set_rate(rate)
            if self.torrents:
                self.torrents.set_limits(rate, self.upload_limit())

    def _apply_torrent_limits(self):
        if self.torrents:
            self._auto_ul = None
            self.torrents.set_limits(self.speed_limit_rate(), self.upload_limit())

    AUTO_UL_MIN, AUTO_UL_MAX = 150 * 1024, 2 * 1024 * 1024

    def upload_limit(self):
        """Torrent yükleme sınırı (bayt/sn, 0 = sınırsız). Elle verilmişse o; değilse indirme sürerken
        otomatik: indirme hızının ~%8'i + 100 KB/s (150 KB/s – 2 MB/s). Yükleme hattı dolunca karşı eşlere
        giden onaylar gecikir ve indirme de yavaşlar; bu pay paylaşım (karşılıklılık) için yeterlidir.
        Yalnızca paylaşım (seed) varken sınır yoktur."""
        manual = self.settings["torrent_upload_kb"] * 1024
        if manual or not self.settings["torrent_upload_auto"]:
            return manual
        down = [i for i in self.items.values() if i.kind == "torrent" and i.status in ("downloading", "connecting")]
        if not down:
            return 0
        rate = sum(i.speed for i in down)
        return int(min(self.AUTO_UL_MAX, max(self.AUTO_UL_MIN, rate * 0.08 + 100 * 1024)))

    def _tick_upload_limit(self, now):
        if not self.torrents or now - self._auto_ul_t < 3:
            return
        self._auto_ul_t = now
        ul = self.upload_limit()
        if self._auto_ul is None or abs(ul - self._auto_ul) > max(32 * 1024, 0.1 * self._auto_ul):
            self._auto_ul = ul
            self.torrents.set_limits(self.speed_limit_rate(), ul)

    # ------------------------------------------------------------ ekleme
    def category_dir(self, cat):
        return os.path.join(self.settings["download_root"], CATEGORIES.get(cat, CATEGORIES["general"])[1])

    def unique_path(self, path):
        taken = {it.path.lower() for it in self.items.values() if it.kind != "torrent"}
        base, ext = os.path.splitext(path)
        n, p = 1, path
        while os.path.exists(p) or os.path.exists(p + ".tdm") or os.path.exists(p + ".tdm_parts") or p.lower() in taken:
            p = f"{base} ({n}){ext}"
            n += 1
        return p

    def add_http(self, url, path, category=None, headers=None, description="",
                 start=True, size=None, resumable=True):
        it = DownloadItem(kind="http", url=url, path=self.unique_path(path),
                          category=category or category_for(path), headers=headers or {},
                          description=description, size=size, resumable=resumable,
                          connections=self.settings["connections"])
        it.in_queue = not start
        it.status = "queued" if not start else "stopped"
        self._register(it)
        if start:
            self.start(it.id)
        return it

    def ffmpeg(self):
        return find_ffmpeg(self.settings.get("ffmpeg_path"))

    def add_hls(self, url, media_url, audio_url, path, headers=None, description="", start=True):
        it = DownloadItem(kind="hls", url=url, path=self.unique_path(path), category="video",
                          headers=headers or {}, description=description,
                          connections=self.settings["connections"],
                          extra={"media_url": media_url, "audio_url": audio_url, "done": [], "bytes": 0})
        it.in_queue = not start
        it.status = "queued" if not start else "stopped"
        self._register(it)
        if start:
            self.start(it.id)
        return it

    def add_ytdlp(self, url, path, choice, title="", headers=None, cookies=None, description="", start=True):
        """Site videosu (YouTube vb.). choice: ytdlp.build_choices çıktısından bir seçenek."""
        it = DownloadItem(kind="ytdlp", url=url, path=self.unique_path(path),
                          category="video" if choice.get("height") else "music",
                          headers=headers or {}, description=description or choice.get("label", ""),
                          connections=self.settings["connections"], size=choice.get("size") or None,
                          extra={"format": choice["format"], "ext": choice.get("ext", "mp4"),
                                 "title": title, "cookies": cookies or [], "size": choice.get("size") or 0,
                                 "streams": choice.get("streams"), "streams_t": time.time()})
        it.in_queue = not start
        it.status = "queued" if not start else "stopped"
        self._register(it)
        if start:
            self.start(it.id)
        return it

    def add_torrent(self, source, save_dir, start=True, description="", priorities=None, probe_key=None):
        """source: magnet ya da .torrent yolu. probe_key: dosya seçimi için meta verisi
        önceden alınmış magnet (TorrentEngine.probe_start) → aynı oturum devralınır."""
        if not self.torrents:
            raise RuntimeError(self.torrent_error or _t("Torrent desteği yok"))
        it = DownloadItem(kind="torrent", category="torrent", path=save_dir, description=description)
        if priorities:
            it.extra["priorities"] = list(priorities)
        if source.startswith("magnet:"):
            it.source = it.url = source
            if probe_key:
                dst = os.path.join(TORRENT_DIR, it.id + ".torrent")
                if self.torrents.probe_save_torrent(probe_key, dst):
                    it.source = dst  # meta veri hazır: yeniden başlatınca tekrar beklemesin
        else:
            dst = os.path.join(TORRENT_DIR, it.id + ".torrent")
            shutil.copyfile(source, dst)
            it.source = dst
            it.url = os.path.basename(source)
        if it.source.endswith(".torrent"):
            it.name = tmod.lt.torrent_info(it.source).name()
        it.in_queue = not start
        it.status = "queued" if not start else "stopped"
        if probe_key:
            self.torrents.probe_adopt(probe_key, it.id, save_dir, priorities)
        else:
            self._attach_torrent(it, paused=True)
            if it.status == "error":
                raise RuntimeError(it.error)
        self._register(it)
        if start:
            self.start(it.id)
        return it

    def set_torrent_priorities(self, iid, priorities):
        it = self.items.get(iid)
        if it and self.torrents:
            it.extra["priorities"] = list(priorities)
            self.torrents.set_priorities(iid, priorities)

    def _register(self, it):
        self.items[it.id] = it
        self.order.append(it.id)
        self.save()

    def _resume_file(self, it):
        return os.path.join(TORRENT_DIR, it.id + ".fastresume")

    def _attach_torrent(self, it, paused):
        try:
            self.torrents.add(it.id, it.source, it.path, self._resume_file(it), paused=paused,
                              priorities=it.extra.get("priorities"))
        except Exception as e:  # noqa: BLE001
            it.status, it.error = "error", str(e)

    def _on_resume_data(self, iid, data):
        it = self.items.get(iid)
        if it:
            with open(self._resume_file(it), "wb") as f:
                f.write(data)

    def _on_torrent_error(self, iid, msg):
        it = self.items.get(iid)
        if it:
            it.error = msg

    # ------------------------------------------------------------ kontrol
    def start(self, iid, auto=False):
        it = self.items.get(iid)
        if not it or it.status in ("downloading", "connecting", "seeding", "converting"):
            return
        it.retry_at = None
        if not auto:
            it.extra.pop("retry_n", None)  # elle başlatma: otomatik deneme hakkı yenilenir
        if it.status == "completed" and (it.kind != "torrent" or not self.settings["seed_after_complete"]):
            return
        it.error = None
        it.last_try = time.time()
        if it.kind in ("http", "hls", "ytdlp") and it.task is not None and getattr(it.task, "alive", False):
            # Duraklat'tan hemen sonra Devam: eski bağlantılar henüz kapanmadı. Aynı segmentlere iki görev
            # yazarsa dosyaya boşluk karışır → eski görev bitince _tick_http yeniden başlatır.
            it.task.stop()
            it.pending_start = True
            it.status = "connecting"
            return
        if it.kind in ("http", "hls", "ytdlp"):
            it.connections = self.settings["connections"]
            lim = ChainLimiter(self.limiter, self.item_limiter(it))
            if it.kind == "http":
                it.task = HttpTask(it, lim)
            elif it.kind == "hls":
                it.task = HlsTask(it, lim, self.ffmpeg())
            else:
                it.task = ytdlp.YtdlpTask(it, lim, self.ffmpeg())
            it.status = "connecting"
            it.task.start()
        else:
            if not self.torrents:
                it.status, it.error = "error", self.torrent_error
                return
            if iid not in self.torrents.handles:
                self._attach_torrent(it, paused=True)
            self.torrents.resume(iid)
            it.status = "seeding" if it.status == "completed" else "connecting"

    def item_limiter(self, it):
        """İndirmeye özel hız sınırı (IDM'deki indirme penceresi → Hız sınırlayıcı). Çalışırken değiştirilebilir."""
        if getattr(it, "limiter", None) is None:
            it.limiter = SpeedLimiter(int(it.extra.get("speed_limit_kb") or 0) * 1024)
        return it.limiter

    def set_item_limit(self, iid, kb):
        it = self.items.get(iid)
        if it:
            it.extra["speed_limit_kb"] = int(kb or 0)
            self.item_limiter(it).set_rate(int(kb or 0) * 1024)

    def stop(self, iid):
        it = self.items.get(iid)
        if not it:
            return
        if it.kind != "torrent":
            it.pending_start = False
            if it.task:
                it.task.stop()
            if it.status in ("downloading", "connecting", "queued"):
                it.status = "stopped"
        else:
            if self.torrents:
                self.torrents.pause(iid)
            it.status = "completed" if it.status in ("completed", "seeding") else "stopped"
        it.speed = 0

    def stop_all(self):
        self.queue_running = False
        for iid in self.order:
            self.stop(iid)

    def remove(self, iid, delete_file=False):
        it = self.items.pop(iid, None)
        if not it:
            return
        self.order.remove(iid)
        if it.kind != "torrent":
            files, dirs = [], []
            if delete_file:
                files.append(it.path)
            if delete_file or it.status != "completed":
                files.append(it.path + ".tdm")
                dirs.append(it.path + ".tdm_parts")
                if it.kind == "ytdlp":
                    files += ytdlp.partial_files(it.path)
                    files += [p["path"] + s for p in (it.extra.get("parts") or {}).values()
                              if p.get("path") for s in ("", ".tdm")]
            task = it.task
            if task:
                task.stop()
            # Çalışan bağlantılar dosyaları açık tutar (Windows silmeye izin vermez). Arayüzü dondurmadan,
            # bağlantılar kapanınca arka planda sil.
            threading.Thread(target=_remove_later, args=(task, files, dirs), daemon=True).start()
        else:
            if self.torrents:
                self.torrents.remove(iid, delete_file)
            _try_remove(self._resume_file(it))
            if it.source.startswith(TORRENT_DIR):
                _try_remove(it.source)
        self.save()

    # ------------------------------------------------------------ kuyruklar
    # "main" (Ana kuyruk) eski tek kuyruktur: ayarları max_concurrent / schedule_* anahtarlarındadır.
    # Diğer kuyruklar settings["queues"] içinde; indirmenin kuyruğu extra["queue"] (yoksa ana kuyruk).
    @property
    def queue_running(self):
        return self._queue_running.get("main", False)

    @queue_running.setter
    def queue_running(self, value):
        self._queue_running["main"] = bool(value)

    def queues(self):
        s = self.settings
        main = {"id": "main", "name": _t("Ana kuyruk"), "max_concurrent": s["max_concurrent"],
                "schedule_enabled": s["schedule_enabled"], "schedule_start": s["schedule_start"],
                "schedule_stop": s["schedule_stop"]}
        return [main] + [q for q in s.get("queues", []) if q.get("id") and q["id"] != "main"]

    def queue_conf(self, qid):
        return next((q for q in self.queues() if q["id"] == qid), self.queues()[0])

    def queue_of(self, it):
        qid = it.extra.get("queue") or "main"
        return qid if any(q["id"] == qid for q in self.queues()) else "main"

    def is_queue_running(self, qid="main"):
        return self._queue_running.get(qid, False)

    def add_queue(self, name):
        q = {"id": "q" + uuid.uuid4().hex[:8], "name": name.strip() or _t("Yeni kuyruk"), "max_concurrent": 2,
             "schedule_enabled": False, "schedule_start": "02:00", "schedule_stop": "07:00"}
        self.settings.setdefault("queues", []).append(q)
        self.save()
        return q

    def update_queue(self, qid, **values):
        if qid == "main":
            for k in ("max_concurrent", "schedule_enabled", "schedule_start", "schedule_stop"):
                if k in values:
                    self.settings[k] = values[k]
            return
        for q in self.settings.get("queues", []):
            if q["id"] == qid:
                q.update(values)

    def remove_queue(self, qid):
        """Kuyruğu siler; içindeki indirmeler Ana kuyruğa geçer."""
        if qid == "main":
            return
        self.stop_queue(qid)
        self.settings["queues"] = [q for q in self.settings.get("queues", []) if q["id"] != qid]
        self._queue_running.pop(qid, None)
        for it in self.items.values():
            if it.extra.get("queue") == qid:
                it.extra.pop("queue", None)
        self.save()

    def set_queue(self, iid, flag, qid="main"):
        it = self.items.get(iid)
        if it and it.status != "completed":
            it.in_queue = flag
            if flag:
                if qid == "main":
                    it.extra.pop("queue", None)
                else:
                    it.extra["queue"] = qid
            if flag and it.status == "stopped":
                it.status = "queued"
            elif not flag and it.status == "queued":
                it.status = "stopped"

    def start_queue(self, qid="main"):
        self._queue_running[qid] = True
        for it in self.items.values():
            if it.in_queue and self.queue_of(it) == qid and it.status in ("stopped", "error"):
                it.status = "queued"

    def stop_queue(self, qid="main"):
        self._queue_running[qid] = False
        for it in self.items.values():
            if it.in_queue and self.queue_of(it) == qid and it.status in ("downloading", "connecting"):
                self.stop(it.id)
                it.status = "queued"

    # ------------------------------------------------------------ liste dışa / içe aktarma
    def export_list(self, path, ids=None):
        """İndirme listesini JSON olarak kaydeder (çerez ve kimlik bilgileri yazılmaz)."""
        out = []
        for iid in self.order:
            if ids and iid not in ids:
                continue
            d = self.items[iid].to_dict()
            d["headers"] = {k: v for k, v in (d.get("headers") or {}).items()
                            if k.lower() not in ("cookie", "authorization")}
            out.append(d)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"app": "TurboDM", "version": 1, "downloads": out}, f, ensure_ascii=False, indent=1)
        return len(out)

    def import_list(self, path):
        """Dışa aktarılmış listeyi ekler; aynı adres listede varsa atlar. Eklenen sayısını döndürür."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        rows = data.get("downloads") if isinstance(data, dict) else data
        if not isinstance(rows, list):
            raise ValueError(_t("Geçerli bir TurboDM listesi değil"))
        have = {(it.url, it.source) for it in self.items.values()}
        added = 0
        for d in rows:
            if not isinstance(d, dict) or not (d.get("url") or d.get("source")):
                continue
            if (d.get("url", ""), d.get("source", "")) in have:
                continue
            d = dict(d, id=None)
            it = DownloadItem(**d)
            it.extra.pop("resume_after_restart", None)
            if it.kind == "torrent":
                if not it.source or (not it.source.startswith("magnet:") and not os.path.isfile(it.source)):
                    continue
                it.status = "completed" if it.status == "completed" else "stopped"
            elif it.status == "completed" and os.path.isfile(it.path):
                pass
            else:  # yarım parça dosyaları bu bilgisayarda yok: baştan inecek
                it.status, it.segments, it.done_bytes = "stopped", [], 0
                it.path = self.unique_path(it.path)
            it.in_queue = False
            self._register(it)
            have.add((it.url, it.source))
            added += 1
        self.save()
        return added

    # ------------------------------------------------------------ periyodik
    def tick(self):
        now = time.time()
        for it in list(self.items.values()):
            if it.status == "converting":
                self._tick_convert(it)
            elif it.kind != "torrent":
                self._tick_http(it, now)
            else:
                self._tick_torrent(it, now)
        if self.torrents:
            self.torrents.pump_alerts()
        self._tick_upload_limit(now)
        self._tick_speed_limit(now)
        self._tick_retry(now)
        self._tick_queue()
        self._tick_schedule()
        if self.settings.get("keep_awake", True):
            power.keep_awake(any(i.status in ("downloading", "connecting", "converting")
                                 for i in self.items.values()))
        else:
            power.keep_awake(False)
        if now - self._last_save > 5:
            if self.torrents:
                self.torrents.request_resume_data()
            self.save()

    def _speed(self, it, now, total):
        if it._last_bytes is None:
            it._last_bytes, it._last_t = total, now
            return
        dt = now - it._last_t
        if dt >= 0.5:
            inst = max(0, total - it._last_bytes) / dt
            it.speed = inst if it.speed == 0 else it.speed * 0.7 + inst * 0.3
            it._last_bytes, it._last_t = total, now

    def _tick_http(self, it, now):
        t = it.task
        if not t:
            return
        it.done_bytes = t.downloaded()
        if it.kind in ("hls", "ytdlp") and t.state != "completed":
            it.size = t.estimated_size() or it.size
        self._speed(it, now, it.done_bytes)
        if t.state == "downloading" and it.status == "connecting":
            it.status = "downloading"
        elif t.state == "completed":
            queued = it.in_queue
            it.status, it.task, it.speed, it.in_queue = "completed", None, 0, False
            it.extra["finished_at"] = time.time()
            it.extra.pop("retry_n", None)
            if getattr(t, "note", None):
                it.description = (it.description + " " + t.note).strip()
            it.done_bytes = it.size or it.done_bytes
            if it.extra.get("convert") in convert.FORMATS and it.extra.get("convert"):
                it.in_queue = queued  # kuyruk, dönüştürme bitmeden "bitti" sayılmaz
                self._start_convert(it)  # "tamamlandı" bildirimi dönüştürme bitince
                return
            self.events.append(("completed", it))
            self.save()
        elif t.state in ("error", "stopped") and getattr(it, "pending_start", False):
            # kullanıcı bu arada Devam dedi: eski görev artık tamamen kapandı → şimdi başlat
            it.pending_start = False
            it.task, it.speed, it.status = None, 0, "stopped"
            self.start(it.id)
        elif t.state == "error":
            it.status, it.error, it.task, it.speed = "error", t.error, None, 0
            n = it.extra.get("retry_n", 0) + 1
            s = self.settings
            if s.get("auto_retry", True) and n <= s.get("auto_retry_count", 3) and _retryable(t.error):
                # bağlantı sorunu: biraz sonra kendiliğinden yeniden dene (hata penceresi açılmaz)
                it.extra["retry_n"] = n
                it.retry_at = now + max(5, s.get("auto_retry_delay", 30))
                it.error = _t("{0} — {1} sn sonra yeniden denenecek ({2}/{3})").format(
                    t.error, int(max(5, s.get("auto_retry_delay", 30))), n, s.get("auto_retry_count", 3))
            else:
                self.events.append(("error", it))
            self.save()
        elif t.state == "stopped":
            it.task, it.speed = None, 0
            if it.status not in ("queued",):
                it.status = "stopped"

    # ------------------------------------------------------------ biçim dönüştürme (indirme bitince)
    def _start_convert(self, it):
        it.status = "converting"
        it._conv = None
        fmt, src, ff = it.extra["convert"], it.path, self.ffmpeg()

        def work():
            try:
                it._conv = (convert.convert(ff, src, fmt), None)
            except Exception as e:  # noqa: BLE001
                it._conv = (None, str(e))
        threading.Thread(target=work, daemon=True).start()

    def _tick_convert(self, it):
        res = getattr(it, "_conv", None)
        if res is None:
            return
        it._conv = None
        dst, err = res
        it.status, it.in_queue = "completed", False
        it.extra.pop("convert", None)
        if dst:
            it.path = dst
            try:
                it.size = it.done_bytes = os.path.getsize(dst)
            except OSError:
                pass
        else:
            it.description = (it.description + _t(" ({0}; asıl dosya korundu)").format(err)).strip()
        self.events.append(("completed", it))
        self.save()

    def _tick_torrent(self, it, now):
        if not self.torrents:
            return
        st = self.torrents.status(it.id)
        if not st:
            return
        it.name = st["name"] or it.name
        if st["size"]:
            it.size = st["size"]
        it.done_bytes = st["done"]
        it.speed, it.ul_speed = st["dl_rate"], st["ul_rate"]
        it.peers, it.seeds = st["peers"], st["seeds"]
        if it.status in ("stopped", "queued", "completed") and st["paused"]:
            it.speed = it.ul_speed = 0
            return
        if st["error"]:
            it.status, it.error = "error", st["error"]
            return
        if st["finished"]:
            it.error = None
            if it.status not in ("completed", "seeding"):
                it.in_queue = False
                it.extra["finished_at"] = time.time()
                self.events.append(("completed", it))
                self.torrents.request_resume_data(it.id)
                if self.settings["seed_after_complete"]:
                    it.status = "seeding"
                else:
                    self.torrents.pause(it.id)
                    it.status = "completed"
                self.save()
        elif not st["paused"]:
            it.status = "downloading" if st["state"] == "downloading" and it.speed > 0 else "connecting"
            it.error = st["state_text"] if it.status == "connecting" else None

    def _tick_retry(self, now):
        for it in list(self.items.values()):
            if it.status == "error" and getattr(it, "retry_at", None) and now >= it.retry_at:
                it.retry_at = None
                self.start(it.id, auto=True)

    def _tick_queue(self):
        for q in self.queues():
            qid = q["id"]
            if not self._queue_running.get(qid):
                continue
            mine = [self.items[i] for i in self.order if self.items[i].in_queue and self.queue_of(self.items[i]) == qid]
            active = [i for i in mine if i.status in ("downloading", "connecting")]
            free = int(q.get("max_concurrent") or 1) - len(active)
            waiting = [i for i in mine if i.status == "queued"]
            for it in waiting[:max(0, free)]:
                it.status = "stopped"
                self.start(it.id)
            # Kuyruk ancak hiçbir iş sürmüyorken biter: dönüştürülen ya da otomatik yeniden denemeyi bekleyen
            # indirme varken "bitti" denirse "Kuyruk bitince kapat/uyut" bilgisayarı yarıda kapatır
            busy = [i for i in mine if i.status == "converting" or getattr(i, "pending_start", False)
                    or (i.status == "error" and getattr(i, "retry_at", None))]
            if not waiting and not active and not busy:
                self._queue_running[qid] = False
                # Ana kuyruk bitince "Kuyruk bitince" eylemi (kapat/uyut) çalışır; diğerleri yalnızca bildirir
                self.events.append(("queue_done", None) if qid == "main"
                                   else ("info", _t("Kuyruk bitti: {0}").format(q["name"])))

    def _tick_schedule(self):
        hm = datetime.now().strftime("%H:%M")
        if hm == self._sched_last:
            return
        self._sched_last = hm
        for q in self.queues():
            if not q.get("schedule_enabled"):
                continue
            if hm == q.get("schedule_start"):
                self.start_queue(q["id"])
                self.events.append(("info", _t("Zamanlayıcı: kuyruk başlatıldı") + f" ({q['name']})"))
            elif hm == q.get("schedule_stop"):
                self.stop_queue(q["id"])
                self.events.append(("info", _t("Zamanlayıcı: kuyruk durduruldu") + f" ({q['name']})"))

    def total_speed(self):
        return sum(i.speed for i in self.items.values())

    def resume_interrupted(self):
        """Güncelleme için kapatılmadan önce inmekte olan indirmeleri yeniden başlat (--resume)."""
        for iid in list(self.order):
            it = self.items[iid]
            if it.extra.pop("resume_after_restart", False):
                self.start(iid)

    def active_count(self):
        return sum(1 for i in self.items.values() if i.status in ("downloading", "connecting", "converting"))

    def shutdown(self):
        power.keep_awake(False)
        for it in self.items.values():
            # kapanırken inmekte olanlar işaretlenir: güncelleme sonrası --resume ile kaldığı yerden sürer
            if it.status in ("downloading", "connecting"):
                it.extra["resume_after_restart"] = True
            else:
                it.extra.pop("resume_after_restart", None)
            if it.task:
                try:  # bir görevin hatası kaydı ve kapanışı engellemesin
                    it.task.stop()
                except Exception:  # noqa: BLE001
                    pass
        if self.torrents:
            self.torrents.request_resume_data()
            time.sleep(0.5)
            self.torrents.pump_alerts()
            self.torrents.shutdown()
        # bağlantıların son baytları yazması için kısa bekleme
        time.sleep(0.3)
        self.save()


def _remove_later(task, files, dirs):
    if task is not None and hasattr(task, "join"):
        task.join(60)
    for _ in range(10):  # antivirüs/dizinleyici anlık kilit tutabilir
        for p in files:
            _try_remove(p)
        for d in dirs:
            shutil.rmtree(d, ignore_errors=True)
        if not any(os.path.exists(p) for p in files + dirs):
            return
        time.sleep(1)


def _try_remove(p):
    try:
        if p and os.path.isfile(p):
            os.remove(p)
    except OSError:
        pass

"""Uygulama kimliği ve kurulum konumu (geliştirme ortamı ya da kurulu .exe)."""
import os
import sys

APP_NAME = "TurboDM"
VERSION = "1.8.1"   # build.ps1 kurulum dosyasının sürümünü buradan alır

# Güncellemelerin yayımlandığı GitHub deposu ("kullanıcı/depo"). Boşsa "Güncellemeleri denetle"
# sunucunun ayarlanmadığını söyler. Program şu adresi okur:
#   https://github.com/<UPDATE_REPO>/releases/latest/download/latest.json
UPDATE_REPO = "wexaR-TDM/TurboDM"
# Deponun eski adı (2026-10-15'te yeniden adlandırıldı; GitHub eski adresi kalıcı olarak yönlendirir).
# 1.5.7 sürümü güncellemeyi yalnızca eski adresten kabul ettiği için latest.json'daki indirme adresi bu
# adla yazılır. Bu hesapta aynı adla yeni bir depo AÇILMAMALIDIR (yönlendirme bozulur).
LEGACY_REPO = "wexaR-TDM/Turbo-Download-Manager-TDM-"

# Edge Add-ons mağazasındaki eklentinin kimliği (CRX ID). Mağaza onaylayınca doldurulur: kurulum programı
# Edge'e eklentiyi önerir. Onaydan önce boş kalmalı (yayımlanmamış kimlik Edge'de hata verir).
# 2026-10-26'da yayımlandı: https://microsoftedge.microsoft.com/addons/detail/dpeakjonbfgodlhkbpeekljfgnpbbjai
EDGE_EXTENSION_ID = "dpeakjonbfgodlhkbpeekljfgnpbbjai"
APP_USER_MODEL_ID = "TurboDM.DownloadManager"
MUTEX_NAME = "TurboDM_SingleInstance_Mutex"

FROZEN = getattr(sys, "frozen", False)


def install_dir():
    """Kurulu sürümde TurboDM.exe'nin klasörü, geliştirmede proje kökü."""
    if FROZEN:
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def bundled_ffmpeg():
    base = install_dir()
    for p in (os.path.join(base, "ffmpeg", "ffmpeg.exe"),
              os.path.join(base, "vendor", "ffmpeg", "ffmpeg.exe")):
        if os.path.isfile(p):
            return p
    return None

// TurboDM tarayıcı köprüsü:
//  1) Tarayıcının başlattığı indirmeleri yakalayıp masaüstü uygulamasına gönderir.
//  2) Video yakalayıcı: sayfaların yüklediği video/ses akışlarını (mp4, webm, m3u8…) izler,
//     sekme başına listeler; içerik betiği videonun üstüne "Bu videoyu indir" düğmesi koyar.
const API = "http://127.0.0.1:9614";
let enabled = true;
let grabber = true;
chrome.storage.local.get({ enabled: true, grabber: true }, (v) => {
  enabled = v.enabled;
  grabber = v.grabber;
  appUp();  // tarayıcının indirme penceresi buna göre açılır/kapanır (syncUi)
});
chrome.storage.onChanged.addListener((c) => {
  if (c.enabled) enabled = c.enabled.newValue;
  if (c.grabber) grabber = c.grabber.newValue;
  if (c.enabled) syncUi();
});

// Tarayıcının kendi indirme penceresi: indirmeler TurboDM'e gidiyorsa kapalıdır (indirme önce tarayıcıda
// belirip sonra kaybolmasın). Yakalama kapalıysa ya da TurboDM'e ulaşılamıyorsa açıktır.
let appSeen = false;
let uiForced = 0;  // tarayıcıda (yeniden) başlatılan indirme görünsün diye pencere kısa süre açık tutulur
function syncUi() {
  const on = !(enabled && appSeen) || Date.now() < uiForced;
  try { Promise.resolve(chrome.downloads.setUiOptions({ enabled: on })).catch(() => {}); } catch {}
}

const M = (key) => chrome.i18n.getMessage(key) || key;  // _locales/<dil>/messages.json

async function cookiesFor(url) {
  try {
    const list = await chrome.cookies.getAll({ url });
    return list.map((c) => `${c.name}=${c.value}`).join("; ");
  } catch {
    return "";
  }
}

// Sayfa videoları için yapılandırılmış çerezler (o sayfanın çerezleri; giriş gerektiren videolar için).
// Eklenti siteleri tanımaz: sayfa adresini çerezleriyle TurboDM'e verir, videoyu çözmek uygulamanın işidir.
async function structuredCookies(url) {
  try {
    const list = await chrome.cookies.getAll({ url });
    return list.map((c) => ({ name: c.name, value: c.value, domain: c.domain, path: c.path,
                              secure: c.secure, expirationDate: c.expirationDate || 0 }));
  } catch {
    return [];
  }
}

const formatCache = new Map(); // sayfa adresi -> {t, data}

async function getFormats(url) {
  const hit = formatCache.get(url);
  if (hit && Date.now() - hit.t < 10 * 60 * 1000) return hit.data;
  const body = { url, cookies: await structuredCookies(url) };
  const r = await postToApp("/formats", body);
  const data = await r.json();
  if (!data.error) formatCache.set(url, { t: Date.now(), data });
  return data;
}

// page: true → bir sayfanın videosu (adres + çerezler; kalite TurboDM'de çözülür)
// TurboDM kapalıysa tarayıcı onu açtırır (native messaging: TurboDM'in kurulumda kaydettiği yardımcı) ve
// açılmasını bekler. Kayıt yoksa (eski sürüm, başka bilgisayar) sessizce vazgeçilir: indirme tarayıcıda kalır.
const NATIVE_HOST = "com.turbodm.app";
// TurboDM'e giden her istekte eklentinin sürümü: elle kurulan eklenti TurboDM güncellenince tarayıcıda kendiliğinden
// yenilenmez; TurboDM eski kopyayı bu başlıktan tanıyıp kullanıcıya "eklentiyi yenileyin" der
const HEADERS = { "Content-Type": "application/json", "X-TurboDM": "1",
                  "X-TurboDM-Ext": chrome.runtime.getManifest().version };

// Kalp atışı yalnızca yoklar; uygulamayı açtırmaz ve indirme yakalamaya dokunmaz.
const HEARTBEAT = "turbodm-heartbeat";
let heartbeatPending = null;
function heartbeat() {
  if (!heartbeatPending) {
    heartbeatPending = fetch(API + "/ping", {
      method: "POST", headers: HEADERS, body: "{}", signal: AbortSignal.timeout(5000),
    }).catch(() => {}).finally(() => { heartbeatPending = null; });
  }
  return heartbeatPending;
}
function ensureHeartbeat() {
  chrome.alarms.get(HEARTBEAT).then((alarm) => {
    if (!alarm) return chrome.alarms.create(HEARTBEAT, { periodInMinutes: 1 });
  }).catch(() => {});
}
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === HEARTBEAT) heartbeat();
});
chrome.runtime.onStartup.addListener(() => { ensureHeartbeat(); heartbeat(); });
ensureHeartbeat();
heartbeat();

function setAppSeen(up) {
  if (up !== appSeen) {
    appSeen = up;
    syncUi();
  }
}

async function appUp() {
  let up = false;
  try { up = (await fetch(API + "/ping")).ok; } catch {}
  setAppSeen(up);
  return up;
}

// Tarayıcıdaki indirmeye dokunmadan önce TurboDM'e sorulur: eklenti iki kez kuruluysa (mağaza + elle) yalnızca
// biri üstlenir; TurboDM'in tarayıcıya bıraktığı indirmeye hiçbir kopya dokunmaz.
// null: TurboDM'e ulaşılamadı · {handle:true}: bu kopya üstlenir · {handle:false}: dokunma
async function claimFor(url) {
  let r;
  try {
    r = await fetch(API + "/claim", { method: "POST",
      headers: HEADERS, body: JSON.stringify({ url }) });
  } catch {
    setAppSeen(false);
    return null;
  }
  setAppSeen(true);
  if (!r.ok) return { handle: true, legacy: true };  // /claim'i bilmeyen eski TurboDM
  try { return await r.json(); } catch { return { handle: true, legacy: true }; }
}

async function wakeApp() {
  try {
    const r = await chrome.runtime.sendNativeMessage(NATIVE_HOST, { cmd: "launch" });
    if (!r || !r.ok) return false;
  } catch { return false; }
  for (let i = 0; i < 48; i++) {  // en fazla ~12 sn
    await new Promise((res) => setTimeout(res, 250));
    if (await appUp()) return true;
  }
  return false;
}

// İsteği TurboDM'e gönderir; ulaşılamazsa bir kez açtırıp yeniden dener
async function postToApp(path, body) {
  const send = () => fetch(API + path, {
    method: "POST",
    headers: HEADERS,
    body: JSON.stringify(body),
  });
  try {
    return await send();
  } catch (e) {
    if (await wakeApp()) return await send();
    throw e;
  }
}

async function sendToApp(info, page = false) {
  if (page) info = { ...info, cookies: await structuredCookies(info.url) };
  const body = { ...info, cookie: info.cookies ? "" : await cookiesFor(info.url), userAgent: navigator.userAgent };
  const r = await postToApp("/add", body);
  if (!r.ok) return false;
  try {
    return (await r.json()).ok !== false;  // TurboDM dosyaya ulaşamıyorsa reddeder (ör. bot koruması)
  } catch { return true; }
}

// ------------------------------------------------------------------ indirme yakalama
// Tarayıcı bir indirme başlattığında: duraklat → uygulamaya gönder → başarılıysa iptal et.
// Uygulama kapalıysa indirme tarayıcıda normal şekilde devam eder.
// .torrent dosyaları tarayıcıda inmeye bırakılır (birçok site dosyayı yalnızca tarayıcıdaki indirme
// düğmesine verir, TurboDM aynı adresi isteyince indirme sayfasını alır); inince TurboDM'de açılır.
const torrentDownloads = new Set();

function isTorrentName(s) {
  return /\.torrent$/i.test((s || "").split(/[?#]/)[0]);
}

function isTorrent(item) {
  return item.mime === "application/x-bittorrent" || isTorrentName(item.finalUrl || item.url)
    || isTorrentName(item.filename);
}

chrome.downloads.onChanged.addListener(async (d) => {
  if (!d.state || d.state.current !== "complete") return;
  torrentDownloads.delete(d.id);
  if (!enabled) return;
  try {
    const [item] = await chrome.downloads.search({ id: d.id });
    // servis çalışanı yeniden başlamış olabilir (küme boşalır): bu yüzden inen dosyanın adına bakılır
    if (!item || !isTorrentName(item.filename)) return;
    await fetch(API + "/add", {
      method: "POST",
      headers: HEADERS,
      body: JSON.stringify({ url: item.finalUrl || item.url, torrent_file: item.filename }),
    });
  } catch {}
});

// Form gönderimiyle (POST) başlayan indirmeler (ör. "Altyazıyı indir" gibi düğmeler): sunucu dosyayı yalnızca
// formdaki verilerle verir. TurboDM aynı adresi verisiz isterse dosya yerine hata/sayfa alır (ör. "ind" adlı
// anlamsız dosya). Bu indirmeler tarayıcıda bırakılır; tarayıcı doğru yanıtı zaten almıştır.
const postedUrls = new Map();  // adres -> zaman
chrome.webRequest.onBeforeRequest.addListener(
  (d) => {
    if (d.method !== "POST") return;
    const now = Date.now();
    postedUrls.set(d.url, now);
    for (const [u, t] of postedUrls) if (now - t > 120000) postedUrls.delete(u);
  },
  { urls: ["<all_urls>"], types: ["main_frame", "sub_frame"] }
);

// Dosyanın kendisi formun yanıtı mı? Form gönderildikten sonra başka bir adrese yönlendirildiyse (ör. doğrulama
// kodlu indirme sayfası → imzalı depolama bağlantısı) son adres düz bir indirmedir: TurboDM indirebilir.
function wasPosted(item) {
  return postedUrls.has(item.finalUrl || item.url);
}

// TurboDM'in alamadığı indirmeyi tarayıcıda (yeniden) başlatır. Bu indirme yeniden yakalanmaz.
const browserOwned = new Set();
async function backToBrowser(url) {
  browserOwned.add(url);
  uiForced = Date.now() + 4000;  // tarayıcının indirme penceresi bu indirmeyi göstersin
  syncUi();
  try {
    await chrome.downloads.download({ url });
  } catch {
    browserOwned.delete(url);
  }
  setTimeout(syncUi, 4500);
}

// Devralınan indirmeler: TurboDM'de hiç başlayamazsa (ör. sunucu bağlantıyı yalnızca bir kez verir, 403)
// tarayıcıya geri verilir. Pencere açıkken kullanıcı düşünebilir: en fazla 15 dk izlenir.
const HANDOFF_MAX = 15 * 60 * 1000;
// TurboDM devir sırasında kapanır ya da çökerse bu süre sonra açtırılır; açılamazsa indirme tarayıcıya geri verilir
const HANDOFF_DOWN = 30 * 1000;
const handoffs = new Map();  // kimlik -> {url, t}
let watching = false;
const saveHandoffs = () => chrome.storage.session.set({ handoffs: [...handoffs] }).catch(() => {});

async function watchHandoffs() {
  if (watching) return;
  watching = true;
  try {
    while (handoffs.size) {
      await new Promise((res) => setTimeout(res, 1500));
      for (const [id, h] of [...handoffs]) {
        if (Date.now() - h.t > HANDOFF_MAX) { handoffs.delete(id); continue; }
        let st;
        try {
          // t: devrin zamanı. TurboDM bu arada yeniden başladıysa ve devri hiç kaydetmediyse "failed" der
          const r = await fetch(API + "/handoff", { method: "POST",
            headers: HEADERS, body: JSON.stringify({ id, t: h.t }) });
          st = (await r.json()).state;
          h.down = 0;
        } catch {
          // TurboDM yanıt vermiyor (kapandı ya da çöktü): indirme kaybolmasın. Önce TurboDM açtırılır (indirmeyi
          // kaydettiyse kendisi sürdürür); açılamazsa indirme tarayıcıda yeniden başlatılır
          if (!h.down) { h.down = Date.now(); continue; }
          if (Date.now() - h.down < HANDOFF_DOWN) continue;
          if (!h.woke) {
            h.woke = true;
            if (await wakeApp()) continue;
          }
          handoffs.delete(id);
          await backToBrowser(h.url);
          continue;
        }
        if (st === "pending") continue;
        handoffs.delete(id);
        if (st === "failed") {
          // önce TurboDM'e bildirilir (adres tarayıcıya bırakılmış sayılır), sonra tarayıcıda başlatılır
          try {
            await fetch(API + "/handoff", { method: "POST", headers: HEADERS,
                                            body: JSON.stringify({ id, returned: true, url: h.url }) });
          } catch {}
          await backToBrowser(h.url);
        }
      }
      await saveHandoffs();  // eklenti API çağrısı: izleme sürerken servis çalışanı kapanmaz
    }
  } finally {
    watching = false;
  }
}
// servis çalışanı yeniden başladıysa yarım kalan izleme sürdürülür
chrome.storage.session.get({ handoffs: [] }).then((v) => {
  for (const [id, h] of v.handoffs || []) handoffs.set(id, h);
  if (handoffs.size) watchHandoffs();
}).catch(() => {});

chrome.downloads.onCreated.addListener(async (item) => {
  if (!enabled) return;
  const url = item.finalUrl || item.url;
  if (!/^(https?|ftp):/i.test(url)) return;
  if (browserOwned.delete(url) || browserOwned.delete(item.url)) return;  // tarayıcıya geri verilen indirme
  if (isTorrent(item)) {
    torrentDownloads.add(item.id);
    return;
  }
  if (wasPosted(item)) return;  // form verisiyle istenen dosya: tarayıcı indirsin
  const name = (item.filename || "").split(/[\\/]/).pop();
  const id = crypto.randomUUID();
  // check: TurboDM kabul etmeden önce dosyaya ulaşabildiğini denetler; handoff: indirme TurboDM'de başlayamazsa
  // tarayıcıya geri verilebilsin diye izlenir
  const info = { url, referrer: item.referrer || "", filename: name, mime: item.mime || "", check: true, handoff: id };
  const claim = await claimFor(url);
  if (claim && !claim.handle) return;  // öteki eklenti kopyası üstlendi ya da indirme tarayıcıya bırakılmış
  if (claim && !claim.legacy) info.claimed = true;
  if (claim) {
    // TurboDM açık: tarayıcıdaki indirme hemen iptal edilir (bir an bile tarayıcıda durmasın);
    // TurboDM alamazsa aynı adres tarayıcıda yeniden başlatılır
    try { await chrome.downloads.cancel(item.id); } catch {}
    try { await chrome.downloads.erase({ id: item.id }); } catch {}
    let ok = false;
    try { ok = await sendToApp(info); } catch {}
    if (ok) {
      handoffs.set(id, { url, t: Date.now() });
      saveHandoffs();
      watchHandoffs();
    } else {
      await backToBrowser(url);
    }
    return;
  }
  // TurboDM kapalı: indirme duraklatılır, TurboDM açtırılır (native messaging); açılamazsa tarayıcıda sürer
  try { await chrome.downloads.pause(item.id); } catch {}
  try {
    if (await sendToApp(info)) {
      await chrome.downloads.cancel(item.id);
      await chrome.downloads.erase({ id: item.id });
      handoffs.set(id, { url, t: Date.now() });
      saveHandoffs();
      watchHandoffs();
      return;
    }
  } catch {}
  try { await chrome.downloads.resume(item.id); } catch {}
});

// ------------------------------------------------------------------ video yakalayıcı
const media = new Map(); // tabId -> [{url, kind, type, size, label}]
const MEDIA_EXT = /\.(m3u8|mp4|webm|mkv|flv|mov|m4v|mp3|m4a|aac|ogg|opus|wav)(\?|#|$)/i;
const SKIP_EXT = /\.(ts|m4s|aac\?.*range|key|vtt|srt)(\?|#|$)/i; // tek tek akış parçalarını listeleme
const HLS_TYPES = ["application/vnd.apple.mpegurl", "application/x-mpegurl", "audio/mpegurl", "audio/x-mpegurl"];
const DASH_TYPES = ["application/dash+xml"];
// Oynatıcı çoğu zaman başka bir siteden gömülü (iframe) gelir; video sunucusu isteğin o oynatıcı sayfasından
// geldiğini denetleyebilir. Her çerçevenin adresi tutulur, indirme o adresle (Referer/Origin) istenir.
const frameUrls = new Map(); // "sekme:çerçeve" -> adres

function forgetTab(tabId) {
  for (const k of frameUrls.keys()) if (k.startsWith(tabId + ":")) frameUrls.delete(k);
}

function originOf(url) {
  try { return new URL(url).origin; } catch { return ""; }
}

function header(headers, name) {
  const h = (headers || []).find((x) => x.name.toLowerCase() === name);
  return h ? h.value : "";
}

function classify(url, ctype, size) {
  const t = (ctype || "").split(";")[0].trim().toLowerCase();
  const path = url.split("?")[0].toLowerCase();
  if (HLS_TYPES.includes(t) || path.endsWith(".m3u8")) return "hls";
  if (DASH_TYPES.includes(t) || path.endsWith(".mpd")) return "dash";
  if (SKIP_EXT.test(path)) return null;
  if (t.startsWith("video/") || t.startsWith("audio/") || MEDIA_EXT.test(path)) {
    if (size && size < 200 * 1024) return null; // küçük reklam/önizleme dosyaları
    return t.startsWith("audio/") || /\.(mp3|m4a|aac|ogg|opus|wav)$/.test(path) ? "audio" : "video";
  }
  return null;
}

function fmtSize(n) {
  if (!n) return "";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return n.toFixed(i ? 1 : 0) + " " + u[i];
}

function addMedia(tabId, entry) {
  if (tabId < 0) return;
  const list = media.get(tabId) || [];
  // aynı kaynağın farklı Range istekleri tek kayıt olsun
  const key = entry.url.replace(/([?&])(range|bytestart|byteend)=[^&]*/gi, "$1");
  if (list.some((m) => m.key === key)) return;
  // HLS ana listesi içindeki alt listeleri ayrı göstermeye gerek yok: ilk m3u8 yeterli
  if (entry.kind === "hls" && list.some((m) => m.kind === "hls" && /master|playlist|index/i.test(m.url))
      && !/master|playlist|index/i.test(entry.url)) return;
  entry.key = key;
  list.push(entry);
  media.set(tabId, list);
  // sekme bu arada kapanmış olabilir (ya da arka planda önceden yüklenen, henüz sekme olmayan bir sayfa):
  // rozet konamazsa sessizce geç, "No tab with id" hatası eklentiler sayfasına düşmesin
  chrome.action.setBadgeBackgroundColor({ tabId, color: "#1e6fd9" }).catch(() => {});
  chrome.action.setBadgeText({ tabId, text: String(list.length) }).catch(() => {});
  chrome.tabs.sendMessage(tabId, { type: "tdm-media", count: list.length }).catch(() => {});
}

chrome.webRequest.onHeadersReceived.addListener(
  (d) => {
    if (!grabber || d.tabId < 0 || d.statusCode >= 400) return;
    if (d.url.startsWith(API)) return;
    // adres içinde bayt aralığı taşıyan istekler bir akışın parçasıdır, tek başına indirilemez
    // (bu tür oynatıcılarda video, sayfa düğmesinin kalite menüsüyle indirilir)
    if (/[?&](range|bytes)=/i.test(d.url)) return;
    const ctype = header(d.responseHeaders, "content-type");
    let size = parseInt(header(d.responseHeaders, "content-length"), 10) || 0;
    const cr = header(d.responseHeaders, "content-range").match(/\/(\d+)/);
    if (cr) size = parseInt(cr[1], 10);
    const kind = classify(d.url, ctype, size);
    if (!kind) return;
    const label = M(kind === "hls" ? "labelHls" : kind === "dash" ? "labelDash"
      : kind === "audio" ? "labelAudio" : "labelVideo")
      + (size ? " · " + fmtSize(size) : "")
      + " · " + (ctype.split(";")[0] || d.url.split("?")[0].split(".").pop());
    const referrer = frameUrls.get(d.tabId + ":" + d.frameId) || d.initiator || "";
    addMedia(d.tabId, { url: d.url, kind, size, label, referrer });
  },
  { urls: ["<all_urls>"], types: ["media", "xmlhttprequest", "other", "object"] },
  ["responseHeaders"]
);

chrome.tabs.onUpdated.addListener((tabId, info) => {
  if (info.url) { // yeni sayfaya gidildi → listeyi sıfırla
    media.delete(tabId);
    forgetTab(tabId);
    chrome.action.setBadgeText({ tabId, text: "" }).catch(() => {});
  }
});
chrome.tabs.onRemoved.addListener((tabId) => { media.delete(tabId); forgetTab(tabId); });

function safeName(title, kind, url) {
  let ext = ".mp4";
  if (kind === "audio") ext = "." + ((url.split("?")[0].match(/\.(mp3|m4a|aac|ogg|opus|wav)$/i) || [0, "mp3"])[1]);
  else {
    const m = url.split("?")[0].match(/\.(mp4|webm|mkv|flv|mov|m4v)$/i);
    if (m) ext = "." + m[1];
  }
  const base = (title || "video").replace(/[\\/:*?"<>|]+/g, " ").replace(/\s+/g, " ").trim().slice(0, 120);
  return (base || "video") + ext;
}

chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  const tabId = msg.tabId ?? (sender.tab ? sender.tab.id : -1);
  if (msg.type === "tdm-frame") {
    if (sender.tab && typeof msg.url === "string") frameUrls.set(sender.tab.id + ":" + (sender.frameId || 0), msg.url);
  } else if (msg.type === "tdm-list") {
    reply(media.get(tabId) || []);
  } else if (msg.type === "tdm-element-src") {
    // <video src="..."> doğrudan bağlantıysa (blob: değilse) onu da listeye ekle
    addMedia(tabId, { url: msg.url, kind: "video", size: 0, label: M("labelPagePlayer") });
  } else if (msg.type === "tdm-formats") {
    // Sayfadaki kalite menüsü için: TurboDM yt-dlp ile kaliteleri listeler (~3 sn; sonuç 10 dk önbellekte)
    getFormats(msg.url).then(reply).catch((e) => reply({ error: e.message || M("appDown") }));
    return true;
  } else if (msg.type === "tdm-page") {
    // Sayfa videosu. msg.choice varsa (menüden seçilen kalite) TurboDM soru sormadan indirmeye başlar;
    // yoksa kalite seçim penceresi açılır.
    sendToApp({ url: msg.url, referrer: msg.url, filename: safeName(msg.title, "video", ""),
                title: msg.title || "", choice: msg.choice || undefined }, true)
      .then((ok) => reply({ ok })).catch(() => reply({ ok: false }));
    return true;
  } else if (msg.type === "tdm-download") {
    const m = msg.media;
    const referrer = m.referrer || msg.pageUrl || "";  // akışı isteyen oynatıcının (çerçevenin) adresi
    sendToApp({
      url: m.url,
      referrer,
      origin: originOf(referrer),
      filename: safeName(msg.title, m.kind, m.url),
    }).then((ok) => reply({ ok })).catch(() => reply({ ok: false }));
    return true; // async yanıt
  }
});

// ------------------------------------------------------------------ sağ tık menüsü
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "turbodm-link",
    title: M("ctxDownload"),
    contexts: ["link", "image", "video", "audio"],
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  const url = info.linkUrl || info.srcUrl;
  if (!url || url.startsWith("blob:")) return;
  try {
    await sendToApp({ url, referrer: info.pageUrl || (tab && tab.url) || "" });
  } catch {
    console.warn(M("appDown"));
  }
});

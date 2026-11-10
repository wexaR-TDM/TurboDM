// background.js'i sahte tarayıcı ortamında çalıştırır: form (POST) indirmesi, normal indirme, TurboDM kapalı,
// TurboDM'in reddettiği ve TurboDM'de başlayamayıp tarayıcıya geri verilen indirmeleri dener.
// TurboDM'in yanıt vermediği süre testte kısaltılır (gerçekte 30 sn)
const src = Deno.readTextFileSync(Deno.args[0]).replace("const HANDOFF_DOWN = 30 * 1000", "const HANDOFF_DOWN = 2000");
const listeners = {};
const ev = (name) => ({ addListener: (fn) => { (listeners[name] ||= []).push(fn); } });
const calls = { fetch: [], pause: [], cancel: [], native: [], resume: [], erase: [], download: [], ui: [], bodies: [] };
let appOnline = true;  // TurboDM açık mı (kapalıyken fetch bağlantı hatası verir)
let nativeOk = true;   // tarayıcı TurboDM'i açtırabiliyor mu (yardımcı kayıtlı değilse hayır)
let nextId = 100;
const handoffState = {};  // devir kimliği -> TurboDM'in /handoff yanıtı (yoksa "ok")
const session = {};
globalThis.chrome = {
  storage: { local: { get: (d, cb) => cb(d) }, onChanged: ev("storage"),
             session: { get: async (d) => ({ ...d, ...session }), set: async (v) => Object.assign(session, v) } },
  runtime: { onMessage: ev("msg"), onInstalled: ev("installed"), onStartup: ev("startup"), getManifest: () => ({ version: "x" }),
             // tarayıcının TurboDM yardımcısını çalıştırması: TurboDM açılır
             sendNativeMessage: async (host, msg) => { calls.native.push([host, msg.cmd]);
                                                       if (!nativeOk) return { ok: false };
                                                       appOnline = true; return { ok: true, launched: true }; } },
  i18n: { getMessage: (k) => k },
  contextMenus: { create() {}, onClicked: ev("ctx") },
  tabs: { onUpdated: ev("tabUpd"), onRemoved: ev("tabRem"), sendMessage: () => Promise.resolve() },
  action: { setBadgeText: () => Promise.resolve(), setBadgeBackgroundColor: () => Promise.resolve() },
  cookies: { getAll: async () => [] },
  alarms: { get: async () => undefined, create: async () => {}, onAlarm: ev("alarm") },
  webRequest: { onBeforeRequest: ev("beforeRequest"), onHeadersReceived: ev("headers"),
                onBeforeSendHeaders: ev("sendHeaders"), onSendHeaders: ev("sendHeaders2") },
  downloads: {
    onCreated: ev("created"), onChanged: ev("changed"), onDeterminingFilename: ev("filename"),
    pause: async (id) => calls.pause.push(id), resume: async (id) => calls.resume.push(id),
    cancel: async (id) => calls.cancel.push(id), erase: async (q) => calls.erase.push(q.id), search: async () => [],
    setUiOptions: async (o) => calls.ui.push(o.enabled),
    // tarayıcıda yeniden başlatılan indirme: gerçek tarayıcı gibi onCreated tetiklenir
    download: async (o) => { const id = nextId++; calls.download.push(o.url);
                             setTimeout(() => fire("created", { id, url: o.url, finalUrl: o.url, filename: "", mime: "" }), 0);
                             return id; },
  },
};
// Sahte TurboDM köprüsü (turbodm/server.py'deki sahiplik kurallarıyla aynı): ilk soran kopya üstlenir,
// TurboDM'in alamadığı ya da geri verdiği adres "browser" olur ve hiçbir kopya onu yakalamaz.
const owners = {};  // adres -> "app" | "browser"
const reply = (obj) => ({ ok: true, status: 200, json: async () => obj });
globalThis.fetch = async (url, opt) => {
  if (!appOnline) throw new TypeError("Failed to fetch");
  calls.fetch.push(url);
  const body = opt && opt.body ? String(opt.body) : "";
  if (body) calls.bodies.push(body);
  const b = body ? JSON.parse(body) : {};
  if (String(url).endsWith("/claim")) {
    if (owners[b.url]) return reply({ handle: false, reason: owners[b.url] });
    owners[b.url] = "app";
    return reply({ handle: true });
  }
  if (String(url).endsWith("/handoff")) {
    if (b.returned) owners[b.url] = "browser";
    return reply({ state: b.returned ? "returned" : (handoffState[b.id] || "ok") });
  }
  if (String(url).endsWith("/add") && b.check) {
    if (owners[b.url] === "browser") return reply({ ok: false, reason: "browser" });
    if (!b.claimed) { if (owners[b.url] === "app") return reply({ ok: true, duplicate: true }); owners[b.url] = "app"; }
    // TurboDM dosyaya ulaşamıyor (ör. Cloudflare): köprü {ok:false} döner, adres tarayıcıya bırakılır
    if (b.url.includes("korumali")) { owners[b.url] = "browser"; return reply({ ok: false, reason: "bot koruması" }); }
  }
  return reply({ ok: true });
};
new Function(src)();

const fire = async (name, arg) => { for (const fn of listeners[name] || []) await fn(arg); };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const added = () => calls.fetch.filter((u) => String(u).endsWith("/add")).length;
const result = {};
await sleep(50);

// 1) Altyazı sitesi: form POST ile /ind isteği, ardından aynı adresten indirme başlar
await fire("beforeRequest", { method: "POST", url: "https://turkcealtyazi.org/ind", type: "main_frame", tabId: 1 });
await fire("created", { id: 1, url: "https://turkcealtyazi.org/ind", finalUrl: "https://turkcealtyazi.org/ind", filename: "", mime: "" });
result.form_post = { turbodm_e_gitti: added() > 0, duraklatildi: calls.pause.includes(1) };

// 2) Normal indirme (GET): TurboDM'e gitmeli; TurboDM açık olduğundan tarayıcıdaki indirme hemen iptal edilir
//    (duraklatılıp beklenmez) ve tarayıcının indirme penceresi kapalıdır (indirme bir an bile görünmesin)
calls.fetch.length = 0;
await fire("beforeRequest", { method: "GET", url: "https://example.com/dosya.zip", type: "main_frame", tabId: 1 });
await fire("created", { id: 2, url: "https://example.com/dosya.zip", finalUrl: "https://example.com/dosya.zip", filename: "dosya.zip", mime: "application/zip" });
result.normal_get = { turbodm_e_gitti: added() > 0, tarayicida_iptal: calls.cancel.includes(2),
                      duraklatilmadi: !calls.pause.includes(2), pencere_kapali: calls.ui.at(-1) === false };

// 3) TurboDM kapalı: eklenti onu açtırır (native messaging), açılınca indirmeyi aktarır
calls.fetch.length = 0;
appOnline = false;
await fire("created", { id: 3, url: "https://example.com/buyuk.iso", finalUrl: "https://example.com/buyuk.iso", filename: "buyuk.iso", mime: "" });
result.app_closed = { acildi: calls.native.length === 1 && calls.native[0][1] === "launch",
                      turbodm_e_gitti: added() > 0, tarayicida_iptal: calls.cancel.includes(3) };

// 5) Form + yönlendirme (metin2.download): doğrulama kodlu form /get/… adresine gider, site imzalı depolama
//    bağlantısına yönlendirir. Son adres düz bir indirme: TurboDM'e verilmeli (son adresle)
calls.fetch.length = 0;
calls.bodies.length = 0;
await fire("beforeRequest", { method: "POST", url: "https://site.example/get/TOKEN/", type: "main_frame", tabId: 1 });
await fire("created", { id: 5, url: "https://site.example/get/TOKEN/", finalUrl: "https://depo.example/files/TOKEN.zip?X-Amz-Signature=abc",
                        filename: "Paket.zip", mime: "application/zip" });
result.post_redirect = { turbodm_e_gitti: added() > 0,
                         son_adresle: calls.bodies.some((b) => b.includes("depo.example/files/TOKEN.zip")),
                         tarayicida_iptal: calls.cancel.includes(5) };

// 4) TurboDM dosyaya ulaşamıyor (bot koruması): indirme tarayıcıda yeniden başlatılır ve bu kez yakalanmaz;
//    tarayıcının indirme penceresi bu indirmeyi göstermek için açılır
calls.fetch.length = 0;
calls.ui.length = 0;
await fire("created", { id: 4, url: "https://korumali-site.example/dosya.zip", finalUrl: "https://korumali-site.example/dosya.zip", filename: "dosya.zip", mime: "application/zip" });
await sleep(50);
result.refused = { turbodm_e_soruldu: added() === 1,
                   tarayicida_yeniden: calls.download.includes("https://korumali-site.example/dosya.zip"),
                   yeniden_yakalanmadi: added() === 1, pencere_acildi: calls.ui.includes(true) };

// 6) TurboDM kabul etti ama indirme hiç başlayamadı (sunucu 403): eklenti bunu öğrenip indirmeyi tarayıcıda
//    yeniden başlatır ve TurboDM'e bildirir (TurboDM başarısız kaydı kaldırır)
calls.fetch.length = 0;
calls.bodies.length = 0;
calls.download.length = 0;
const realUUID = crypto.randomUUID.bind(crypto);
crypto.randomUUID = () => "devir-403";
handoffState["devir-403"] = "pending";
await fire("created", { id: 6, url: "https://depo.example/tek-kullanimlik.bin", finalUrl: "https://depo.example/tek-kullanimlik.bin", filename: "a.bin", mime: "" });
await sleep(1700);
const beklerken = calls.download.length;  // TurboDM henüz karar vermedi: tarayıcıda başlatılmaz
handoffState["devir-403"] = "failed";
await sleep(1700);
crypto.randomUUID = realUUID;
result.handoff_failed = { beklerken_baslatilmadi: beklerken === 0,
                          tarayicida_yeniden: calls.download.includes("https://depo.example/tek-kullanimlik.bin"),
                          turbodm_e_bildirildi: calls.bodies.some((b) => b.includes('"returned":true')),
                          yeniden_yakalanmadi: added() === 1 };

// 7) Eklenti iki kez kurulu (mağaza + elle): ikinci kopya aynı tarayıcıya yüklenir, iki kopya da her indirmeyi görür
new Function(src)();
await sleep(50);
calls.fetch.length = 0;
calls.cancel.length = 0;
await fire("created", { id: 7, url: "https://example.com/iki-kopya.zip", finalUrl: "https://example.com/iki-kopya.zip", filename: "a.zip", mime: "" });
await sleep(100);
result.two_copies = { turbodm_e_bir_kez: added() === 1, tarayicida_iptal: calls.cancel.includes(7) };

// 8) İki kopya + TurboDM dosyayı alamıyor: indirme tarayıcıda bir kez yeniden başlar ve orada kalır
//    (kopyalar birbirinin yeniden başlattığı indirmeyi kapıp döngüye girmez)
calls.fetch.length = 0;
calls.download.length = 0;
await fire("created", { id: 8, url: "https://korumali-iki.example/dosya.zip", finalUrl: "https://korumali-iki.example/dosya.zip", filename: "dosya.zip", mime: "" });
await sleep(400);
result.two_copies_refused = { tarayicida_bir_kez: calls.download.length === 1, turbodm_e_bir_kez: added() === 1 };

// 9) TurboDM devraldıktan sonra, indirme başlamadan çöktü: eklenti bir süre sonra TurboDM'i açtırır; yeniden açılan
//    TurboDM devri kaydetmemişse "failed" der ve indirme tarayıcıda yeniden başlatılır (kaybolmaz)
calls.fetch.length = 0;
calls.download.length = 0;
calls.native.length = 0;
crypto.randomUUID = () => "devir-cokme";
handoffState["devir-cokme"] = "pending";
await fire("created", { id: 9, url: "https://depo.example/cokme.bin", finalUrl: "https://depo.example/cokme.bin", filename: "c.bin", mime: "" });
await sleep(1700);
appOnline = false;                      // çöktü
handoffState["devir-cokme"] = "failed";  // yeniden açılan TurboDM devri tanımıyor
await sleep(1700);
const cokunce = calls.download.length;   // hemen tarayıcıya verilmez (TurboDM belki kendine gelir)
await sleep(5000);
crypto.randomUUID = realUUID;
result.app_crashed = { hemen_verilmedi: cokunce === 0, acildi: calls.native.length > 0,
                       tarayicida_yeniden: calls.download.includes("https://depo.example/cokme.bin") };

// 10) TurboDM çöktü ve açtırılamıyor (yardımcı kayıtlı değil): indirme yine tarayıcıda yeniden başlatılır
calls.download.length = 0;
crypto.randomUUID = () => "devir-cokme-2";
handoffState["devir-cokme-2"] = "pending";
appOnline = true;
await fire("created", { id: 10, url: "https://depo.example/cokme2.bin", finalUrl: "https://depo.example/cokme2.bin", filename: "d.bin", mime: "" });
await sleep(1700);
appOnline = false;
nativeOk = false;
await sleep(6000);
crypto.randomUUID = realUUID;
result.app_crashed_no_launch = { tarayicida_yeniden: calls.download.includes("https://depo.example/cokme2.bin") };
// sorulan her devirde zaman bilgisi gönderilir (yeniden başlayan TurboDM için)
result.handoff_has_time = calls.bodies.filter((b) => b.includes('"id":"devir-')).every((b) => b.includes('"t":') || b.includes('"returned":true'));

console.log(JSON.stringify(result, null, 1));
Deno.exit(0);

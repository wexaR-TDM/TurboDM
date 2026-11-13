# TurboDM sürüm notları

Her sürümde nelerin değiştiği, en yeni sürüm en üstte. Son sürümü indirmek için:
**[github.com/wexaR-TDM/TurboDM/releases/latest](https://github.com/wexaR-TDM/TurboDM/releases/latest)**
Kurulu TurboDM'i güncellemek için: *Yardım → Güncellemeleri denetle*. · [English release notes](RELEASE_NOTES.md)

<!-- Geliştirici notu: her yeni sürümde en üste "## x.y.z" bölümü eklenir (İngilizcesi RELEASE_NOTES.md'ye). "Güncellemeleri denetle"
     penceresinde o sürümün bölümü gösterilir (build.ps1 otomatik olarak latest.json'a koyar). -->

## 1.8.1
• Daha sade görünüm: pencerelerde kutu içinde kutu yok, ayarlar ve bilgiler düz liste hâlinde; düğmeler sade, yalnızca ana eylem mavi
• İndirme listesi: dosya adının altında tek satır (boyut · durum), hız ve kalan süre tek sütunda; satır düğmeleri fare üzerine gelince ya da satır seçiliyken görünür. Boyut ve Kalan Süre sütunlarını isterseniz sütun başlığına sağ tıklayarak geri açabilirsiniz
• Hız paneli ince bir şerit oldu: toplam hız, küçük hız grafiği, etkin indirme sayısı ve kalan süre. Kuyruğu başlatma/durdurma ve zamanlayıcı "Diğer" menüsünde
• İndirme penceresi kısaldı: tek satırlık özet; bağlantı ayrıntıları "Ayrıntıları göster" ile açılır
• Yeni İndirme penceresi kısaldı: kategori, açıklama, kuyruğa ekleme ve kimlik bilgisi "Diğer seçenekler" altında. Enter indirmeyi başlatır

## 1.8.0
• Yenilenen Seçenekler penceresi: solda Genel, Bağlantı, Video, Torrent ve Kategoriler menüsü; ayarlar başlıklı gruplar hâlinde, onay kutuları yerine açma/kapama anahtarları, tema için Sistem / Açık / Koyu seçimi
• Yenilenen indirme penceresi: büyük yüzde ve hız, indirilen, kalan süre, bağlantı sayısı ve devam ettirilebilirlik kartları, açılır bağlantı tablosu
• Hız sınırlayıcı: tek tıkla hazır değerler (512 KB/s, 1 MB/s, 5 MB/s, 10 MB/s), KB/s ya da MB/s seçimi
• "Bitince yapılacaklar" artık tek seçim: Hiçbir şey yapma, TurboDM'den çık, Uyku moduna geç ya da Bilgisayarı kapat. Önceden birden fazla seçenek işaretliyse en güçlüsü korunur (kapat, sonra uyku, sonra çık)
• Yenilenen Yeni İndirme penceresi: dosya bilgisi kartı (boyut, devam ettirilebilir mi), kategori, kaydedilecek yer, açıklama ve açılır kimlik bilgisi bölümü
• Diğer pencereler (toplu indirme, torrent, zamanlayıcı, sağlama, güncelleme) de aynı görünüme kavuştu

## 1.7.32
• Yenilenen uygulama simgesi: tanıdık mavi daire ve ok daha temiz çizildi; okun altındaki çizgi artık parçalı (TurboDM dosyayı parçalara bölerek indirir). Masaüstü, görev çubuğu, kurulum sihirbazı ve tarayıcı eklentisinde aynı simge

## 1.7.31
• Arama kutusu: sayfa başlığındaki kutuya yazarak listeyi dosya adına göre süzün (Ctrl+F ile açılır, Esc ile temizlenir)
• Hız paneli: toplam hız, son 60 saniyenin hız grafiği, etkin indirme sayısı, kalan süre ve kuyruğu başlatıp durdurma, zamanlayıcı. İstemezseniz "Diğer" menüsünden kapatabilirsiniz
• Durum çubuğu: tarayıcı eklentisinin TurboDM'e bağlı olup olmadığı, indirme klasöründeki boş alan, toplam indirme hızı ve sürüm
• Listede sade sayılar (ör. 337 / 512 MB), boş hız ve süre hücrelerinde "–", bitenlerde ne zaman bittiği (ör. bugün 14:32), duraklatılan indirmede klasörü aç düğmesi; yenilenen simgeler ve başlıkta tümünü seç kutusu
• Dar pencerede başlık ve düğmeler kaybolmuyor: önce arama kutusu ve düğme yazıları küçülür, gerekirse Hız ve Kalan Süre sütunları geçici olarak gizlenir
• Ağ sürücüsündeki indirme klasörünün boş alanı okunurken pencere artık donmuyor
(tarayıcı eklentisi 1.7.8: TurboDM'e dakikada bir "buradayım" der, böylece bağlantı durumu gösterilebilir)

## 1.7.30
• Yenilenen indirme listesi: her indirme iki satırda; dosya türü simgesi, kalın dosya adı, altında kategori ve bağlantı sayısı. Durum sütununda her bağlantıyı ayrı gösteren parçalı ilerleme çubuğu
• Satır düğmeleri: durdur, devam et, klasörü aç, Tekrar Dene ve daha fazla işlem için ⋯ doğrudan satırda
• Liste İndiriliyor, Bekleyen ve Tamamlanan olarak gruplara ayrılır. İstemezseniz "Diğer" menüsünden ya da sütun başlığına sağ tıklayarak kapatabilirsiniz
• Sütun başlığına tıklayarak sıralama: gruplar açıkken her grup kendi içinde sıralanır, seçiminiz hatırlanır
• Pencere ilk açılışta daha geniş (1280x720) açılır

## 1.7.29
• Yenilenen ana pencere: üstteki araç çubuğu yerine solda "Yeni İndirme" düğmesi (okundan toplu indirme, torrent ve magnet) ve sade bir yan menü; sağda seçili görünümün başlığı, indirme sayısı ve işlem düğmeleri. Bitenleri Sil, kuyruk ve zamanlayıcı işlemleri "Diğer" menüsünde; açık ve koyu tema renkleri de yenilendi
• Son Deneme, Açıklama, Eklenme ve Bitiş sütunları artık başta kapalı, dosya adına daha çok yer kalıyor. Sütun başlığına sağ tıklayarak açabilirsiniz (seçim korunur)
• Düzeltme: seçili kuyruk silinince liste boş kalıyordu; artık Tüm İndirmeler gösteriliyor

## 1.7.28
• Düzeltme: tarayıcı indirmeyi TurboDM'e devrettikten hemen sonra, indirme başlamadan TurboDM kapanır ya da çökerse indirme kaybolabiliyordu. Artık eklenti TurboDM'i yeniden açtırıyor; TurboDM indirmeyi kaydetmişse kaldığı yerden sürdürüyor, kaydetmemişse ya da açılamıyorsa indirme tarayıcıda yeniden başlatılıyor (tarayıcı eklentisi 1.7.7)
• Eski sürümlerin kurulum dosyaları artık GitHub'dan silinmiyor (winget gibi paket yöneticilerinin bağlantıları bozulmasın)

## 1.7.27
• Chrome, Brave ve Opera'da elle kurulan tarayıcı eklentisini tarayıcı, TurboDM güncellense de kendiliğinden yenilemiyor; eski eklenti çalışmayı sürdürüyordu (ör. video düğmesi taşınamıyordu). Artık TurboDM eski eklentiyi fark ediyor ve nasıl yenileneceğini söylüyor: eklentiler sayfasında TurboDM kartındaki yenile (↻) düğmesi. Edge mağazasından kurulan eklenti mağazadan güncellendiği için uyarı çıkmaz (tarayıcı eklentisi 1.7.6)

## 1.7.26
• Düzeltme: duraklatılan bir indirmenin dosyası sunucuda değişirse (yeni sürüm yüklenmesi gibi) eski ve yeni dosyanın parçaları birleşip bozuk bir dosya "tamamlandı" görünebiliyordu. Artık değişiklik fark ediliyor ve dosya baştan indiriliyor; sunucunun yanlış yerden gönderdiği parçalar da dosyaya yazılmıyor
• Güvenlik: bir indirme başka bir siteye yönlendirildiğinde (ör. dosya barındırma sunucusu) tarayıcıdan gelen oturum çerezi artık oraya gönderilmiyor; tarayıcı da göndermez
• Güvenlik: oturum isteyen indirmelerin çerezleri indirme listesinde artık Windows şifrelemesiyle saklanıyor (yalnızca aynı Windows kullanıcısı çözebilir)
• Düzeltme: "Kuyruk bitince bilgisayarı kapat/uyut" seçiliyken, otomatik yeniden denemeyi bekleyen ya da biçimi dönüştürülen bir indirme varken kuyruk bitmiş sayılıp bilgisayar kapatılabiliyordu
• Düzeltme: indirme sürerken klasörde aynı adla başka bir dosya oluşursa, indirme bitince o dosyanın üzerine yazılıyordu. Artık o dosya korunuyor, indirilen dosya "ad (1)" olarak kaydediliyor

## 1.7.25
• Düzeltme: bazı sitelerde (ör. Twitch, Kick) site oynatıcıyı yeniden yükleyince eski videonun "Bu videoyu indir" düğmesi ekranda kalıyor, birden çok düğme görünüyor ve kalan düğme × ile kapanmıyordu. Artık ekranda tek düğme var: en büyük görünen videoda
• Video düğmesi sürüklenerek videonun istenen yerine taşınabiliyor; seçilen yer hatırlanıyor
• Canlı yayınlarda video düğmesi artık çıkmıyor (TurboDM canlı yayın indirmiyor)
(tarayıcı eklentisi 1.7.5)

## 1.7.24
• Tarayıcı eklentisi artık Microsoft Edge Eklentileri mağazasında: TurboDM kurulunca Edge eklentiyi kendisi önerir, güncellemeler mağazadan gelir (https://microsoftedge.microsoft.com/addons/detail/dpeakjonbfgodlhkbpeekljfgnpbbjai)
• Eklenti iki kez kuruluysa (mağazadan ve elle) indirme artık TurboDM'e iki kez gelmiyor; TurboDM'in alamayıp tarayıcıya bıraktığı indirmeyi iki kopya birbirinden kapıp sürekli yeniden başlatmıyor (tarayıcı eklentisi 1.7.4)
• Eklenti kurulum rehberi mağaza bağlantısıyla güncellendi

## 1.7.23
• Düzeltme: video sitesi bağlantısı (ör. elle yapıştırılan bir video adresi) eklenirken video incelenirken ya da video bulunamadığında "İndirmeyi Başlat"a basılırsa video yerine sitenin web sayfası iniyordu. Artık düğmeler video bulunana kadar kapalı; bulunamazsa nedeni yazıyor
• Tarayıcı eklentisi kurulum rehberi güncellendi

## 1.7.22
• İndirme artık önce tarayıcıda belirip duraklatılmıyor: TurboDM açıkken tarayıcının indirme paneli açılmaz, tarayıcıdaki indirme beklemeden iptal edilir ve dosya doğrudan TurboDM'e geçer
• Düzeltme: TurboDM'in devraldığı indirme hiç başlayamazsa (ör. sunucu bağlantıyı yalnızca bir kez verip "HTTP 403" döndürürse) indirme kaybolmuyor; tarayıcıda yeniden başlatılıyor ve TurboDM nedenini bildiriyor. TurboDM'in hiç alamadığı dosyalar (bot koruması vb.) da tarayıcının indirme panelinde görünüyor
(tarayıcı eklentisi 1.7.3)

## 1.7.21
• Düzeltme: sunucu dosya boyutunu bildirmediğinde (ör. iCloud'dan ZIP olarak indirilen fotoğraflar) ayrıntılarda "151 MB / 4194304 TB" gibi anlamsız bir toplam görünüyor, yüzde %0'da kalıyordu. Artık yalnızca indirilen miktar gösteriliyor, ilerleme çubuğu boyut belli olana kadar kayan çubuk olarak çalışıyor

## 1.7.20
• Düzeltme: doğrulama kodlu indirme sayfaları (ör. metin2.download) artık TurboDM'e geliyor. Bu sitelerde "İndir" düğmesi bir form gönderir, site de dosyanın asıl bağlantısına yönlendirir; eklenti bu tür indirmeleri yanlışlıkla tarayıcıda bırakıyordu. Dosya doğrudan formun yanıtıysa (ör. altyazı siteleri) yine tarayıcıda iner (tarayıcı eklentisi 1.7.2)

## 1.7.19
• Düzeltme: TurboDM tarayıcının indirmesini devralmadan önce dosyaya gerçekten ulaşabildiğini denetler. Cloudflare gibi bot korumalı sitelerde (ör. metin2.download) koruma TurboDM'i engellediğinde indirme artık iptal edilip kaybolmaz, tarayıcıda sürer; TurboDM nedenini bildirir. Giriş ya da doğrulama sayfası dönen bağlantılar için de aynısı geçerli (tarayıcı eklentisi 1.7.1)

## 1.7.18
• Toplu indirme ekleme (Görevler → Toplu indirme ekle…, Ctrl+Shift+N): bağlantı listesini ya da içinde bağlantı geçen herhangi bir metni yapıştırın; dosya adları ve boyutları denetlenir, işaretlenenler hemen başlar ya da seçilen kuyruğa eklenir
• Dosya doğrulama: biten indirmede sağ tık → Dosyayı doğrula; MD5 / SHA-1 / SHA-256 hesaplanır, sitenin verdiği değerle karşılaştırılır
• İndirme sürerken bilgisayar uyku moduna geçmez (Seçenekler → Genel'den kapatılabilir)
• Bağlantı sorunuyla (kopma, zaman aşımı, sunucu hatası) duran indirme kendiliğinden yeniden denenir; "bulunamadı" ya da disk hatalarında denenmez
• Çıkışta onay: inmekte olan dosya varken Çıkış'a basılınca sorulur
• Seçenekler → Bağlantı: vekil sunucu (proxy), özel tarayıcı kimliği (User-Agent), site girişleri (kullanıcı adı/parola; parolalar Windows'un şifrelemesiyle saklanır)
• Birden çok kuyruk: Zamanlayıcı penceresinden yeni kuyruk eklenir, her kuyruğun ayrı aynı-anda-indirme sayısı ve başlama/durma saati olur; sağ tık → Kuyruğa ekle
• Kendi kategorileriniz (Seçenekler → Kategoriler): belirttiğiniz uzantılar kendi klasörüne iner
• Listeyi dışa/içe aktarma (Görevler menüsü); sütun başlığına sağ tıkla sütunları gizleme; yeni "Eklenme" ve "Bitiş" sütunları; seçili indirmelerin toplam boyutu
• Tepsi menüsünden hız sınırını tek tıkla açma/kapama; istenirse sınır yalnızca bilgisayar kullanılırken uygulanır
• Tarayıcı eklentisi 1.7.0: TurboDM kapalıysa eklenti onu kendisi açar ve indirmeyi aktarır

## 1.7.17
• Tarayıcı eklentisi 1.6.4: form düğmesiyle (ör. altyazı sitelerindeki "Altyazıyı indir") başlayan indirmeler artık tarayıcıda iner. Bu dosyaları sunucu yalnızca formdaki bilgilerle verdiği için TurboDM'e aktarılınca "ind" gibi anlamsız bir dosya iniyordu

## 1.7.16
• Tarayıcı eklentisi 1.6.3: "Bu videoyu indir" düğmesi film izlerken göze batmıyor. Fare 3 saniye kıpırdamazsa oynatıcının kendi denetimleri gibi solar, fare oynayınca geri gelir
• Düğmenin yanındaki × ile düğme o sayfada gizlenir; sayfa yenilenince (F5) ya da başka bir videoya geçilince yeniden görünür

## 1.7.15
• Tarayıcı eklentisi 1.6.2: eklenti güncellenince ya da yeniden yüklenince açık sekmelerde eklentiler sayfasına düşen "Extension context invalidated" hata kaydı giderildi; eski kopya düğmelerini kaldırıp sessizce durur (sayfa yenilenince yeni sürüm çalışır)

## 1.7.14
• Tarayıcı eklentisi 1.6.1: sayfada video varsa eklenti penceresinde de "Video kaliteleri" listelenir; bir kaliteye tıklayınca TurboDM'in kayıt penceresi o kalite seçili açılır (videonun üstündeki menüyle aynı)

## 1.7.13
• Tarayıcı eklentisi 1.6.0: yeni TurboDM teması. Eklenti penceresi ve videonun üstündeki kalite menüsü programla aynı renklerde, tarayıcının açık/koyu moduna kendiliğinden uyar; açma/kapama anahtarları, TurboDM'in çalışıp çalışmadığını gösteren durum etiketi
• Eklenti penceresindeki "Bu sayfadaki medyalar" bölümü yalnızca sayfada indirilebilir bir akış bulunduğunda görünür (boş "Yok. Videoyu oynatmayı deneyin." yazısı kaldırıldı)

## 1.7.12
• Akıcı gösterim ayrıntılarda da: indirme penceresindeki bağlantı çubuğu ve bağlantı listesindeki "İndirilen" miktarları artık sıçramadan, yumuşak ilerler
• Video indirmelerinde bağlantı listesindeki "Veri alınıyor" satırları da yeşil gösterilir

## 1.7.11
• Akıcı gösterim: indirme penceresinde ve listede yüzde, indirilen miktar, aktarım hızı ve ilerleme çubuğu artık sıçramadan, yumuşak ilerler (%14 → %18 → %23 gibi atlamalar yerine %14.1, %14.2…); hız dalgalanmadan gösterilir. Yalnızca görünüm değişti, indirme hızı aynı

## 1.7.10
• Tarayıcı eklentisi 1.5.3: 1.7.8'deki değişiklikten sonra bazı büyük video sitelerinde "Bu videoyu indir" düğmesi hiç görünmüyordu; düzeltildi (düğme yine yalnızca ekranda görünen videoda çıkar)

## 1.7.9
• Düzeltme: bazı bilgisayarlarda gofile gibi sitelerden indirirken çıkan "CERTIFICATE_VERIFY_FAILED: certificate has expired" hatası giderildi. HTTPS sertifikaları artık tarayıcılar gibi Windows'un kendi doğrulamasıyla denetleniyor (gerekli yeni kök sertifikalar Windows tarafından otomatik alınır); güvenlik denetimi gevşetilmedi

## 1.7.8
• Tarayıcı eklentisi 1.5.2: Instagram hikâyeleri gibi sayfalarda "Bu videoyu indir" düğmesi yalnızca ekranda görünen videoda çıkar (önceden yüklenmiş, gizli ya da kenardan kesilmiş videolar için boş alanlarda düğmeler çıkıyordu)

## 1.7.7
• Kurulum sihirbazının yan görselindeki yazı, kurulumda seçilen dilde görünür

## 1.7.6
• Düzeltme: TurboDM.exe'nin dosya özelliklerinde (Ayrıntılar) sürüm artık doğru görünür (hep 1.0.0.0 yazıyordu)
• Kurulum sihirbazının yan görselindeki özellik satırı güncellendi
• Kod ve belgelerde genel temizlik: kullanılmayan kod ve metinler kaldırıldı, geliştirici notları güncellendi

## 1.7.5
• Pencere kapatılıp program sistem tepsisine indiğinde "Program arka planda çalışmaya devam ediyor" bildirimi artık her seferinde değil, yalnızca ilk kez gösterilir

## 1.7.4
• Tarayıcı eklentisi 1.5.1: video bulunan sekme kapatılınca eklentiler sayfasında görünen "No tab with id" hata kaydı artık oluşmuyor (zararsızdı, işleyişi etkilemiyordu)

## 1.7.3
• Düzeltme: listedeki hata durumu ("Hata: …") ve video akışlarındaki "yeniden deneniyor" bilgisi de seçilen dilde görünür
• GitHub sayfası: İngilizce sayfada programın İngilizce ekran görüntüleri

## 1.7.2
• Varsayılan dil yeniden Windows'un dili (kurulumda ve programda); Language menüsünün başında "Sistem dili (otomatik)" seçeneği

## 1.7.1
• Dil anında değişir: menü çubuğunda sabit "Language" menüsü; seçince program kapanmadan menüler, liste ve açık indirme pencereleri yeni dile geçer, indirmeler sürer
• Varsayılan dil İngilizce (kurulumda ve programda); dil kurulumun başında ya da Language menüsünden seçilir

## 1.7.0
• Dil desteği: Türkçe, English, Deutsch, Français, Español, العربية (sağdan sola düzen), Italiano — Seçenekler → Genel → Dil; varsayılan Windows'un dili
• Kurulum programı en başta dil sorar; seçilen dil programın dili olur. Kurulum ve kaldırma pencereleri de seçilen dilde
• Tarayıcı eklentisi 1.5.0: 7 dil (tarayıcının diline göre)
• Güncelleme penceresindeki sürüm notları programın diline göre (Türkçe ya da İngilizce); GitHub sayfası ve sürüm notları İngilizce olarak da var

## 1.6.4
• Güncelleme penceresi, güncellemede ne olacağını açıklar: program kısa süre kapanır, kurulum bitince görev çubuğunda kendiliğinden açılır, inmekte olan indirmeler kaldığı yerden sürer

## 1.6.3
• Yardım → Sürüm notları: tüm sürümlerin değişiklik notları tek sayfada (GitHub'da da herkese açık)

## 1.6.2
• TurboDM artık açık kaynak: GNU GPL v3 lisansı; kaynak kodu github.com/wexaR-TDM/TurboDM adresinde
• Lisans metni kurulumla birlikte gelir; Hakkında penceresinde lisans ve kaynak kodu bağlantısı

## 1.6.1
• İndirme pencereleri ana pencereden bağımsız: ana pencere simge durumuna küçültülünce onlar açık kalır

## 1.6.0
• Biçim seçimi: indirme penceresinde "Biçim" — MP4 (olduğu gibi), MKV (kayıpsız, hızlı), AVI (eski TV/oynatıcılar için), MP3 (yalnızca ses); dönüştürme indirme bitince yapılır
• DASH (.mpd) video akışları desteklenir
• Gömülü oynatıcılar: video, oynatıcının kendi sayfa adresi ve kökeniyle istenir (403 hatası veren sunucular için)
• Tarayıcı eklentisi 1.4.4: DASH akışlarını ve gömülü oynatıcıların adresini yakalar

## 1.5.8
• Proje deposunun yeni adresi: github.com/wexaR-TDM/TurboDM (eski adres yönlendirir; güncellemeler kesintisiz)
• Lisans: kurulumla gelen ffmpeg'in birebir kaynak kodu her sürüm sayfasında yayımlanır; kaynak bilgisi ffmpeg klasöründe
• Tarayıcı eklentisi 1.4.3: proje sayfası bağlantısı güncellendi

## 1.5.7
• Güvenlik: güncellemeler artık dijital imzalı. TurboDM yalnızca geliştiricinin imzaladığı güncellemeyi kurar; sahte güncelleme dağıtılamaz
• Güvenlik: güncelleme yalnızca resmi GitHub sürüm sayfasından indirilir

## 1.5.6
• Yeni açılan pencereler (indirme penceresi, seçenekler, uyarılar) ekranın tam ortasında açılır

## 1.5.5
• Sunucu bağlantı sınırı sabit kalmaz: indirme sorunsuz sürerken ~20 sn'de bir yeni bağlantı denenir; sunucu izin verirse hız artar ve yeni sınır kaydedilir

## 1.5.4
• Sunucu bağlantı sınırı (IDM gibi): sunucu az bağlantıya izin veriyorsa (ör. gofile) fazla bağlantılar indirmeyi bozmadan çekilir; indirme çalışan bağlantılarla sürer, hız dalgalanması azalır
• Tek bir bağlantının tekrar tekrar hata vermesi artık tüm indirmeyi durdurmaz; yalnızca hiçbir bağlantı çalışmıyorsa hata verilir
• Öğrenilen sınır kaydedilir: devam ettirince sunucunun izin verdiği kadar bağlantı açılır; indirme penceresinde gösterilir
• Bağlantı listesinde hatanın gerçek nedeni yazılır; sunucu "Retry-After" bildirirse ona uyulur

## 1.5.3
• Hakkında penceresi sadeleşti; video bileşeni her yerde "Video motoru" olarak anılır

## 1.5.2
• Yeni TurboDM teması: Windows'un açık/koyu moduna kendiliğinden uyar; Windows'ta mod değişince program açıkken de anında geçer
• TurboDM'e özel çizgi simgeler, logo ve adla araç çubuğu, sayılı kategori menüsü
• Listede "Durum" sütununda ince ilerleme çizgisi; tamamlananlar yeşil, hatalılar kırmızı
• Pencere başlıkları temanın rengini alır (Windows 11)
• Seçenekler → Genel → Tema: Windows ile aynı / Açık / Koyu

## 1.5.1
• Toplu işlem: listenin başında onay kutuları; kutuya tıklayınca satır diğer seçimler bozulmadan seçime eklenir
• Başlıktaki kutu ile tümünü seç / seçimi kaldır; Ctrl+A ve Esc kısayolları
• "Toplu seçim" menüsü: bitmemişleri, bitenleri, durdurulanları, hatalıları seç
• Sağ tık menüsü birden çok indirmede hepsine uygulanır (devam, durdur, kuyruk, adresleri kopyala, sil)
• Düzeltme: liste yenilenince çoklu seçimin yalnızca son satırı kalıyordu

## 1.5.0
• Torrent hızlandı: indirirken yükleme hızı otomatik sınırlanır (dolan yükleme hattı indirmeyi yavaşlatıyordu)
• Torrent: daha çok eşe daha hızlı bağlanma, daha derin parça isteği kuyruğu, çok çekirdekli parça doğrulama
• Torrent: şifreli bağlantı tercih edilir ve bilinen 6881 yerine rastgele port kullanılır (servis sağlayıcı yavaşlatmalarına karşı)
• Seçenekler → Torrent: "İndirirken yükleme hızını otomatik sınırla" ayarı
• Güncelleme sonrası TurboDM kendiliğinden yeniden açılır (görev çubuğunda, öne çıkmadan); inmekte olan indirmeler kaldığı yerden sürer

## 1.4.9
• Tarayıcı eklentisi 1.4.2: Türkçe ve İngilizce dil desteği (eklentinin adı ve açıklaması tarayıcının diline göre)

## 1.4.8
• Tarayıcı eklentisi 1.4.1: TurboDM simgesi (araç çubuğu ve eklentiler sayfası), mağazaya hazır paket

## 1.4.7
• Tarayıcı eklentisi 1.4.0: "Bu videoyu indir" düğmesi ve kalite menüsü artık her sitede çalışır (Vimeo, Dailymotion, X ve daha fazlası)
• Eklenti sayfadaki videoyu TurboDM'e iletir, kaliteleri TurboDM bulur; sayfanın yüklediği video akışları da aynı menüde
• Eklenti penceresinde her sayfa için "Bu sayfadaki videoyu TurboDM'de aç" düğmesi

## 1.4.6
• Güncellemeler artık GitHub üzerinden: Yardım → Güncellemeleri denetle ile yeni sürüm indirilip kurulabilir

## 1.4.5
• Güncelleme sırasında inmekte olan indirmeler, güncelleme bitince kaldığı yerden otomatik olarak sürer

## 1.4.4
• Torrent: .torrent bağlantıları artık dosya olarak kaydedilmez, doğrudan torrent olarak açılır (dosya seçimi penceresi)
• Torrent: dosyayı yalnızca tarayıcıya veren sitelerde (indirme düğmeli sayfalar) .torrent tarayıcıda iner ve otomatik olarak TurboDM'de açılır (tarayıcı eklentisi 1.3.2)
• Site torrent yerine web sayfası gönderirse .html kaydetmek yerine ne yapılacağı anlatılır
• İndirme penceresine küçült ve tam ekran düğmeleri eklendi; küçültülünce görev çubuğuna iner

## 1.4.3
• Kaldırma: kayıt defterinde boş 'Software\TurboDM' anahtarı da artık silinir (hiç iz kalmaz)

## 1.4.2
• Güvenlik: tarayıcı köprüsü yalnızca yerel adresten gelen istekleri kabul eder (DNS rebinding koruması)
• Aynı anda iki kez açılma ve köprü portunu kullanan başka bir program artık sorun çıkarmaz
• İndirme listesi bozulursa bir önceki sağlam kopyadan otomatik kurtarılır
• İndirme başlamadan disk alanı denetlenir; disk/izin hataları anlaşılır Türkçe mesajla hemen bildirilir
• Süresi dolan yönlendirme adresleri (bulut depolama, GitHub vb.) otomatik yenilenir
• Çok uzun ve Windows'ta yasak dosya adları (CON, NUL…) düzeltilir

## 1.4.1
• Büyük dosyalarda (ör. 22 GB 8K video) indirme başında yaşanan uzun bekleme giderildi: geçici dosya seyrek dosya olarak açılır
• Renkler TurboDM mavisi: Windows vurgu rengi (ör. kırmızı) artık ilerleme çubuğuna ve tablolara yansımaz
• İndirme penceresinde 'Kayıt klasörü' yalnızca klasörü gösterir; dosya adı otomatik verilir

## 1.4.0
• IDM düzeninde indirme penceresi: bağlantılar ve parçalı ilerleme çubuğu alt bölümde (Ayrıntıları gizle/göster)
• Yeni sekme 'Hız sınırlayıcı': indirmeye özel hız sınırı, indirme sürerken değiştirilebilir
• Yeni sekme 'Bitince yapılacaklar': bilgisayarı kapat / uyku / TurboDM'den çık (30 sn geri sayım, iptal edilebilir)
• Zamanlayıcı: kuyruk bitince bilgisayarı kapat / uyku / çık

## 1.3.1
• Tarayıcı menüsünde kalite seçilince kayıt yeri penceresi açılır (kalite ve uzantı seçili gelir; Sonra İndir / İndirmeyi Başlat sizde)

## 1.3.0
• YouTube'da 'Bu videoyu indir' düğmesi kalite menüsünü sayfada açar; seçilen kalite soru sorulmadan iner (IDM gibi)
• TurboDM'in pencereleri ve uyarıları (indirme, tamamlandı, hata) ekranın önüne gelir
• İndirme hatasında önde bir uyarı ve 'Tekrar Dene' düğmesi

## 1.2.0
• YouTube indirmeleri 2–3 kat hızlı: görüntü ve ses aynı anda, 24 bağlantıyla (IDM yöntemi)
• Düzeltme: başlığında ™ gibi özel karakter olan videolar "yt-dlp çıkış kodu 0" hatası veriyordu
• Akış adresinin süresi dolarsa otomatik yenilenir, indirme kaldığı yerden sürer
• Önceki sürümde hata sanılan ama aslında inmiş videolar "Devam Et" ile yeniden indirilmeden tamamlanır
• Windows bildirimlerinde program adı "TurboDM" olarak görünür
• Düzeltme: hız sınırı açıkken Duraklat'tan hemen sonra Devam Et dosyayı bozabiliyordu
• Düzeltme: bağlantısı erken kopan tek parçalı indirmeler yarım hâliyle "tamamlandı" sayılıyordu

## 1.1.0
• YouTube ve diğer sitelerden video indirme (1080p/4K, yalnızca ses) — tarayıcıda videonun üstündeki düğmeyle
• Yardım → Güncellemeleri denetle: TurboDM ve YouTube motoru tek pencereden güncellenir
• TurboDM temalı yeni kurulum sihirbazı; kurulu sürüm kontrolü ve güncelleme modu
• Kaldırma seçenekleri: ayarlar, yarım kalanlar ve indirilen dosyalar ayrı ayrı seçilebilir

## 1.0.0
• İlk sürüm: çok bağlantılı indirme, FTP, HLS video, BitTorrent, tarayıcı eklentisi

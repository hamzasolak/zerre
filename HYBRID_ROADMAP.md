# ZERRE — GPU + Optik Hibrit Araştırma Yol Haritası (`Sonraki Aşama Notları`)

> **Amaç:** Bu doküman, `v0.5.0` ve `v0.6` çalışmalarında teknik dezavantajların (tek katman sınırı, yapısal uyumsuzluk, 60 Hz tekil görüntü hızı) giderilmesinin ardından **ZERRE optoelektronik mimarisi ile GPU hesaplamasının gerçekten iddialı biçimde birleşeceği 4 hibrit araştırma yönünü** kalıcı referans olarak saklar.

---

## Temel İlke: Veri Neden E→O→E Dönüşümüne Yakalanmamalı?

Dijital bellekte zaten hazır bulunan küçük bir görüntüyü (`28×28` MNIST) `60 Hz` bir LCD'ye yazdırıp kırınımdan geçirip CMOS ile geri okumanın elektronik I/O maliyeti, optik geçişin hızını (`~0,33 ns`) bastırır. **İddialı bir GPU + Optik hibrit çalışma**, optik katmanın GPU'nun tek başına fiziksel olarak erişemediği veya çok yüksek bellekle/maliyetle yapabildiği bir işi üstlendiği rejimde ortaya çıkar:

1. Giriş bilgisinin zaten ışık alanı olarak geldiği durumlar (sıfır `E→O` dönüşüm maliyeti),
2. Çok büyük uzamsal çözünürlüklerde (`1024×1024+`) tek geçişli optik frekans/uzay operatörleri,
3. Yapısal donanım uyumsuzluğunu GPU kalibrasyonuyla yenen fiziksel prototipler,
4. Optik güncellemeyi sıfırlayan sabit/rastgele yüksek boyutlu optik rezervuarlar.

---

## Fikir 1 — Giriş LCD'siz "Programlanabilir Optik Ön-Uç + GPU Ortak Eğitimi" *(En Yüksek Öncelik)*

### Mimari Fikir
İlk giriş LCD'si (`E→O` kodlayıcısı) kaldırılır; doğrudan sahneden veya mikroskoptan gelen fiziksel ışık `7 μm` mSLA LC faz/genlik maskesinden geçirilip doğrudan CMOS sensöre düşürülür. GPU yalnızca sensörde oluşan düşük boyutlu (`32×32` veya `64×64`) veya görev-odaklı ön-işlenmiş haritayı alır.

### GPU'nun Tek Başına Yapamadığı 3 Güçlü Uygulama
1. **Etiketsiz Faz Mikroskopisi (Label-Free Phase / Brightfield Sensing):**
   Şeffaf biyolojik hücreler ışığın genliğini çok az, **fazını** ise belirgin biçimde değiştirir. Standart kamera + GPU şeffaf nesnede faz bilgisini kaybeder; mSLA LC düzlemi optik olarak faz kontrastı/türev filtresi gibi eğitilip bilgiyi yoğunluğa çevirerek GPU sınıflandırıcısıyla uçtan uca (end-to-end) optimize edilir.
2. **Optik Gizlilik Korumalı Akıllı Kamera (Privacy-Preserving Vision):**
   mSLA ağırlık düzlemi sahnedeki insan kimliğini (yüz detaylarını) sensöre düşmeden **optik alanda geri döndürülemez biçimde bozar**; ancak arka plandaki GPU ağı yalnızca izin verilen görevi (düşme algılama, kişi sayımı, güvenlik ekipmanı tespiti) yüksek doğrulukla sürdürür.
3. **Sıfır E→O Maliyeti ve Sensör-GPU Bant Genişliği Sıkıştırması:**
   12 MP ham görüntüyü GPU belleğine taşıyıp ilk evrişim katmanlarını çalıştırmak yerine, optik kırınım katmanı bilgiyi kamera üzerinde sıkıştırır.

### Ek Donanım / Başarı Ölçütü
* **Donanım:** 1. giriş mSLA paneli çıkarılır, önüne nesne/mikroskop aydınlatması veya sahne objektifi gelir (maliyet düşer).
* **Başarı Ölçütü:** Şeffaf faz hedeflerinde (`|A|=1, Δφ_nesne ≠ 0`) ham yoğunluk kamerası + GPU tabanını istatistiksel olarak geçmek; gizlilik testinde yeniden yapılandırma PSNR'ını düşürürken görev doğruluğunu korumak.

---

## Fikir 2 — `4f` Optik Mega-Konvolüsyon / Fourier Neural Operator (`FNO`) + GPU

### Mimari Fikir
Mevcut `Z_1 + Z_2` serbest uzay Fresnel kurulumuna iki ucuz akromatik mercek eklenerek **`4f` Fourier düzlemi** kurulur. mSLA paneli Fourier düzlemine konduğunda `1440×2560` piksel tek geçişte **devasa karmaşık frekans filtresi** ($F^{-1}\{M_{\text{LC}} \cdot F\{u\}\}$) uygular.

### GPU ile İş Bölümü
* **Optik Taraf:** Büyük çözünürlüklü (`512×512` → `2048×2048`) global evrişim ve PDE spektral operatörlerini görüntü boyutundan bağımsız tek geçişte yürütür.
* **GPU Taraf:** Küçük yerel (`3×3`) evrişimler, aktivasyonlar (`GELU/ReLU`) ve katman normalizasyonunu üstlenir.

### Ek Donanım / Başarı Ölçütü
* **Donanım:** İki `f = 75–100 mm` mercek (~60–120 USD ek maliyet) ve hassas `f` aralığı ray montajı.
* **Başarı Ölçütü:** Büyük çekirdekli görüntü restorasyonu veya Navier–Stokes / Helmholtz tarzı 2B PDE çözücülerinde GPU bellek bant genişliği kazancı.

---

## Fikir 3 — Gerçek 800 USD Masaüstü Prototip + "Kendi Kendini Kalibre Eden Hibrit İkiz"

### Mimari Fikir
`v0.5.0`'ın temel bilimsel keşfi (*"parametrik kaymalarda PAT güçlü ama yapısal uyumsuzlukta yalnız-kafa kalibrasyonunun gerisinde kalıyor"*) ile `v0.6` kara-kutu kalibre vekil çözümünü doğrudan **gerçek 800 USD masaüstü donanımında** birleştirir.

### GPU ile İş Bölümü
* Donanımdan toplanan küçük bir siyah-kutu kalibrasyon kümesiyle GPU üzerinde **Sinirsel Artık Fizik Vekili (`Neural Residual Physics Proxy` + öğrenilen TN panel LUT + kamera gamması + Zernike haritası)** öğrenilir.
* Ardından Sharpness-Aware Training (`SAT`, Ref. [24]) eklenerek cihazlar/günler arası drift altında kalibrasyon kararlılığı sağlanır.

### Başarı Ölçütü
* Gerçek masaüstü 532 nm lazer + TN mSLA + IMX708 kamerada kör PAT'ın başarısız olduğunu deneysel gösterip, GPU-kalibreli hibrit vekil PAT ile yalnızca dijital-kafa ayarını ve kör PAT'ı anlamlı farkla geçmek.

---

## Fikir 4 — Eğitimsiz Yüksek Boyutlu Optik Rezervuar (`ELM`) + Hafif GPU Kafa

### Mimari Fikir
`v0.5.0` Tablo III bulgusu (*`32×32` rastgele optik + MLP = `%94,20`*, neredeyse PAT'a denk) üzerine kuruludur: `60 Hz` / `~50 ms` LC güncelleme döngüsüyle ağırlıkları çevrimiçi eğitmeye çalışmak yerine, mSLA paneli **sabit veya blok-uzamsal çok kanallı rasgele kırınım/benek karıştırıcısı** olarak kullanıp yalnızca GPU'daki tek katmanlı hafif başlığı (`Ridge` / `Linear CE` / `Tiny MLP`) eğitmek.

### Avantaj ve Ödünleşim
* **Tamamen ortadan kalkan sorunlar:** Çevrimiçi PAT donanım eğitim süresi (saatler → saniyeler), LC gecikmesi, geri yayılım vekil hatası ve lazer beneği (artık yüksek boyutlu doğrusal olmayan rasgele özellik jeneratörüne dönüşür).
* **Başarı Ölçütü:** Sabit optik benek + dijital doğrusal kafa ile yüksek boyutlu çok kanallı sınıflandırmada maliyet/enerji başına doğruluk kıyası.

---

## Not Edilen Teknik Temel (`v0.6`)
Hibrit aşamaya geçmeden önce aşağıdaki üç temel dezavantajın sayısal çözümleri bu depoda (`zerre_twin.py`, `zerre_pat_torch.py`, `tests/test_zerre_physics.py`) doğrulanmış ve saklanmıştır:
1. **Tek-katmanlı pozitif yoğunluk darboğazı** → `FoldedMultiPassTwin` (tek mSLA ekranla katlanmış çok-katman + diferansiyel okuma $I_+ - I_-$).
2. **Yapısal model-uyumsuzluğu düşüşü** → `CalibratedSurrogateTwin` + `calibrate_surrogate_blackbox` (kara-kutu kalibre vekil PAT).
3. **60 Hz tekil görüntü darboğazı** → `SpatialBatchEngine` (tek karede paralel uzamsal mozaik paketleme).
